"""Loader for the per-domain canonical reference sheet.

The reference sheet (a directory of per-component YAML + a manifest) is the controlled vocabulary that
the canonicalization layer uses three ways: injected into the extractor prompt (drive reuse), a
deterministic alias tier in the matcher (synonym -> canonical), and a `judge` that scores a case's
classes. Applies the manifest loader-contract (effective canonical = component canonical MINUS manifest
constraint_fold MINUS concepts[].drop_shadows; folded/dropped/do_not_mint labels redirect to a target).

Domain-aware: the sheet directory comes from the active DomainConfig, so a second domain is just a
different reference-sheet directory (no loader change). Dependency-light (yaml only) so both the live
extractor and the tooling/judge can import it.

Verdicts:
  reused           -- matches an effective-canonical label/iri, or an alt_label alias
  should_decompose -- matches a fold / drop_shadow / do_not_mint label (with a target)
  over_compound    -- not on the sheet and the label is compound (>=4 words or actor-laden)
  genuinely_new    -- not on the sheet, short/clean (candidate for the provisional queue)
"""
from __future__ import annotations
import os, re, glob, yaml
from dataclasses import dataclass, field

try:  # package member (live extractor) vs standalone file (tooling/judge)
    from .domain_config import active_domain
    from .core_vocab import COMPONENTS, CONCEPT_TYPE_TO_CORE_CATEGORY
except ImportError:  # pragma: no cover - tooling path
    from domain_config import active_domain
    from core_vocab import COMPONENTS, CONCEPT_TYPE_TO_CORE_CATEGORY

CLASS_COMPONENTS = ["roles", "principle", "obligation", "state",
                    "resource", "capability", "constraint"]
AE_COMPONENTS = ["action", "event"]

# sheet file stem -> core Category (the authoritative component for entries in that file)
_FILE_TO_CATEGORY = {
    "roles": "Role", "principle": "Principle", "obligation": "Obligation",
    "state": "State", "resource": "Resource", "capability": "Capability",
    "constraint": "Constraint", "action": "Action", "event": "Event",
}
# core Category -> file stem (inverse; for rendering a category's sheet block)
_CATEGORY_TO_FILE = {v: k for k, v in _FILE_TO_CATEGORY.items()}

_ACTOR = re.compile(r"\b[A-Z]\b")  # a lone capital (Engineer A), an actor tell


def _sheet_dir() -> str:
    # Explicit env override wins; else the active domain's configured dir.
    return os.environ.get("REFERENCE_SHEET_DIR") or active_domain().reference_sheet_dir


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def is_compound(label: str) -> bool:
    if not label:
        return False
    if len(label.split()) >= 4:
        return True
    return bool(_ACTOR.search(label)) or "'s" in label


@dataclass
class Verdict:
    label: str
    verdict: str
    target: str | None = None
    via: str | None = None


@dataclass
class ReferenceSheet:
    canonical: dict = field(default_factory=dict)   # norm -> (component, iri/label)
    aliases: dict = field(default_factory=dict)     # norm -> (iri, component)
    redirects: dict = field(default_factory=dict)   # norm -> (target, via, component)  [should_decompose]
    recipes: dict = field(default_factory=dict)     # norm -> the full do_not_mint decompose dict (role/state/obligation)
    display: dict = field(default_factory=dict)     # norm -> original human label (for prompt rendering)
    global_rules: list = field(default_factory=list)  # cross-component hygiene rules {id, rule, scope}
    sheet_dir: str = ""

    @classmethod
    def load(cls, sheet_dir: str | None = None) -> "ReferenceSheet":
        sheet_dir = sheet_dir or _sheet_dir()
        rs = cls(sheet_dir=sheet_dir)
        files = {os.path.basename(f)[:-5]: yaml.safe_load(open(f)) or {}
                 for f in glob.glob(os.path.join(sheet_dir, "*.yaml"))}
        if not files:
            raise FileNotFoundError(f"No reference-sheet YAML found in {sheet_dir!r}")
        manifest = files.get("manifest", {})
        rs.global_rules = [r for r in (manifest.get("global_rules") or []) if isinstance(r, dict) and r.get("rule")]

        suppressed = set()
        for fold in (manifest.get("constraint_fold") or []):
            lab = norm(fold.get("label"))
            if lab:
                rs.redirects[lab] = (fold.get("into"), "fold", "Constraint")
                rs.display.setdefault(lab, fold.get("label"))
                suppressed.add(lab)
        for con in (manifest.get("concepts") or []):
            for ds in (con.get("drop_shadows") or []):
                if not isinstance(ds, dict):
                    continue
                act = str(ds.get("action") or "")
                lab = norm(ds.get("label"))
                if not lab or act.upper().startswith("KEEP"):
                    continue
                tgt = ds.get("fold_into") or ds.get("into")
                rs.redirects[lab] = (tgt, "drop_shadow", _FILE_TO_CATEGORY.get(ds.get("component")))
                rs.display.setdefault(lab, ds.get("label"))
                suppressed.add(lab)

        for comp in CLASS_COMPONENTS + AE_COMPONENTS:
            d = files.get(comp, {})
            # canonical_parents: the reusable parent classes already in proethica-intermediate
            # (e.g. EngineerRole, RiskState). The role+facet materializer retypes individuals to
            # these and the LLM legitimately reuses them, so they count as reuse, not a new mint.
            # They are bare local-names; a fuller `canonical` entry for the same name wins (read after).
            for parent in (d.get("canonical_parents") or []):
                nk = norm(parent) if isinstance(parent, str) else None
                if nk and nk not in suppressed and nk not in rs.canonical:
                    rs.canonical[nk] = (comp, parent)
                    rs.display.setdefault(nk, parent)
            for sect in ("canonical", "canonical_types"):
                for e in (d.get(sect) or []):
                    if not isinstance(e, dict):
                        continue
                    iri = e.get("iri") or e.get("label")
                    label = e.get("label") or e.get("iri")
                    for key in (e.get("iri"), e.get("label")):
                        nk = norm(key)
                        if nk and nk not in suppressed:
                            rs.canonical[nk] = (comp, iri)
                            rs.display[nk] = label
                    for a in (e.get("alt_labels") or []):
                        na = norm(a)
                        if na and na not in rs.canonical:
                            rs.aliases[na] = (iri, _FILE_TO_CATEGORY.get(comp))
                            rs.display.setdefault(na, a)
            for e in (d.get("do_not_mint") or []):
                if not isinstance(e, dict):
                    continue
                lab = norm(e.get("label"))
                if not lab:
                    continue
                dec = e.get("decompose") or {}
                tgt = dec.get("role") or dec.get("obligation") or dec.get("state") or dec.get("note") \
                    or (dec if isinstance(dec, str) else None)
                if isinstance(tgt, dict):
                    tgt = tgt.get("iri") or str(tgt)
                rs.redirects.setdefault(lab, (tgt, "do_not_mint", _FILE_TO_CATEGORY.get(comp)))
                rs.display.setdefault(lab, e.get("label"))
                if isinstance(dec, dict) and dec:
                    rs.recipes.setdefault(lab, {"_component": _FILE_TO_CATEGORY.get(comp), **dec})
        return rs

    def recipe_for(self, label: str) -> dict | None:
        """The full do_not_mint decompose recipe for a compound label (role/state/obligation), or None."""
        return self.recipes.get(norm(label))

    def resolve(self, label: str) -> Verdict:
        n = norm(label)
        if n in self.redirects:
            tgt, via = self.redirects[n][0], self.redirects[n][1]
            return Verdict(label, "should_decompose", target=tgt, via=via)
        if n in self.canonical:
            comp, iri = self.canonical[n]
            return Verdict(label, "reused", target=iri, via="canonical")
        if n in self.aliases:
            iri, _comp = self.aliases[n]
            return Verdict(label, "reused", target=iri, via="alias")
        if is_compound(label):
            return Verdict(label, "over_compound")
        return Verdict(label, "genuinely_new")

    def alias_targets(self) -> dict:
        """{normalized label -> (canonical_full_iri, canonical_label, component)} for the matcher alias tier.

        SAME-CATEGORY reuse only: alt_labels (synonyms of a canonical class) and do_not_mint redirects
        whose target is a single canonical class local-name in the SAME component. Cross-category folds
        (e.g. a Constraint folding into an Obligation) are EXCLUDED -- those are decompositions handled by
        the prompt + State materializer, not matcher reuse. `component` is the sheet's authoritative
        category for the canonical, so the matcher does not have to infer it from the IRI or require the
        class to exist in the ontology yet. Bare local-names resolve to the active domain's intermediate
        namespace via the seam, so a second domain mints under its own namespace.
        """
        cfg = active_domain()

        def full(x):
            if not x or not isinstance(x, str):
                return None
            if "#" in x or "://" in x:
                return x
            return cfg.intermediate(x)

        out: dict = {}
        for n, (iri, comp) in self.aliases.items():
            f = full(iri)
            if f:
                out[n] = (f, iri, comp)
        for n, (tgt, via, comp) in self.redirects.items():
            # only same-component do_not_mint reuse; skip cross-category fold/drop decomposes
            if n in out or via != "do_not_mint" or not isinstance(tgt, str):
                continue
            if " " not in tgt and tgt[:1].isupper() and tgt.isidentifier():
                f = full(tgt)
                if f:
                    out[n] = (f, tgt, comp)
        return out

    def build_alias_resolver(self):
        """callable(label) -> (canonical_iri, canonical_label, component) | None, for EntityMatcher.
        Memoized on the (cached) sheet instance so per-candidate construction stays cheap."""
        table = getattr(self, "_alias_table", None)
        if table is None:
            table = self._alias_table = self.alias_targets()
        def resolve(label: str):
            return table.get(norm(label))
        return resolve

    def _global_rules_for(self, category: str) -> list:
        """Global hygiene rules (from manifest global_rules) that apply to this category.
        scope is 'all' or a list of core Categories. Returns whitespace-normalized rule strings."""
        out = []
        for r in self.global_rules:
            scope = r.get("scope", "all")
            if scope == "all" or (isinstance(scope, (list, tuple)) and category in scope):
                txt = " ".join(str(r.get("rule", "")).split())
                if txt:
                    out.append(txt)
        return out

    def prompt_block(self, category: str) -> str:
        """Reuse-bias guidance for one core Category (Role/State/...), rendered from the sheet:
        the canonical classes to reuse, synonyms that fold into them, and compound anti-patterns to
        avoid (including the cross-component manifest folds). Returns '' when the sheet has nothing
        for the category. Memoized per (cached) instance so per-prompt construction stays cheap."""
        cache = getattr(self, "_block_cache", None)
        if cache is None:
            cache = self._block_cache = {}
        if category in cache:
            return cache[category]

        canon = sorted(
            {self.display.get(n, iri)
             for n, (comp, iri) in self.canonical.items()
             if _FILE_TO_CATEGORY.get(comp) == category},
            key=str.lower,
        )
        synonyms = sorted(
            ((self.display.get(n, n), tgt) for n, (tgt, comp) in self.aliases.items()
             if comp == category and tgt),
            key=lambda p: str(p[0]).lower(),
        )
        antipatterns = sorted(
            ((self.display.get(n, n), tgt) for n, (tgt, via, comp) in self.redirects.items()
             if comp == category and tgt),
            key=lambda p: str(p[0]).lower(),
        )
        if not (canon or synonyms or antipatterns):
            cache[category] = ""
            return ""

        cat_l = category.lower()
        lines = [
            f"=== REUSE THESE CANONICAL {category.upper()} CLASSES (do not mint compound variants) ===",
            f"When a {cat_l} matches one of these, reuse the exact canonical label.",
        ]
        # Global cross-component hygiene rules (declared once in the sheet manifest's global_rules;
        # NOT hardcoded here, so a second domain swaps them with its sheet). Soft at the prompt layer;
        # the deterministic enforcement point is the commit-time normalizer + SHACL.
        grules = self._global_rules_for(category)
        if grules:
            lines.append("Rules for every class you mint:")
            lines += [f"- {r}" for r in grules]
        if canon:
            lines.append("Canonical classes: " + "; ".join(canon))
        if synonyms:
            lines.append("")
            lines.append("Synonyms (fold into a canonical class above -- reuse it, do not mint a new class):")
            lines += [f"- {label} -> {tgt}" for label, tgt in synonyms]
        if antipatterns:
            lines.append("")
            lines.append("Do NOT mint these compound patterns (reuse the target instead):")
            lines += [f"- {label} -> {tgt}" for label, tgt in antipatterns]
        block = "\n".join(lines)
        cache[category] = block
        return block

    def stats(self) -> dict:
        return {"canonical": len(self.canonical), "aliases": len(self.aliases),
                "redirects": len(self.redirects), "alias_targets": len(self.alias_targets()),
                "sheet_dir": self.sheet_dir}


_CACHE: dict = {}


def get_sheet(sheet_dir: str | None = None) -> "ReferenceSheet":
    """Cached ReferenceSheet for the active (or given) domain's sheet dir."""
    d = sheet_dir or _sheet_dir()
    if d not in _CACHE:
        _CACHE[d] = ReferenceSheet.load(d)
    return _CACHE[d]


def reuse_block_for_concept(concept_type: str, sheet_dir: str | None = None) -> str:
    """Reuse-bias prompt block for a plural extraction concept_type (roles/states/obligations/...),
    rendered from the active (or given) domain's reference sheet. Returns '' when the concept_type
    maps to no sheet component. Injected into the extractor prompt by format_existing_entities so the
    model reuses canonical classes instead of minting context-laden compound classes."""
    category = CONCEPT_TYPE_TO_CORE_CATEGORY.get((concept_type or "").strip().lower())
    if not category:
        return ""
    return get_sheet(sheet_dir).prompt_block(category)


if __name__ == "__main__":
    rs = ReferenceSheet.load()
    print("loaded reference sheet:", rs.stats())
    for probe in ["AI Tool Reliant Engineer", "Environmental Engineer",
                  "AI Tool Disclosure Constraint", "Municipal Engineer",
                  "Dual Capacity Engineer", "Some Brand New Concept"]:
        v = rs.resolve(probe)
        print(f"  {probe:34} -> {v.verdict:16} via={v.via}  target={v.target}")
