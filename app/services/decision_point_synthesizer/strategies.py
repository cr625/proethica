"""
Decision Point Synthesizer (Phase 3) -- LLM fallback/refinement strategies.

The three LLM strategies and their prompt-build / response-parse helpers, split
out of synthesizer.py as a mixin so the orchestrating class stays focused on the
pipeline. Mixed into DecisionPointSynthesizer, so every `self.` call resolves
across both (the strategies call retained helpers like _build_entity_uri_lookup /
_clean_text_formatting / _append_normative_status, and the orchestrator calls
these strategies). The import header mirrors synthesizer.py so relocated method
bodies resolve every name they reference.
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

from app import db
from app.models import TemporaryRDFStorage, ExtractionPrompt
from app.utils.llm_utils import get_llm_client
from app.utils.llm_json_utils import parse_json_response
from app.domains import DomainConfig, get_domain_config
from app.services.ontserve.ontserve_config import get_ontserve_mcp_url
from model_config import ModelConfig

from app.services.entity_analysis import (
    compose_decision_points,
    ComposedDecisionPoints,
    EntityGroundedDecisionPoint,
)
from app.services.ontserve.mcp_entity_enrichment_service import (
    enrich_prompt_with_metadata,
    EnrichmentResult,
)
from app.services.step4_synthesis.template_loader import get_step4_template

from .models import (
    ToulminStructure,
    QCAlignmentScore,
    CanonicalDecisionPoint,
    Phase3SynthesisResult,
    SynthesisTrace,
)

logger = logging.getLogger(__name__)

# Toulmin (1958) field specification, single-sourced into every decision-point
# prompt. Each field must respect its category from The Uses of Argument; the
# 2026-07-08 audit found the earlier loose paraphrases ("what creates
# uncertainty") let rebuttals drift into generic counter-considerations and
# omitted claim and qualifier entirely.
TOULMIN_FIELD_SPEC = """Toulmin argument structure (Toulmin 1958). Each field must respect its category:
- toulmin_claim: the CLAIM. The course of action asserted as the right one. Where the Board ruled, this states the Board's chosen course; where it did not, the course the case record best supports.
- toulmin_data: the GROUNDS. The specific case facts appealed to in support of the claim. Facts only; no duties, principles, or evaluations.
- toulmin_warrants: the WARRANT(s). The general professional rules that license the step from those facts to the claim, stated as rules (e.g. "Engineers must hold paramount the safety of the public"). Where duties compete, state the competing warrants and which prevails.
- toulmin_qualifier: the QUALIFIER. The modal strength of the claim and any conditions the Board attached (e.g. "presumably", "unless the contract requires disclosure", "provided consent is obtained"). Empty string only when the claim is unconditional.
- toulmin_rebuttals: the REBUTTAL. The conditions of exception: the circumstances under which the warrant would NOT license the claim, stated as a defeating condition drawn from the case ("unless ...", "would not apply if ..."). Not a generic counter-argument and never empty; use the strongest case-supplied defeater.
- provision_labels: the BACKING. The NSPE Code sections that authorize the warrants (e.g. ["II.1.f", "I.1"]). Entries MUST be NSPE code section citations; do NOT put duty or principle names here."""


class LLMStrategiesMixin:
    """LLM refinement + the two generation fallbacks (causal-links, Q&C-direct)
    and their prompt/parse helpers. Mixed into DecisionPointSynthesizer."""

    REFINEMENT_BATCH_SIZE = 5

    def _llm_refine(
        self,
        case_id: int,
        candidates: List[EntityGroundedDecisionPoint],
        alignment_scores: List[QCAlignmentScore],
        questions: List[Dict],
        conclusions: List[Dict],
        question_emergence: List[Dict],
        resolution_patterns: List[Dict]
    ) -> Tuple[List[CanonicalDecisionPoint], str, str, Optional[EnrichmentResult]]:
        """
        Use LLM to refine top-scoring candidates into canonical decision points.

        When more than REFINEMENT_BATCH_SIZE candidates qualify, they are split
        into batches and each batch is refined in a separate LLM call. This
        prevents response truncation from exceeding max_tokens.

        Returns:
            Tuple of (canonical_points, prompt, response, enrichment_result)
        """
        # Select top candidates (score > 0.3 or top 8)
        score_map = {s.candidate_id: s for s in alignment_scores}
        top_candidates = []
        for candidate in candidates:
            score = score_map.get(candidate.focus_id)
            if score and (score.total_score > 0.3 or len(top_candidates) < 8):
                top_candidates.append((candidate, score))

        if not top_candidates:
            logger.warning("No candidates passed threshold - using all candidates")
            top_candidates = [(c, score_map.get(c.focus_id, QCAlignmentScore(c.focus_id, 0.0)))
                            for c in candidates[:8]]

        # Batch candidates if there are too many for a single LLM call
        batch_size = self.REFINEMENT_BATCH_SIZE
        if len(top_candidates) <= batch_size:
            batches = [top_candidates]
        else:
            batches = [
                top_candidates[i:i + batch_size]
                for i in range(0, len(top_candidates), batch_size)
            ]
            logger.info(f"Stage 3.3: Splitting {len(top_candidates)} candidates into {len(batches)} batches")

        all_canonical = []
        all_prompts = []
        all_responses = []
        enrichment_result = None

        for batch_idx, batch in enumerate(batches):
            batch_label = f"batch {batch_idx + 1}/{len(batches)}" if len(batches) > 1 else "single batch"

            # Calculate how many decision points this batch should produce
            # Distribute evenly: aim for 2-3 per batch, min 1
            if len(batches) == 1:
                target_count = "4-6"
            else:
                per_batch = max(1, round(len(batch) * 0.5))
                target_count = f"{per_batch}-{per_batch + 1}"

            prompt = self._build_refinement_prompt(
                case_id,
                batch,
                questions,
                conclusions,
                question_emergence,
                resolution_patterns,
                target_count=target_count,
            )

            # Enrich only the first batch prompt (enrichment applies globally)
            if batch_idx == 0:
                try:
                    enrichment_result = enrich_prompt_with_metadata(prompt, mode="glossary")
                    prompt = enrichment_result.enriched_text
                    logger.info(f"Enriched refinement prompt: {enrichment_result.mcp_resolved_count} from MCP, "
                               f"{enrichment_result.local_resolved_count} from local, "
                               f"{enrichment_result.not_found_count} not found")
                except Exception as e:
                    logger.warning(f"MCP enrichment failed, using unenriched prompt: {e}")

            try:
                from app.utils.llm_utils import streaming_completion

                # Retry once on failure (streaming timeout, JSON parse error, etc.)
                response_text = None
                last_error = None
                for attempt in range(2):
                    try:
                        response_text = streaming_completion(
                            self.llm_client,
                            model=ModelConfig.get_claude_model("default"),
                            max_tokens=32000,
                            prompt=prompt,
                            temperature=0.2,
                        )
                        logger.info(f"Stage 3.3 {batch_label} response: {len(response_text)} chars")

                        batch_points = self._parse_refinement_response(
                            response_text,
                            batch,
                            questions,
                            conclusions,
                            question_emergence,
                            resolution_patterns,
                            case_id=case_id
                        )
                        all_canonical.extend(batch_points)
                        all_prompts.append(prompt)
                        all_responses.append(response_text)
                        last_error = None
                        break
                    except Exception as retry_err:
                        last_error = retry_err
                        if attempt == 0:
                            logger.warning(f"Stage 3.3 {batch_label} attempt 1 failed: {retry_err}, retrying...")
                            continue

                if last_error:
                    raise last_error

            except Exception as e:
                logger.error(f"LLM refinement failed for {batch_label}: {e}")
                # Fall back to algorithmic conversion for this batch only
                batch_candidates = [c for c, _ in batch]
                batch_scores = [s for _, s in batch]
                fallback_points = self._convert_to_canonical_without_llm(
                    batch_candidates, batch_scores, questions, conclusions,
                    question_emergence, resolution_patterns
                )
                all_canonical.extend(fallback_points)
                all_responses.append(f"ERROR: {e}")

        # Renumber focus_ids sequentially across batches
        for i, dp in enumerate(all_canonical, 1):
            dp.focus_id = f"DP{i}"
            dp.focus_number = i

        combined_prompt = "\n---\n".join(all_prompts) if all_prompts else ""
        combined_response = "\n---\n".join(all_responses) if all_responses else ""

        if not all_canonical:
            logger.warning("All batches failed - full algorithmic fallback")
            all_canonical = self._convert_to_canonical_without_llm(
                candidates, alignment_scores, questions, conclusions,
                question_emergence, resolution_patterns
            )

        return all_canonical, combined_prompt, combined_response, enrichment_result

    def _llm_generate_from_causal_links(
        self,
        case_id: int,
        questions: List[Dict],
        conclusions: List[Dict],
        question_emergence: List[Dict],
        resolution_patterns: List[Dict]
    ) -> Tuple[List[CanonicalDecisionPoint], str, str, Optional[EnrichmentResult]]:
        """
        LLM fallback: Generate decision points from causal_normative_links when E1-E3 finds 0 candidates.

        Uses the already-extracted causal links (action-obligation relationships) to generate
        meaningful decision points via LLM.

        Returns:
            Tuple of (canonical_points, prompt, response, enrichment_result)
        """
        logger.info(f"LLM fallback: Loading causal links for case {case_id}")

        # Load causal_normative_links from database
        causal_links = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='causal_normative_link'
        ).all()

        if not causal_links:
            logger.warning("No causal links found for LLM fallback")
            return [], "", "", None

        # Format causal links for the prompt
        causal_links_text = []
        for i, link in enumerate(causal_links):
            link_data = link.rdf_json_ld or {}
            causal_links_text.append(f"""
{i+1}. {link.entity_label}
   - Action: {link_data.get('action_label', link.entity_label)}
   - Obligation: {link_data.get('fulfills_obligations', link_data.get('obligation_label', 'N/A'))}
   - Violates: {link_data.get('violates_obligations', 'N/A')}
   - Description: {link.entity_definition or link_data.get('description', '')}
""")

        # Format questions
        questions_text = []
        for i, q in enumerate(questions[:10]):  # Limit to 10
            questions_text.append(f"Q{i+1}: {q.get('question_text', q.get('text', ''))[:400]}")

        # Format conclusions. FULL text: the previous 200-character truncation
        # starved the model of the very holdings it must paraphrase and mark
        # board choices against -- the grounding failures the Phase-B judging
        # found persisted under prompt rules because the model never saw the
        # conclusions (2026-07-08 Decisions analysis).
        conclusions_text = []
        for i, c in enumerate(conclusions[:10]):  # Limit to 10
            conclusions_text.append(f"C{i+1}: {c.get('conclusion_text', c.get('text', ''))[:1200]}")

        prompt = get_step4_template('step4_dp_causal').render(
            causal_links_block="\n".join(causal_links_text),
            questions_block="\n".join(questions_text),
            conclusions_block="\n".join(conclusions_text),
            toulmin_field_spec=TOULMIN_FIELD_SPEC,
        )

        # HO-005: surface obligation compliance / capability proficiency
        prompt = self._append_normative_status(prompt)

        # Enrich prompt with entity definitions from OntServe MCP
        enrichment_result = None
        try:
            enrichment_result = enrich_prompt_with_metadata(prompt, mode="glossary")
            prompt = enrichment_result.enriched_text
            logger.info(f"Enriched causal link prompt: {enrichment_result.mcp_resolved_count} from MCP, "
                       f"{enrichment_result.local_resolved_count} from local, "
                       f"{enrichment_result.not_found_count} not found")
        except Exception as e:
            logger.warning(f"MCP enrichment failed, using unenriched prompt: {e}")

        try:
            from app.utils.llm_utils import streaming_completion
            response_text = streaming_completion(
                self.llm_client,
                model=ModelConfig.get_claude_model("default"),
                max_tokens=32000,
                prompt=prompt,
                temperature=0.3,
            )

            # Parse response
            canonical_points = self._parse_causal_link_response(
                response_text, case_id, questions, conclusions
            )

            logger.info(f"LLM fallback generated {len(canonical_points)} decision points")
            return canonical_points, prompt, response_text, enrichment_result

        except Exception as e:
            logger.error(f"LLM fallback failed: {e}")
            return [], prompt, f"ERROR: {e}", enrichment_result

    def _parse_causal_link_response(
        self,
        response_text: str,
        case_id: int,
        questions: List[Dict],
        conclusions: List[Dict]
    ) -> List[CanonicalDecisionPoint]:
        """Parse LLM response from causal link generation."""

        parsed = parse_json_response(
            response_text, "causal link decision points", strict=True
        )
        if not parsed:
            return []

        # Build question/conclusion URI lookup
        q_uri_map = {f"Q{i+1}": q.get('uri', '') for i, q in enumerate(questions)}
        c_uri_map = {f"C{i+1}": c.get('uri', '') for i, c in enumerate(conclusions)}

        # Resolve LLM labels to real extraction URIs
        entity_uri_lookup = self._build_entity_uri_lookup(case_id)

        canonical_points = []
        for i, dp_data in enumerate(parsed):
            # Find aligned question
            addresses = dp_data.get('addresses_questions', [])
            aligned_q_uri = None
            aligned_q_text = None
            if addresses:
                first_q = addresses[0] if isinstance(addresses, list) else addresses
                aligned_q_uri = q_uri_map.get(first_q, '')
                for q in questions:
                    if q.get('uri') == aligned_q_uri:
                        # `or`, not dict-default: question_text may be PRESENT
                        # but empty, which shadowed the text fallback (part of
                        # the aligned_question_text 4/75 sparsity).
                        aligned_q_text = q.get('question_text') or q.get('text', '')
                        break

            # Resolve role/obligation labels to proper extraction URIs
            role_label = dp_data.get('role_label', 'Unknown')
            role_uri = entity_uri_lookup.get(role_label.lower(), '') if role_label else ''
            obl_label = dp_data.get('obligation_label')
            obl_uri = entity_uri_lookup.get(obl_label.lower(), '') if obl_label else None

            # Build Toulmin structure from LLM-emitted fields. The fallback
            # prompts (causal-link and qc-direct) request these alongside
            # the high-level fields; older outputs that predate the prompt
            # update will simply produce empty strings, which render as
            # missing Toulmin in the view.
            # provision_labels must cite NSPE code sections; the LLM
            # intermittently emits duty/principle names there (44 across the
            # gold corpus, 2026-07-08 Provisions census). Non-codes drop --
            # the normative content is already carried by obligation_label
            # and the Toulmin warrants.
            from app.utils.provision_codes import is_provision_code
            provision_labels = [x for x in (dp_data.get('provision_labels', []) or [])
                                if is_provision_code(x)]
            toulmin = ToulminStructure(
                claim=dp_data.get('toulmin_claim', ''),
                data_summary=dp_data.get('toulmin_data', ''),
                warrants_summary=dp_data.get('toulmin_warrants', ''),
                qualifier=dp_data.get('toulmin_qualifier', ''),
                rebuttals_summary=dp_data.get('toulmin_rebuttals', ''),
                backing_provisions=provision_labels,
            )

            # Score fields from the LLM. Fall back to 0.0 (not the previous
            # 0.5 / 0.7 sentinels) so that flat-constant rows in the view
            # are immediately diagnosable as parse failures rather than
            # masquerading as real scores.
            try:
                intensity_score = float(dp_data.get('intensity_score', 0.0))
            except (TypeError, ValueError):
                intensity_score = 0.0
            try:
                qc_alignment_score = float(dp_data.get('qc_alignment_score', 0.0))
            except (TypeError, ValueError):
                qc_alignment_score = 0.0

            # Pass through options including option_id and is_board_choice.
            options_out = []
            for j, opt in enumerate(dp_data.get('options', [])):
                options_out.append({
                    'option_id': opt.get('option_id', f'O{j+1}'),
                    'label': opt.get('label', f'Option {j+1}'),
                    'description': opt.get('description', ''),
                    'is_board_choice': bool(opt.get('is_board_choice', False)),
                })

            # Conclusion alignment, mirroring the refinement parser: the
            # conclusions whose answersQuestions cover the DP's addressed
            # questions supply aligned_conclusion_* and the resolution text
            # verbatim. The fallback path never set these (Phase-C census
            # 2026-07-08: case 10's five fallback DPs all had empty
            # aligned_conclusion_uri, so the Step-5 resolution-pattern join
            # matched nothing).
            addresses_uris = [q_uri_map.get(q, q) for q in (addresses if isinstance(addresses, list) else [addresses])]
            addressed_nums = {q.get('question_number') for q in questions
                              if q.get('uri') in addresses_uris and q.get('question_number') is not None}
            answering = [c for c in conclusions
                         if addressed_nums & set(c.get('answersQuestions') or [])]
            aligned_c = answering[0] if answering else None
            derived_resolution = ' '.join(
                (c.get('conclusion_text') or c.get('text') or '').strip()
                for c in answering[:2]).strip()

            # Create canonical decision point
            dp = CanonicalDecisionPoint(
                focus_id=dp_data.get('focus_id', f'DP{i+1}'),
                focus_number=i + 1,
                description=dp_data.get('description', ''),
                decision_question=dp_data.get('decision_question', ''),
                role_uri=role_uri,
                role_label=role_label,
                obligation_uri=obl_uri,
                obligation_label=obl_label,
                provision_labels=provision_labels,
                toulmin=toulmin,
                aligned_question_uri=aligned_q_uri,
                aligned_question_text=aligned_q_text,
                aligned_conclusion_uri=aligned_c.get('uri') if aligned_c else None,
                aligned_conclusion_text=aligned_c.get('text') if aligned_c else None,
                board_resolution=(derived_resolution[:800] if derived_resolution
                                  else dp_data.get('board_resolution', '')),
                addresses_questions=addresses_uris,
                options=options_out,
                intensity_score=intensity_score,
                qc_alignment_score=qc_alignment_score,
                synthesis_method='llm_fallback',
            )
            self._clean_text_formatting(dp)
            canonical_points.append(dp)

        return canonical_points

    def _llm_generate_from_qc_direct(
        self,
        case_id: int,
        questions: List[Dict],
        conclusions: List[Dict],
        question_emergence: List[Dict],
        resolution_patterns: List[Dict]
    ) -> Tuple[List[CanonicalDecisionPoint], str, str, Optional[EnrichmentResult]]:
        """
        Last-resort fallback: Generate decision points directly from Q&C + QE + RP
        when both E1-E3 and causal link fallback produce nothing.

        This path uses the rich analysis data (questions, conclusions, question emergence,
        resolution patterns) plus obligation/role context to synthesize decision points.
        """
        logger.info(f"Q&C direct fallback: Synthesizing decision points for case {case_id}")

        # Load obligations and roles for grounding
        obligations = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='obligations'
        ).all()
        roles = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='roles'
        ).all()

        # Format questions
        questions_text = []
        for i, q in enumerate(questions[:15]):
            q_text = q.get('question_text', q.get('text', ''))
            source = q.get('source', '')
            source_tag = f" [{source}]" if source else ""
            questions_text.append(f"Q{i+1}{source_tag}: {q_text[:250]}")

        # Format conclusions
        conclusions_text = []
        for i, c in enumerate(conclusions[:15]):
            c_text = c.get('conclusion_text', c.get('text', ''))
            source = c.get('source', '')
            source_tag = f" [{source}]" if source else ""
            conclusions_text.append(f"C{i+1}{source_tag}: {c_text[:250]}")

        # Format question emergence (how questions arise)
        qe_text = []
        for i, qe in enumerate(question_emergence[:10]):
            qe_str = qe.get('description', qe.get('text', ''))
            q_ref = qe.get('question_ref', '')
            qe_text.append(f"QE{i+1} (re {q_ref}): {qe_str[:200]}")

        # Format resolution patterns (how board resolved)
        rp_text = []
        for i, rp in enumerate(resolution_patterns[:10]):
            rp_str = rp.get('description', rp.get('text', ''))
            c_ref = rp.get('conclusion_ref', '')
            rp_text.append(f"RP{i+1} (re {c_ref}): {rp_str[:200]}")

        # Format obligations
        obl_text = []
        for i, o in enumerate(obligations[:15]):
            obl_text.append(f"O{i+1}: {o.entity_label} -- {(o.entity_definition or '')[:150]}")

        # Format roles
        role_text = []
        for i, r in enumerate(roles[:10]):
            role_text.append(f"R{i+1}: {r.entity_label}")

        prompt = get_step4_template('step4_dp_qc_direct').render(
            questions_block="\n".join(questions_text),
            conclusions_block="\n".join(conclusions_text),
            qe_block="\n".join(qe_text),
            rp_block="\n".join(rp_text),
            obligations_block="\n".join(obl_text),
            roles_block="\n".join(role_text),
            toulmin_field_spec=TOULMIN_FIELD_SPEC,
        )

        # HO-005: surface obligation compliance / capability proficiency
        prompt = self._append_normative_status(prompt)

        enrichment_result = None
        try:
            enrichment_result = enrich_prompt_with_metadata(prompt, mode="glossary")
            prompt = enrichment_result.enriched_text
            logger.info(f"Enriched Q&C direct prompt: {enrichment_result.mcp_resolved_count} from MCP, "
                       f"{enrichment_result.local_resolved_count} from local")
        except Exception as e:
            logger.warning(f"MCP enrichment failed: {e}")

        try:
            from app.utils.llm_utils import streaming_completion
            response_text = streaming_completion(
                self.llm_client,
                model=ModelConfig.get_claude_model("default"),
                max_tokens=32000,
                prompt=prompt,
                temperature=0.3,
            )

            # Reuse the same parser as the causal link fallback
            canonical_points = self._parse_causal_link_response(
                response_text, case_id, questions, conclusions
            )

            logger.info(f"Q&C direct fallback generated {len(canonical_points)} decision points")
            return canonical_points, prompt, response_text, enrichment_result

        except Exception as e:
            logger.error(f"Q&C direct fallback failed: {e}")
            return [], prompt, f"ERROR: {e}", enrichment_result

    def _build_refinement_prompt(
        self,
        case_id: int,
        top_candidates: List[Tuple[EntityGroundedDecisionPoint, QCAlignmentScore]],
        questions: List[Dict],
        conclusions: List[Dict],
        question_emergence: List[Dict],
        resolution_patterns: List[Dict],
        target_count: str = "4-6",
    ) -> str:
        """Build LLM prompt for decision point refinement."""

        # Format candidates with scores
        candidates_text = []
        for candidate, score in top_candidates:
            candidates_text.append(f"""
### {candidate.focus_id} (Q&C Alignment: {score.total_score:.2f})
- Description: {candidate.description}
- Question: {candidate.decision_question}
- Role: {candidate.grounding.role_label} [{candidate.grounding.role_uri}]
- Obligation: {candidate.grounding.obligation_label or 'N/A'} [{candidate.grounding.obligation_uri or 'N/A'}]
- Matched Questions: {', '.join(score.matched_questions) or 'None'}
- Options:
""" + "\n".join(
                f"    O{j+1}: {opt.description} [{'chosen' if opt.is_extracted_action else 'alternative'}]"
                for j, opt in enumerate(candidate.options)
            ))


        # Format questions with Toulmin analysis. Stored QE/RP keys are
        # normalized to the in-memory lists' key form (qc_refs key_aliases;
        # mixed-generation join tolerance -- c422755 review).
        from app.services.step4_synthesis.qc_refs import key_aliases
        _q_alias = key_aliases(questions, 'Q')
        _c_alias = key_aliases(conclusions, 'C')
        qe_map = {_q_alias.get(qe.get('question_uri', ''), qe.get('question_uri', '')): qe
                  for qe in question_emergence}
        questions_text = []
        for i, q in enumerate(questions):
            q_uri = q.get('uri', '')
            qe = qe_map.get(q_uri, {})
            questions_text.append(f"""
Q{i}: {q.get('text', q.get('label', ''))}
  - URI: {q_uri}
  - DATA (triggering facts): {', '.join(qe.get('data_events', []) + qe.get('data_actions', [])) or 'Not analyzed'}
  - WARRANTS (competing obligations): {qe.get('competing_warrants', 'Not analyzed')}
  - REBUTTAL: {qe.get('rebuttal_conditions', 'Not analyzed')[:200] if qe.get('rebuttal_conditions') else 'None'}
""")

        # Format conclusions with resolution patterns (same normalization).
        rp_map = {_c_alias.get(rp.get('conclusion_uri', ''), rp.get('conclusion_uri', '')): rp
                  for rp in resolution_patterns}
        conclusions_text = []
        for i, c in enumerate(conclusions):
            c_uri = c.get('uri', '')
            rp = rp_map.get(c_uri, {})
            conclusions_text.append(f"""
C{i}: {c.get('text', c.get('label', ''))}
  - URI: {c_uri}
  - Determinative Principles: {', '.join(rp.get('determinative_principles', [])) or 'Not analyzed'}
  - Resolution: {rp.get('resolution_narrative', '')[:200] if rp.get('resolution_narrative') else 'Not analyzed'}
""")

        _refinement_prompt = get_step4_template('step4_dp_refine').render(
            case_id=case_id,
            candidates_block=''.join(candidates_text),
            questions_block=''.join(questions_text),
            conclusions_block=''.join(conclusions_text),
            toulmin_field_spec=TOULMIN_FIELD_SPEC,
            target_count=target_count,
        )
        # HO-005: surface obligation compliance / capability proficiency
        return self._append_normative_status(_refinement_prompt)

    def _parse_refinement_response(
        self,
        response_text: str,
        top_candidates: List[Tuple[EntityGroundedDecisionPoint, QCAlignmentScore]],
        questions: List[Dict],
        conclusions: List[Dict],
        question_emergence: List[Dict],
        resolution_patterns: List[Dict],
        case_id: int = None
    ) -> List[CanonicalDecisionPoint]:
        """Parse LLM refinement response into canonical decision points."""

        synthesis_data = parse_json_response(
            response_text, "decision point refinement", strict=False
        )
        if not synthesis_data:
            raise ValueError("No JSON found in LLM refinement response")

        # Build label->URI lookup from algorithmic candidates so we don't
        # trust the LLM's fabricated URIs (e.g. "case-74#Engineer" instead
        # of the real extraction URI).
        entity_uri_lookup = {}  # lowercase label -> URI
        uri_to_label = {}  # URI -> shortest canonical label
        for candidate, _ in top_candidates:
            g = candidate.grounding
            if g.role_label and g.role_uri:
                entity_uri_lookup[g.role_label.lower()] = g.role_uri
                # Keep the shortest label per URI (prefer "Engineer A" over
                # "Engineer A Water Rights Analysis Engineer")
                existing = uri_to_label.get(g.role_uri)
                if existing is None or len(g.role_label) < len(existing):
                    uri_to_label[g.role_uri] = g.role_label
            if g.obligation_label and g.obligation_uri:
                entity_uri_lookup[g.obligation_label.lower()] = g.obligation_uri
            if g.constraint_label and g.constraint_uri:
                entity_uri_lookup[g.constraint_label.lower()] = g.constraint_uri

        # Back the candidate lookup with the committed case graph: candidates
        # cover only the composed groundings, and an unvalidated fallback to the
        # LLM-echoed URI put obligation URIs into role slots (2026-07-08
        # Decisions analysis, case 9). A URI the case graph does not know is
        # dropped rather than stored.
        known_uris = set(entity_uri_lookup.values())
        if case_id is not None:
            try:
                from rdflib import RDFS as _RDFS
                from app.services.entity.committed_case_graph import load_case_graph
                _g = load_case_graph(case_id)
                for _s, _o in _g.subject_objects(_RDFS.label):
                    entity_uri_lookup.setdefault(str(_o).lower(), str(_s))
                    known_uris.add(str(_s))
            except Exception as _exc:  # noqa: BLE001 - no committed TTL yet
                logger.info(f"Case-graph label lookup unavailable for case {case_id}: {_exc}")
            known_uris.update(entity_uri_lookup.values())

        def _resolve_uri(label: str, llm_uri: str) -> str:
            """Label -> URI via candidates + case graph; an LLM-echoed URI is
            kept only when the case graph knows it."""
            if label:
                resolved = entity_uri_lookup.get(label.lower())
                if resolved:
                    return resolved
            return llm_uri if llm_uri in known_uris else ''

        def _resolve_role_label(label: str, resolved_uri: str) -> str:
            """Normalize role label to the canonical (shortest) form for the URI."""
            canonical = uri_to_label.get(resolved_uri)
            if canonical:
                return canonical
            return label

        canonical_points = []
        for i, data in enumerate(synthesis_data, 1):
            # Build Toulmin structure
            from app.utils.provision_codes import is_provision_code
            provision_labels = [x for x in (data.get('provision_labels', []) or [])
                                if is_provision_code(x)]
            toulmin = ToulminStructure(
                claim=data.get('toulmin_claim', ''),
                data_summary=data.get('toulmin_data', ''),
                warrants_summary=data.get('toulmin_warrants', ''),
                qualifier=data.get('toulmin_qualifier', ''),
                rebuttals_summary=data.get('toulmin_rebuttals', ''),
                backing_provisions=provision_labels
            )

            # Map question indices to URIs
            addresses_q = []
            for q_ref in data.get('addresses_questions', []):
                if isinstance(q_ref, int) and q_ref < len(questions):
                    addresses_q.append(questions[q_ref].get('uri', ''))
                elif isinstance(q_ref, str):
                    # Could be "Q0", "Q1" format
                    try:
                        idx = int(q_ref.replace('Q', ''))
                        if idx < len(questions):
                            addresses_q.append(questions[idx].get('uri', ''))
                    except ValueError:
                        addresses_q.append(q_ref)  # Already a URI

            # Get primary aligned Q&C
            aligned_q = None
            aligned_c = None
            if addresses_q and questions:
                for q in questions:
                    if q.get('uri') in addresses_q:
                        aligned_q = q
                        break

            # Board resolution derived from the record, not LLM-authored: the
            # conclusions whose answersQuestions cover the DP's addressed
            # questions supply the text verbatim. The LLM-authored field
            # embellished beyond the record even under explicit grounding
            # rules (case-4 audit: a 'clearly labeled recommendation'
            # carve-out present in neither conclusions nor discussion). The
            # LLM text is kept only when no answering conclusion resolves.
            addressed_nums = set()
            for q in questions:
                if q.get('uri') in addresses_q and q.get('question_number') is not None:
                    addressed_nums.add(q.get('question_number'))
            answering = [c for c in conclusions
                         if addressed_nums & set(c.get('answersQuestions') or [])]
            if answering:
                aligned_c = answering[0]
                derived = ' '.join(
                    (c.get('conclusion_text') or c.get('text') or '').strip()
                    for c in answering[:2]).strip()
                if derived:
                    data['board_resolution'] = derived[:800]

            canonical = CanonicalDecisionPoint(
                focus_id=data.get('focus_id', f'DP{i}'),
                focus_number=i,
                description=data.get('description', ''),
                decision_question=data.get('decision_question', ''),
                role_uri=(resolved_role_uri := _resolve_uri(data.get('role_label', ''), data.get('role_uri', ''))),
                role_label=_resolve_role_label(data.get('role_label', ''), resolved_role_uri),
                obligation_uri=_resolve_uri(data.get('obligation_label'), data.get('obligation_uri', '')),
                obligation_label=data.get('obligation_label'),
                constraint_uri=_resolve_uri(data.get('constraint_label'), data.get('constraint_uri', '')),
                constraint_label=data.get('constraint_label'),
                # Action slot type-filtered: the LLM intermittently echoes
                # Constraint/State class URIs or non-action individuals here
                # (case 57: ScopeOfPracticeCompetenceConstraint,
                # SupervisoryDirectionState), which silently defeats the
                # timeline's decision-point nesting -- it matches this slot
                # against temporal Action_/Event_ individuals. Same category
                # discipline as the provision-slot filter.
                involved_action_uris=[
                    u for u in (data.get('involved_action_uris') or [])
                    if isinstance(u, str)
                    and ('#Action_' in u or '#Event_' in u)
                ],
                provision_uris=data.get('provision_uris', []),
                provision_labels=provision_labels,
                toulmin=toulmin,
                aligned_question_uri=aligned_q.get('uri') if aligned_q else None,
                aligned_question_text=aligned_q.get('text') if aligned_q else None,
                aligned_conclusion_uri=aligned_c.get('uri') if aligned_c else None,
                aligned_conclusion_text=aligned_c.get('text') if aligned_c else None,
                addresses_questions=addresses_q,
                board_resolution=data.get('board_resolution', ''),
                options=data.get('options', []),
                intensity_score=data.get('intensity_score', 0.0),
                qc_alignment_score=data.get('qc_alignment_score', 0.0),
                source='unified',
                source_candidate_ids=data.get('source_candidate_ids', []),
                # Honest provenance: when composition yields fewer candidates
                # than the target count, the refinement generates additional
                # DPs beyond the candidate pool. Those cite no algorithmic
                # source, so labeling them 'algorithmic+llm' overstated the
                # grounding (Phase-C census 2026-07-08: 10 of 76).
                synthesis_method=('algorithmic+llm' if data.get('source_candidate_ids')
                                  else 'llm_direct'),
                llm_refined_description=data.get('description'),
                llm_refined_question=data.get('decision_question')
            )
            self._clean_text_formatting(canonical)
            canonical_points.append(canonical)

        return canonical_points
