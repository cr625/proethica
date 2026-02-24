#!/usr/bin/env python3
"""
Quick post-extraction verification for a case.

Usage:
    python scripts/verify_case_quick.py <case_id>
    python scripts/verify_case_quick.py 7 8    # verify multiple cases

Checks:
  1. All 16 extraction types present with counts
  2. Published count matches total (all committed)
  3. Class context injection (HAS_CONTEXT for non-first cases)
  4. Extended TTL class count and discoveredInCase references
  5. OntServe DB registration
  6. Model consistency (claude-sonnet-4-6 only)
"""

import os
import subprocess
import sys

DB_ENV = {"PGPASSWORD": "PASS", "PATH": "/usr/bin:/bin"}
EXTENDED_TTL = "/home/chris/onto/OntServe/ontologies/proethica-intermediate-extended.ttl"

EXPECTED_TYPES = [
    "canonical_decision_point", "capabilities", "causal_normative_link",
    "code_provision_reference", "constraints", "ethical_conclusion",
    "ethical_question", "obligations", "precedent_case_reference",
    "principles", "question_emergence", "resolution_pattern",
    "resources", "roles", "states", "temporal_dynamics_enhanced",
]


def psql(query, db="ai_ethical_dm"):
    result = subprocess.run(
        ["psql", "-h", "localhost", "-U", "postgres", "-d", db, "-t", "-A", "-c", query],
        capture_output=True, text=True, env=DB_ENV,
    )
    return result.stdout.strip()


def verify_case(case_id):
    issues = []
    print(f"\n{'=' * 50}")
    print(f"Case {case_id} Verification")
    print(f"{'=' * 50}")

    # 1. Entity counts by type
    rows = psql(
        f"SELECT extraction_type, COUNT(*) FROM temporary_rdf_storage "
        f"WHERE case_id = {case_id} GROUP BY extraction_type ORDER BY extraction_type;"
    )
    type_counts = {}
    total = 0
    if rows:
        for line in rows.split("\n"):
            parts = line.split("|")
            if len(parts) == 2:
                etype, count = parts[0], int(parts[1])
                type_counts[etype] = count
                total += count

    print(f"\nEntity counts ({total} total):")
    for etype in EXPECTED_TYPES:
        count = type_counts.get(etype, 0)
        status = "OK" if count > 0 else "MISSING"
        if status == "MISSING":
            issues.append(f"CRITICAL: Missing extraction type: {etype}")
        print(f"  {etype:40s} {count:4d}  {status}")

    extra = set(type_counts.keys()) - set(EXPECTED_TYPES)
    if extra:
        for e in sorted(extra):
            print(f"  {e:40s} {type_counts[e]:4d}  (extra)")

    # 2. Published count
    pub_row = psql(
        f"SELECT COUNT(*), SUM(CASE WHEN is_published THEN 1 ELSE 0 END) "
        f"FROM temporary_rdf_storage WHERE case_id = {case_id};"
    )
    if pub_row:
        parts = pub_row.split("|")
        total_count, published = int(parts[0]), int(parts[1])
        pub_status = "PASS" if total_count == published else "FAIL"
        if pub_status == "FAIL":
            issues.append(f"WARNING: {total_count} total but only {published} published")
        print(f"\nPublished: {published}/{total_count} {pub_status}")

    # 3. Class context injection
    context_rows = psql(
        f"SELECT concept_type || '|' || section_type || '|' || "
        f"CASE WHEN prompt_text LIKE '%PREVIOUSLY EXTRACTED CLASSES%' THEN 'HAS_CONTEXT' "
        f"     WHEN prompt_text LIKE '%previously extracted%' THEN 'HAS_CONTEXT' "
        f"     ELSE 'NO_CONTEXT' END "
        f"FROM extraction_prompts WHERE case_id = {case_id} AND step_number IN (1, 2) "
        f"ORDER BY concept_type, section_type;"
    )
    if context_rows:
        has_context = context_rows.count("HAS_CONTEXT")
        no_context = context_rows.count("NO_CONTEXT")
        total_prompts = has_context + no_context
        if has_context == total_prompts:
            print(f"Context injection: HAS_CONTEXT on all {total_prompts} prompts")
        elif no_context == total_prompts:
            print(f"Context injection: NO_CONTEXT on all {total_prompts} prompts (first case in batch?)")
        else:
            print(f"Context injection: {has_context} HAS_CONTEXT, {no_context} NO_CONTEXT")
            issues.append(f"WARNING: Mixed context injection ({no_context} prompts missing context)")

    # 4. Extended TTL
    ttl_classes = 0
    discovered = 0
    if os.path.exists(EXTENDED_TTL):
        with open(EXTENDED_TTL) as f:
            for line in f:
                if "a owl:Class" in line:
                    ttl_classes += 1
                if f"discoveredInCase {case_id} " in line or f"firstDiscoveredInCase {case_id} " in line:
                    discovered += 1
    print(f"Extended TTL: {ttl_classes} total classes, {discovered} referencing case {case_id}")
    if discovered == 0:
        issues.append(f"CRITICAL: No discoveredInCase references for case {case_id} in TTL")

    # 5. OntServe DB registration
    ont_row = psql(
        f"SELECT COUNT(*) FROM ontology_entities oe "
        f"JOIN ontologies o ON oe.ontology_id = o.id "
        f"WHERE o.name = 'proethica-case-{case_id}';",
        db="ontserve"
    )
    ont_count = int(ont_row) if ont_row else 0
    print(f"OntServe DB: proethica-case-{case_id} has {ont_count} entities")
    if ont_count == 0:
        issues.append(f"CRITICAL: Case ontology not registered in OntServe DB")

    # 6. Model consistency
    models = psql(
        f"SELECT DISTINCT llm_model FROM extraction_prompts WHERE case_id = {case_id};"
    )
    model_list = [m.strip() for m in models.split("\n") if m.strip()] if models else []
    # "algorithmic" is expected from reconciliation step
    llm_models = [m for m in model_list if m != "algorithmic"]
    if llm_models == ["claude-sonnet-4-6"]:
        print(f"Model: claude-sonnet-4-6 (consistent)")
    elif not llm_models:
        print(f"Model: no LLM prompts found")
    else:
        print(f"Models: {', '.join(llm_models)}")
        issues.append(f"WARNING: Non-standard models: {llm_models}")

    # Summary
    if issues:
        print(f"\nIssues ({len(issues)}):")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print(f"\nAll checks PASSED")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/verify_case_quick.py <case_id> [case_id ...]")
        sys.exit(1)

    case_ids = [int(x) for x in sys.argv[1:]]
    all_pass = True
    for cid in case_ids:
        if not verify_case(cid):
            all_pass = False

    if len(case_ids) > 1:
        print(f"\n{'=' * 50}")
        print(f"Summary: {'ALL PASSED' if all_pass else 'ISSUES FOUND'}")

    sys.exit(0 if all_pass else 1)
