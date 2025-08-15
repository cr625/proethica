from __future__ import annotations

from typing import List, Optional, Set, Any, Dict
import os
import re
from slugify import slugify

from .base import ConceptCandidate, MatchedConcept, SemanticTriple, Extractor, Linker
from .policy_gatekeeper import RelationshipPolicyGatekeeper
from config.models import ModelConfig
try:
    from app.utils.llm_utils import get_llm_client
except Exception:
    get_llm_client = None  # type: ignore


class PrinciplesExtractor(Extractor):
    """Lightweight heuristic extractor for principles.

    This is a placeholder baseline; replace with provider-backed extraction later.
    """

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = (provider or 'auto').lower()

    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        if not text:
            return []

        # Provider-backed attempt first if configured
        if self.provider != 'heuristic' and get_llm_client is not None:
            try:
                items = self._extract_with_llm(text)
                if items:
                    return [
                        ConceptCandidate(
                            label=i.get('label') or i.get('principle') or i.get('name') or '',
                            description=i.get('description') or i.get('explanation') or None,
                            primary_type='principle',
                            category='principle',
                            confidence=float(i.get('confidence', 0.65)) if isinstance(i.get('confidence', 0.65), (int, float, str)) else 0.65,
                            debug={'source': 'provider', 'provider': self.provider}
                        )
                        for i in items
                        if (i.get('label') or i.get('principle') or i.get('name'))
                    ]
            except Exception:
                pass
        sentences = re.split(r"(?<=[\.!?])\s+", text.strip())
        # Common principle keywords in engineering ethics contexts
        kw = re.compile(r"\b(safety|welfare|integrity|honesty|objectivity|fairness|competence|confidentiality|public\s+welfare|responsibility)\b", re.IGNORECASE)
        seen: Set[str] = set()
        out: List[ConceptCandidate] = []
        for s in sentences:
            if not s:
                continue
            if kw.search(s):
                label = s.strip()
                key = label.lower()
                if key in seen:
                    continue
                seen.add(key)
                display = label if len(label) <= 120 else label[:117] + '…'
                out.append(ConceptCandidate(
                    label=display,
                    description=label if display != label else None,
                    primary_type='principle',
                    category='principle',
                    confidence=0.45,
                    debug={'source': 'heuristic_keywords', 'guideline_id': guideline_id}
                ))
        return out

    # ---- Provider-backed helpers ----
    def _extract_with_llm(self, text: str) -> List[Dict[str, Any]]:
        client = get_llm_client() if get_llm_client else None
        if client is None:
            return []

        prompt = (
            "You are an ontology-aware extractor. From the guideline excerpt, list distinct ethical principles.\n"
            "Return STRICT JSON with an array under key 'principles'. Each item: {label, description, confidence}.\n"
            "Guideline excerpt:\n" + text
        )

        # Gemini
        try:
            if hasattr(client, 'GenerativeModel'):
                model_name = os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')
                model = client.GenerativeModel(model_name)
                resp = model.generate_content(prompt)
                output = getattr(resp, 'text', None) or (resp.candidates[0].content.parts[0].text if getattr(resp, 'candidates', None) else '')
                return self._parse_json_items(output, root_key='principles')
        except Exception:
            pass

        # Anthropic
        try:
            if hasattr(client, 'messages') and hasattr(client.messages, 'create'):
                model = ModelConfig.get_default_model()
                resp = client.messages.create(
                    model=model,
                    max_tokens=800,
                    temperature=0,
                    system=(
                        "Extract ethical principles from text and output ONLY JSON with key 'principles'."
                    ),
                    messages=[{"role": "user", "content": prompt}],
                )
                content = getattr(resp, 'content', None)
                if content and isinstance(content, list) and len(content) > 0:
                    text_out = getattr(content[0], 'text', None) or str(content[0])
                else:
                    text_out = getattr(resp, 'text', None) or str(resp)
                return self._parse_json_items(text_out, root_key='principles')
        except Exception:
            pass

        # OpenAI
        try:
            if hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
                model = os.getenv('OPENAI_CHAT_MODEL', 'gpt-4o-mini')
                resp = client.chat.completions.create(
                    model=model,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                )
                text_out = resp.choices[0].message.content if getattr(resp, 'choices', None) else ''
                return self._parse_json_items(text_out, root_key='principles')
        except Exception:
            pass

        return []

    @staticmethod
    def _parse_json_items(raw: Optional[str], root_key: str) -> List[Dict[str, Any]]:
        if not raw:
            return []
        import json, re as _re
        s = raw.strip()
        if s.startswith('```'):
            s = _re.sub(r"^```[a-zA-Z0-9]*\n|\n```$", "", s)
        try:
            if s.strip().startswith('['):
                arr = json.loads(s)
                return arr if isinstance(arr, list) else []
        except Exception:
            pass
        try:
            obj = json.loads(s)
            val = obj.get(root_key)
            if isinstance(val, list):
                return val
        except Exception:
            try:
                m = _re.search(r"\[(?:.|\n)*\]", s)
                if m:
                    return json.loads(m.group(0))
            except Exception:
                return []
        return []


class SimplePrincipleMatcher:
    """Assigns stable derived URIs for principles when unmatched.

    URI scheme: urn:proethica:principle:<slug>
    """

    def match(self, candidates: List[ConceptCandidate], *, world_id: Optional[int] = None) -> List[MatchedConcept]:
        results: List[MatchedConcept] = []
        for c in candidates:
            slug = slugify(c.label or 'principle')
            uri = f"urn:proethica:principle:{slug}"
            results.append(MatchedConcept(
                candidate=c,
                ontology_match={'uri': uri, 'label': c.label, 'score': 0.45},
                similarity=0.45,
                normalized_label=c.label,
                notes='derived: simple matcher'
            ))
        return results


class PrinciplesLinker(Linker):
    """Generates Role→adheresToPrinciple→Principle links with policy gating."""

    def __init__(self, gatekeeper: Optional[RelationshipPolicyGatekeeper] = None) -> None:
        self.gate = gatekeeper or RelationshipPolicyGatekeeper()

    def link(self, matches: List[MatchedConcept], *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[SemanticTriple]:
        triples: List[SemanticTriple] = []
        roles = [m for m in matches if (m.candidate.primary_type or '').lower() in {'role', 'professionalrole', 'participantrole'}]
        principles = [m for m in matches if (m.candidate.primary_type or '').lower() == 'principle']

        for role in roles:
            subj_uri = (role.ontology_match or {}).get('uri')
            subj_type = (role.candidate.primary_type or '')
            if not subj_uri:
                continue
            for pr in principles:
                obj_uri = (pr.ontology_match or {}).get('uri')
                if not obj_uri:
                    continue
                obj_type = (pr.candidate.primary_type or '')
                if not self.gate.can_link_adheres_to_principle(subj_type, obj_type):
                    continue
                triples.append(
                    SemanticTriple(
                        subject_uri=subj_uri,
                        predicate_uri='adheresToPrinciple',
                        object_uri=obj_uri,
                        context={'guideline_id': guideline_id} if guideline_id else {},
                        is_approved=False,
                    )
                )
        return triples
