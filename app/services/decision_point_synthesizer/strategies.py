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

from .models import (
    ToulminStructure,
    QCAlignmentScore,
    CanonicalDecisionPoint,
    Phase3SynthesisResult,
    SynthesisTrace,
)

logger = logging.getLogger(__name__)


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
                            max_tokens=16000,
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
            questions_text.append(f"Q{i+1}: {q.get('question_text', q.get('text', ''))[:200]}")

        # Format conclusions
        conclusions_text = []
        for i, c in enumerate(conclusions[:10]):  # Limit to 10
            conclusions_text.append(f"C{i+1}: {c.get('conclusion_text', c.get('text', ''))[:200]}")

        prompt = f"""You are analyzing an ethics case to identify key decision points where ethical choices must be made.

The E1-E3 algorithmic composition found no decision point candidates. However, the case analysis has identified
the following CAUSAL-NORMATIVE LINKS (relationships between actions and obligations):

{chr(10).join(causal_links_text)}

ETHICAL QUESTIONS identified in the case:
{chr(10).join(questions_text)}

BOARD CONCLUSIONS:
{chr(10).join(conclusions_text)}

Based on these causal links, generate 3-5 canonical decision points. Each decision point should represent
a moment where an agent must choose between actions with ethical implications.

For each decision point, provide:
1. A focus_id (e.g., "DP1", "DP2")
2. A description of the decision situation
3. A decision_question (what choice must be made?)
4. The primary role/agent facing the decision
5. The relevant obligation or constraint
6. 2-3 options available to the decision-maker, with one marked as the Board's choice
7. Which question(s) this addresses (reference Q numbers)
8. How the board resolved it (reference C numbers)
9. Toulmin argument structure: data_summary (triggering facts), warrants_summary (competing obligations or duties at stake), rebuttals_summary (sources of uncertainty or counter-considerations)
10. NSPE Code provisions cited as backing (provision_labels, e.g. ["II.1.f", "I.1"]). Entries MUST be NSPE code section citations; do NOT put duty or principle names here.
11. intensity_score (float 0.0-1.0): moral intensity of this decision (urgency, magnitude of consequences, proximity)
12. qc_alignment_score (float 0.0-1.0): strength of alignment between this decision and the Questions/Conclusions

CRITICAL FORMATTING:
- Do NOT use em dash characters anywhere in your output. Use commas or periods instead.
- role_label must be a SHORT identifier for the decision-maker (e.g., "Engineer A", "Firm C", "Engineers A and B").
  Do NOT append obligation names, case descriptions, or topic keywords to the role_label.
  BAD: "Engineer A Construction Observation Engineer" or "Engineer H Public Hearing Testimony Completeness"
  GOOD: "Engineer A" or "Engineer H"
- decision_question should be concise (1-2 sentences). Frame as "Should [role] [action]?" or "Must [role] [choice]?"
- Option labels must be short action phrases (3-8 words), NEVER "Option A", "Option B", "Option C".
- Good labels: "Disclose AI Tool Usage", "Verify Code with Expert", "Withdraw from Project"
- Bad labels: "Option A", "Option B", "Alternative Approach"
- Descriptions expand on the label with case-specific detail.
- Exactly one option per decision point must have is_board_choice=true; the rest is_board_choice=false.

GROUNDING RULES (2026-07-08 Phase-B audit; each was a judged failure mode):
- is_board_choice marks the course the Board held to be the ETHICAL one. When the Board
  found the party's actual conduct unethical, the board choice is the compliant
  alternative (e.g. "Obtain Client Consent"), NOT the conduct that occurred. Never mark
  condemned conduct as the Board's choice.
- Options must be alternatives the case states or clearly implies were available to the
  decision-maker at that moment. Do NOT invent options the case never mentions or
  contemplates, and do not split one course of action into two near-identical options.
- board_resolution must paraphrase only what the Board's conclusions state. Do not add
  interpretive elaborations, carve-outs, or rationales the conclusions do not contain.
- rebuttals_summary must never be empty: state the strongest opposing consideration the
  case itself supplies (the losing party's position, the dissent, or the constraint that
  pulled the other way).

Return as JSON array:
```json
[
  {{
    "focus_id": "DP1",
    "description": "...",
    "decision_question": "...",
    "role_label": "...",
    "obligation_label": "...",
    "options": [
      {{"option_id": "O1", "label": "Disclose X to Stakeholders", "description": "Formally notify all affected stakeholders of X through written communication", "is_board_choice": true}},
      {{"option_id": "O2", "label": "Withhold Disclosure of X", "description": "Continue without disclosure, relying on existing contractual scope limitations", "is_board_choice": false}}
    ],
    "addresses_questions": ["Q1", "Q2"],
    "board_resolution": "The board concluded that... (C1)",
    "toulmin_data": "Summary of triggering facts (1-2 sentences)",
    "toulmin_warrants": "Summary of the obligations or duties that justify the Board's chosen option (1-2 sentences, cite Code provisions inline)",
    "toulmin_rebuttals": "Summary of what creates uncertainty or supports an alternative (1-2 sentences)",
    "provision_labels": ["II.1.f", "I.1"],
    "intensity_score": 0.78,
    "qc_alignment_score": 0.82
  }}
]
```
"""

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
                max_tokens=16000,
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
                        aligned_q_text = q.get('question_text', q.get('text', ''))
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
                data_summary=dp_data.get('toulmin_data', ''),
                warrants_summary=dp_data.get('toulmin_warrants', ''),
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
                board_resolution=dp_data.get('board_resolution', ''),
                addresses_questions=[q_uri_map.get(q, q) for q in (addresses if isinstance(addresses, list) else [addresses])],
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

        prompt = f"""You are analyzing an ethics case to identify key decision points where ethical choices must be made.

The algorithmic composition and causal link analysis found no decision point candidates for this case.
However, the case has rich analytical data. Synthesize decision points from the following context.

ETHICAL QUESTIONS identified in the case:
{chr(10).join(questions_text)}

BOARD CONCLUSIONS:
{chr(10).join(conclusions_text)}

QUESTION EMERGENCE (how ethical questions arise from case facts):
{chr(10).join(qe_text)}

RESOLUTION PATTERNS (how the board resolved questions):
{chr(10).join(rp_text)}

OBLIGATIONS extracted from the case:
{chr(10).join(obl_text)}

ROLES in the case:
{chr(10).join(role_text)}

Based on this analysis, generate 3-5 canonical decision points. Each should represent
a moment where an agent must choose between actions with ethical implications.

For each decision point, provide:
1. A focus_id (e.g., "DP1", "DP2")
2. A description of the decision situation
3. A decision_question -- an actionable choice framed as "Should [role] do X or Y?"
4. The primary role/agent facing the decision (use exact role labels from above)
5. The relevant obligation (use exact obligation labels from above)
6. 2-3 options that DIRECTLY ANSWER the decision_question, with one marked as the Board's choice
7. Which question(s) this addresses (reference Q numbers)
8. How the board resolved it (reference C numbers)
9. Toulmin argument structure: data_summary (triggering facts), warrants_summary (competing obligations or duties at stake), rebuttals_summary (sources of uncertainty or counter-considerations)
10. NSPE Code provisions cited as backing (provision_labels, e.g. ["II.1.f", "I.1"]). Entries MUST be NSPE code section citations; do NOT put duty or principle names here.
11. intensity_score (float 0.0-1.0): moral intensity of this decision (urgency, magnitude of consequences, proximity)
12. qc_alignment_score (float 0.0-1.0): strength of alignment between this decision and the Questions/Conclusions

CRITICAL FORMATTING:
- Do NOT use em dash characters anywhere in your output. Use commas or periods instead.
- role_label must be a SHORT identifier (e.g., "Engineer A", "Firm C"). Do NOT append topic descriptions.
  BAD: "Engineer D Bid Document Material Information Inclusion" GOOD: "Engineer D"

CRITICAL COHERENCE: The decision_question and options must form a coherent decision:
- The question must present an actionable choice the named role faces.
  BAD: "Whether the obligation arose at point X" (analytical, not a choice)
  GOOD: "Should Engineer Doe submit full findings or limit disclosure to correcting false data?"
- Each option must be a direct answer to that question. Reading the question then the option,
  the option must be a plausible course of action the role could choose.
- The role_label must be the agent making the decision, not a passive party.
- is_board_choice marks the course the Board held ETHICAL; when the Board condemned the
  actual conduct, the board choice is the compliant alternative, never the condemned act.
- Options must be alternatives the case states or implies; do not invent unmentioned ones.
- board_resolution paraphrases only what the conclusions state; rebuttals_summary is
  never empty (use the strongest case-supplied opposing consideration).

CRITICAL OPTION FORMAT:
- Labels must be 3-8 words, Title Case, starting with a verb. NEVER "Option A", "Option B".
- Good labels: "Disclose Conflict to Client", "Recuse from Project", "Seek Independent Review"
- Descriptions expand on the label with 1-2 sentences of case-specific detail.
- Options must represent genuinely defensible positions, not straw-man alternatives.
- Exactly one option per decision point must have is_board_choice=true; the rest is_board_choice=false.

Return as JSON array:
```json
[
  {{
    "focus_id": "DP1",
    "description": "...",
    "decision_question": "...",
    "role_label": "...",
    "obligation_label": "...",
    "options": [
      {{"option_id": "O1", "label": "Disclose Conflict to Client", "description": "Formally notify the client of the conflict of interest and recommend independent oversight", "is_board_choice": true}},
      {{"option_id": "O2", "label": "Recuse from Project", "description": "Withdraw from the project entirely to avoid any appearance of compromised judgment", "is_board_choice": false}}
    ],
    "addresses_questions": ["Q1", "Q2"],
    "board_resolution": "The board concluded that... (C1)",
    "toulmin_data": "Summary of triggering facts (1-2 sentences)",
    "toulmin_warrants": "Summary of the obligations or duties that justify the Board's chosen option (1-2 sentences, cite Code provisions inline)",
    "toulmin_rebuttals": "Summary of what creates uncertainty or supports an alternative (1-2 sentences)",
    "provision_labels": ["II.1.f", "I.1"],
    "intensity_score": 0.78,
    "qc_alignment_score": 0.82
  }}
]
```
"""

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
                max_tokens=16000,
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


        # Format questions with Toulmin analysis
        qe_map = {qe.get('question_uri', ''): qe for qe in question_emergence}
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

        # Format conclusions with resolution patterns
        rp_map = {rp.get('conclusion_uri', ''): rp for rp in resolution_patterns}
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

        _refinement_prompt = f"""You are synthesizing decision points for NSPE ethics case {case_id}.

## TOP ALGORITHMIC CANDIDATES (Scored by Q&C Alignment)

These candidates were composed algorithmically from extracted entities and scored against the board's actual questions and conclusions:

{''.join(candidates_text)}

## BOARD'S QUESTIONS (with Toulmin Analysis)

These are the actual ethical questions with their Toulmin structure:

{''.join(questions_text)}

## BOARD'S CONCLUSIONS (with Resolution Patterns)

{''.join(conclusions_text)}

## TASK

Synthesize {target_count} decision points that:

1. **Preserve entity grounding** - Keep URI references from candidates
2. **Align with Q&C** - Each point should address real board concerns
3. **Merge similar candidates** - Combine candidates addressing the same issue
4. **Include Toulmin structure** - Show DATA, WARRANTs, and REBUTTAL for each
5. **Coherent question-option structure** - Options must directly answer the question

CRITICAL FORMATTING REQUIREMENT:

- Do NOT use em dash characters anywhere in your output. Use commas or periods instead.

CRITICAL ROLE LABEL REQUIREMENT:

- The role_label must be a SHORT identifier for the decision-maker: "Engineer A", "Firm C",
  "Engineers A and B", "Client", etc. Do NOT append obligation names, case descriptions,
  or topic keywords to the role_label.
  - BAD: "Engineer A Construction Observation Engineer", "Engineer H Public Hearing Testimony Completeness ZZZ Truck Stop"
  - GOOD: "Engineer A", "Engineer H"
- The role_label must be the agent who faces the decision. Do not assign a decision to a party
  who is not making the choice (e.g., do not assign a disclosure decision to the "Client"
  when it is the engineer who must decide whether to disclose).

CRITICAL COHERENCE REQUIREMENT:

The decision_question, description, and options must form a coherent decision structure:

1. The "decision_question" must be framed as an actionable choice the named role faces:
   - Format: "Should [role] [action A] or [action B]?" or "Must [role] [choice]?"
   - The question must present the core tension between competing courses of action.
   - Keep it to 1-2 sentences. Do not embed long subordinate clauses.
   - BAD: "Whether the obligation arose at point X or point Y" (analytical, not actionable)
   - BAD: "The interaction between principle X and principle Y" (abstract, no agent choosing)
   - GOOD: "Should Engineer A disclose the conflict to the client before accepting the project, or rely on internal firewalls?"

2. Each option must be a DIRECT ANSWER to the decision_question. If you read the question
   then read each option, the option must be a plausible response the named role could choose.
   - BAD: Question asks "when did the obligation arise?" but options are "Submit Report" / "Limit Disclosure"
   - GOOD: Question asks "Should Doe submit full findings or limit disclosure?" and options are
     "Submit Full Report" / "Limit Disclosure to Correcting False Data" / "Seek Ethics Guidance First"

CRITICAL OPTION REQUIREMENTS:

1. Each option MUST have a short "label" (3-8 words, Title Case, action phrase starting with a verb)
   and a longer "description" (1-2 sentences elaborating the action).
   The label is a DISCRETE CHOICE that a decision-maker selects from a list.
   - Good labels: "Disclose Conflict to Client", "Recuse from Evaluation", "Report to State Agency"
   - Bad labels: "Option A", "Proactively disclose AI tool usage and identify AI-generated sections to client before submission"
   The label must be distinct enough to distinguish options at a glance.

2. Each decision point MUST have 2-3 options that represent GENUINELY DEFENSIBLE positions.
   Do NOT create straw-man alternatives. Each option should be an action a reasonable
   professional could plausibly choose given competing pressures (time, cost, client
   relationship, scope of duty, professional judgment).

   - BAD (straw-man negation):
     O1: "Conduct rigorous line-by-line review before sealing"
     O2: "Seal without any verification"
   - GOOD (genuine tension):
     O1: "Conduct full independent technical review of all AI outputs before sealing"
     O2: "Apply standard firm QA protocols to AI outputs at the same level as conventional CAD software"
     O3: "Engage a third-party reviewer with AI expertise for safety-critical elements while applying standard review to remaining outputs"

   The non-board-choice options must represent positions with real justifications
   (efficiency, precedent, scope limitation, competing obligations) -- not simply
   omitting or refusing to perform the ethical action.

## OUTPUT FORMAT (JSON)

```json
[
  {{
    "focus_id": "DP1",
    "source_candidate_ids": ["DP1", "DP3"],
    "description": "Clear description",
    "decision_question": "The key ethical question",
    "role_label": "Engineer A",
    "role_uri": "URI from candidate",
    "obligation_label": "From candidate",
    "obligation_uri": "URI",
    "constraint_label": null,
    "constraint_uri": null,
    "provision_labels": ["II.1.c"],
    "provision_uris": ["URIs"],
    "involved_action_uris": ["action URIs"],
    "toulmin_data": "Summary of triggering facts",
    "toulmin_warrants": "Summary of competing obligations",
    "toulmin_rebuttals": "What creates uncertainty",
    "addresses_questions": ["Q0", "Q1"],
    "board_resolution": "How board resolved this",
    "qc_alignment_score": 0.85,
    "intensity_score": 0.7,
    "options": [
      {{"option_id": "O1", "label": "Disclose AI Usage to Client Before Submission", "description": "Proactively disclose AI tool usage and identify AI-generated sections to client before submission", "action_uri": "URI", "is_board_choice": true}},
      {{"option_id": "O2", "label": "Treat AI as Internal Drafting Tool", "description": "Treat AI tool as internal drafting software equivalent to CAD, disclosing only upon direct client inquiry", "action_uri": "URI", "is_board_choice": false}},
      {{"option_id": "O3", "label": "Disclose in Project Documentation Only", "description": "Disclose AI usage in project documentation without separate client notification, following existing firm software disclosure policy", "action_uri": "URI", "is_board_choice": false}}
    ]
  }}
]
```

Produce exactly {target_count} decision points capturing the key ethical issues. Do NOT produce more than the requested count.
"""
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
                data_summary=data.get('toulmin_data', ''),
                warrants_summary=data.get('toulmin_warrants', ''),
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
                involved_action_uris=data.get('involved_action_uris', []),
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
                synthesis_method='algorithmic+llm',
                llm_refined_description=data.get('description'),
                llm_refined_question=data.get('decision_question')
            )
            self._clean_text_formatting(canonical)
            canonical_points.append(canonical)

        return canonical_points
