#!/usr/bin/env python3
"""
Run the ProEthica extraction pipeline for a case via HTTP API.

Usage:
    python scripts/run_pipeline.py <case_id>                  # Full pipeline (uncommit -> Steps 1-4 -> commit)
    python scripts/run_pipeline.py <case_id> --step 1         # Step 1 only (facts + discussion)
    python scripts/run_pipeline.py <case_id> --step 2         # Step 2 only
    python scripts/run_pipeline.py <case_id> --step 3         # Step 3 only
    python scripts/run_pipeline.py <case_id> --step reconcile # Reconciliation only
    python scripts/run_pipeline.py <case_id> --step commit    # Commit to OntServe only
    python scripts/run_pipeline.py <case_id> --step uncommit  # Uncommit from OntServe only
    python scripts/run_pipeline.py <case_id> --step 4         # Step 4 only
    python scripts/run_pipeline.py <case_id> --step qc        # Run QC audit only
    python scripts/run_pipeline.py --list                     # List unextracted cases
    python scripts/run_pipeline.py --status <case_id>         # Show extraction status
    python scripts/run_pipeline.py --batch                    # Full batch: clean + extract all cases
    python scripts/run_pipeline.py --batch --skip-clean       # Batch without cleanup (resume)
    python scripts/run_pipeline.py --batch --start-from 56    # Resume batch from case 56
    python scripts/run_pipeline.py --clean                    # Run cleanup only (no extraction)

Requires ProEthica server running on localhost:5000.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:5000"
DB_ENV = {"PGPASSWORD": "PASS", "PATH": "/usr/bin:/bin"}
ONTSERVE_PATH = "/home/chris/onto/OntServe"
EXTENDED_TTL = os.path.join(ONTSERVE_PATH, "ontologies", "proethica-intermediate-extended.ttl")

EXTENDED_TTL_SKELETON = """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix proeth: <http://proethica.org/ontology/intermediate#> .
@prefix proeth-core: <http://proethica.org/ontology/core#> .
@prefix proeth-prov: <http://proethica.org/provenance#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

proeth: rdfs:comment "Full batch re-extraction with pipeline commit and class accumulation." .
"""


def http_post(path, data=None, stream=False):
    """POST to the server, optionally streaming SSE."""
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode() if data else b'{}'
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        },
    )
    return urllib.request.urlopen(req, timeout=600)


def http_get(path, stream=False):
    """GET from the server, optionally streaming SSE."""
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "text/event-stream" if stream else "application/json"},
    )
    return urllib.request.urlopen(req, timeout=600)


def parse_sse_events(response):
    """Yield parsed JSON from SSE data lines."""
    for raw_line in response:
        line = raw_line.decode("utf-8").strip()
        if line.startswith("data: "):
            try:
                yield json.loads(line[6:])
            except json.JSONDecodeError:
                pass


def collect_sse(response):
    """Collect all SSE events and return summary."""
    events = []
    for data in parse_sse_events(response):
        events.append(data)
        status = data.get("status", data.get("stage", ""))
        if status in ("extracted", "stored"):
            etype = data.get("entity_type", "?")
            result = data.get("result") or {}
            classes = (result.get("data") or {}).get("classes", [])
            individuals = (result.get("data") or {}).get("individuals", [])
            if classes or individuals:
                print(f"    {etype}: {len(classes)} classes, {len(individuals)} individuals")
        elif "_DONE" in str(status) or status in ("COMPLETE", "complete"):
            msg = data.get("message", data.get("messages", ""))
            if isinstance(msg, list):
                msg = msg[0] if msg else ""
            print(f"    {status}: {msg}")
        elif status == "error":
            print(f"    ERROR: {json.dumps(data)[:300]}")
    return events


def run_step1(case_id, section_type):
    """Run Step 1 extraction for a section."""
    print(f"  Step 1 {section_type}...")
    t0 = time.time()
    resp = http_post(
        f"/scenario_pipeline/case/{case_id}/entities_pass_execute_streaming",
        {"section_type": section_type},
        stream=True,
    )
    events = collect_sse(resp)
    elapsed = time.time() - t0
    print(f"    Completed in {elapsed:.0f}s")
    return events


def run_step2(case_id, section_type):
    """Run Step 2 extraction for a section."""
    print(f"  Step 2 {section_type}...")
    t0 = time.time()
    resp = http_post(
        f"/scenario_pipeline/case/{case_id}/normative_pass_execute_streaming",
        {"section_type": section_type},
        stream=True,
    )
    events = collect_sse(resp)
    elapsed = time.time() - t0
    print(f"    Completed in {elapsed:.0f}s")
    return events


def run_step3(case_id):
    """Run Step 3 (temporal dynamics via LangGraph)."""
    print("  Step 3 (LangGraph temporal dynamics)...")
    t0 = time.time()
    resp = http_get(
        f"/scenario_pipeline/case/{case_id}/step3/extract_enhanced",
        stream=True,
    )
    events = collect_sse(resp)
    elapsed = time.time() - t0
    print(f"    Completed in {elapsed:.0f}s")
    return events


def run_reconcile(case_id, mode="auto"):
    """Run reconciliation. mode='auto' for exact-match only, 'review' for LLM dedup."""
    print(f"  Reconciliation (mode={mode})...")
    t0 = time.time()
    resp = http_post(f"/scenario_pipeline/case/{case_id}/reconcile/run", {"mode": mode})
    data = json.loads(resp.read().decode())
    elapsed = time.time() - t0
    success = data.get("success", False)
    candidates = len(data.get("candidates", []))
    auto_merged = data.get("auto_merged", 0)
    print(f"    Success={success}, candidates={candidates}, auto_merged={auto_merged}")
    print(f"    Completed in {elapsed:.0f}s")
    return data


def run_step4(case_id):
    """Run Step 4 complete synthesis stream."""
    print("  Step 4 (complete synthesis)...")
    t0 = time.time()
    resp = http_post(
        f"/scenario_pipeline/case/{case_id}/run_complete_synthesis_stream",
        stream=True,
    )
    events = collect_sse(resp)
    elapsed = time.time() - t0
    print(f"    Completed in {elapsed:.0f}s")
    return events


def run_arguments(case_id):
    """Generate pro/con arguments for decision points (Part F of Step 4)."""
    print("  Generating arguments...")
    t0 = time.time()
    try:
        resp = http_post(f"/scenario_pipeline/case/{case_id}/generate_arguments")
        data = json.loads(resp.read().decode())
        elapsed = time.time() - t0
        args_list = data.get("arguments", [])
        total_pro = sum(len(a.get("pro_arguments", [])) for a in args_list)
        total_con = sum(len(a.get("con_arguments", [])) for a in args_list)
        print(f"    Decision points={len(args_list)}, pro={total_pro}, con={total_con}")
        print(f"    Completed in {elapsed:.0f}s")
        return data
    except urllib.error.HTTPError as e:
        elapsed = time.time() - t0
        body = e.read().decode() if e.fp else ''
        print(f"    Warning: argument generation returned {e.code} ({elapsed:.0f}s)")
        if body:
            try:
                err_data = json.loads(body)
                print(f"    {err_data.get('error', body[:200])}")
            except json.JSONDecodeError:
                print(f"    {body[:200]}")
        return {}


def run_uncommit(case_id):
    """Uncommit existing OntServe data for a case (idempotent)."""
    print("  Uncommitting from OntServe...")
    t0 = time.time()
    try:
        resp = http_post(f"/scenario_pipeline/case/{case_id}/reconcile/uncommit")
        data = json.loads(resp.read().decode())
        elapsed = time.time() - t0
        deleted = data.get('ontserve_entities_deleted', 0)
        ttl = data.get('ttl_deleted', False)
        print(f"    Entities deleted={deleted}, TTL deleted={ttl}")
        print(f"    Completed in {elapsed:.0f}s")
        return data
    except urllib.error.HTTPError as e:
        elapsed = time.time() - t0
        if e.code == 400:
            print(f"    No committed entities to uncommit (clean state)")
        else:
            print(f"    Warning: uncommit returned {e.code} ({elapsed:.0f}s)")
        return {}


def run_commit(case_id):
    """Commit entities to OntServe."""
    print("  Committing to OntServe...")
    t0 = time.time()
    try:
        resp = http_post(f"/scenario_pipeline/case/{case_id}/entities/commit")
        data = json.loads(resp.read().decode())
        elapsed = time.time() - t0
        result = data.get('result', data)
        classes = result.get('classes_committed', 0)
        individuals = result.get('individuals_committed', 0)
        print(f"    Classes={classes}, Individuals={individuals}")
        print(f"    Completed in {elapsed:.0f}s")
        return data
    except urllib.error.HTTPError as e:
        elapsed = time.time() - t0
        body = e.read().decode() if e.fp else ''
        print(f"    Warning: commit returned {e.code} ({elapsed:.0f}s)")
        if body:
            try:
                err_data = json.loads(body)
                print(f"    {err_data.get('error', body[:200])}")
            except json.JSONDecodeError:
                print(f"    {body[:200]}")
        return {}


def run_qc(case_id):
    """Run QC audit via HTTP API (uses running Flask server context)."""
    print("  QC Audit (V0-V9)...")
    t0 = time.time()
    try:
        resp = http_post(f"/api/qc/audit/{case_id}")
        data = json.loads(resp.read().decode())
        elapsed = time.time() - t0

        if not data.get('success'):
            print(f"    QC audit failed: {data.get('error', 'unknown')} ({elapsed:.0f}s)")
            return None

        audit = data['audit']
        status = audit['overall_status']
        total = audit['entity_count_total']
        types = audit['extraction_types_count']
        cc = audit['critical_count']
        wc = audit['warning_count']
        ic = audit['info_count']

        symbol = '[+]' if status == 'PASS' else '[!]' if status == 'ISSUES_FOUND' else '[X]'
        print(f"    {symbol} {status}  ({total} entities, {types} types, {cc}C/{wc}W/{ic}I)")

        # Print issue details
        for check in audit.get('check_results', []):
            if check['status'] in ('FAIL', 'INFO') and check['check_id'] != 'V1':
                print(f"    {check['check_id']} {check['name']}: {check['status']} [{check['severity']}]")
                if check.get('message'):
                    print(f"      {check['message'][:120]}")

        print(f"    Completed in {elapsed:.0f}s")
        return audit
    except urllib.error.HTTPError as e:
        elapsed = time.time() - t0
        print(f"    QC audit HTTP error {e.code} ({elapsed:.0f}s)")
        return None
    except Exception as e:
        elapsed = time.time() - t0
        print(f"    QC audit failed: {e} ({elapsed:.0f}s)")
        return None


def clear_old_entities(case_id):
    """Delete pre-existing entities and prompts for a case before re-extraction."""
    result = subprocess.run(
        ["psql", "-h", "localhost", "-U", "postgres", "-d", "ai_ethical_dm", "-t", "-A", "-c",
         f"DELETE FROM temporary_rdf_storage WHERE case_id = {case_id}; "
         f"DELETE FROM extraction_prompts WHERE case_id = {case_id}; "
         f"DELETE FROM reconciliation_decisions WHERE run_id IN "
         f"(SELECT id FROM reconciliation_runs WHERE case_id = {case_id}); "
         f"DELETE FROM reconciliation_runs WHERE case_id = {case_id};"],
        capture_output=True, text=True, env=DB_ENV,
    )
    if result.returncode == 0:
        print("    Cleared old entities and prompts")
    else:
        print(f"    Warning: clear failed: {result.stderr.strip()}")


def run_full_pipeline(case_id):
    """Run the complete pipeline for a case."""
    total_start = time.time()

    print(f"\nPipeline run for case {case_id}")
    print("=" * 50)

    run_uncommit(case_id)
    clear_old_entities(case_id)
    run_step1(case_id, "facts")
    run_step1(case_id, "discussion")
    run_step2(case_id, "facts")
    run_step2(case_id, "discussion")
    run_step3(case_id)
    run_reconcile(case_id)
    run_commit(case_id)
    run_step4(case_id)
    run_commit(case_id)  # Second commit: Step 4 synthesis entities

    # QC audit (V0-V9) - stored as provenance
    run_qc(case_id)

    total_elapsed = time.time() - total_start
    print(f"\nTotal wall time: {total_elapsed:.0f}s ({total_elapsed/60:.1f}m)")

    # Print entity summary
    print_status(case_id)
    return total_elapsed


# ---- Batch processing helpers ----

def psql(query, db="ai_ethical_dm"):
    """Run a psql query and return stdout."""
    result = subprocess.run(
        ["psql", "-h", "localhost", "-U", "postgres", "-d", db, "-t", "-A", "-c", query],
        capture_output=True, text=True, env=DB_ENV,
    )
    if result.returncode != 0:
        print(f"  psql error: {result.stderr.strip()}")
        return ""
    return result.stdout.strip()


def count_extended_classes():
    """Count owl:Class entries in proethica-intermediate-extended.ttl."""
    if not os.path.exists(EXTENDED_TTL):
        return 0
    count = 0
    with open(EXTENDED_TTL) as f:
        for line in f:
            if "a owl:Class" in line:
                count += 1
    return count


def get_case_order():
    """Get all case IDs in batch order: Year DESC, case_number ASC."""
    query = """
SELECT d.id
FROM documents d
WHERE d.document_type IN ('case', 'case_study')
  AND d.content IS NOT NULL AND LENGTH(d.content) > 100
ORDER BY
  (d.doc_metadata->>'year')::text DESC NULLS LAST,
  (d.doc_metadata->>'case_number')::text ASC;
"""
    rows = psql(query)
    if not rows:
        return []
    return [int(r) for r in rows.split("\n") if r.strip()]


def run_cleanup():
    """
    Full pre-batch cleanup. Resets all extraction state for a fresh run.

    Operations:
    1. Reset proethica-intermediate-extended.ttl to skeleton
    2. Delete all proethica-case-*.ttl files
    3. Clear OntServe DB registrations for case ontologies
    4. Reset published flags in ProEthica DB
    5. Clear pipeline tracking tables
    6. Refresh OntServe extended ontology DB
    """
    print("\n" + "=" * 60)
    print("PRE-BATCH CLEANUP")
    print("=" * 60)

    # 1. Reset extended TTL
    print("\n[1/6] Resetting proethica-intermediate-extended.ttl...")
    with open(EXTENDED_TTL, "w") as f:
        f.write(EXTENDED_TTL_SKELETON)
    print("  Written skeleton TTL")

    # 2. Delete case TTL files
    print("\n[2/6] Deleting case TTL files...")
    ttl_dir = os.path.join(ONTSERVE_PATH, "ontologies")
    deleted_ttl = 0
    for fname in os.listdir(ttl_dir):
        if fname.startswith("proethica-case-") and fname.endswith(".ttl"):
            os.remove(os.path.join(ttl_dir, fname))
            deleted_ttl += 1
    print(f"  Deleted {deleted_ttl} case TTL files")

    # 3. Clear OntServe DB case registrations
    print("\n[3/6] Clearing OntServe DB case registrations...")
    n1 = psql(
        "DELETE FROM ontology_entities WHERE ontology_id IN "
        "(SELECT id FROM ontologies WHERE name LIKE 'proethica-case-%'); "
        "SELECT COUNT(*) FROM ontology_entities WHERE 1=0;",
        db="ontserve"
    )
    n2 = psql(
        "DELETE FROM ontology_versions WHERE ontology_id IN "
        "(SELECT id FROM ontologies WHERE name LIKE 'proethica-case-%');",
        db="ontserve"
    )
    n3 = psql("DELETE FROM ontologies WHERE name LIKE 'proethica-case-%';", db="ontserve")
    print(f"  Cleared case ontology registrations from OntServe DB")

    # 4. Reset published flags
    print("\n[4/6] Resetting published flags...")
    result = psql("UPDATE temporary_rdf_storage SET is_published = false WHERE is_published = true RETURNING id;")
    count = len(result.split("\n")) if result else 0
    print(f"  Reset {count} published entities")

    # 5. Clear pipeline tracking tables
    print("\n[5/6] Clearing pipeline tracking tables...")
    psql("DELETE FROM pipeline_queue;")
    psql("DELETE FROM pipeline_runs;")
    psql("SELECT setval('pipeline_runs_id_seq', 1, false);")
    psql("SELECT setval('pipeline_queue_id_seq', 1, false);")
    print("  Cleared pipeline_runs and pipeline_queue")

    # 6. Refresh OntServe extended ontology DB
    print("\n[6/6] Refreshing OntServe extended ontology in DB...")
    refresh_script = os.path.join(ONTSERVE_PATH, "scripts", "refresh_entity_extraction.py")
    venv_python = os.path.join(ONTSERVE_PATH, "venv-ontserve", "bin", "python")
    if os.path.exists(refresh_script) and os.path.exists(venv_python):
        subprocess.run(
            [venv_python, refresh_script, "proethica-intermediate-extended"],
            capture_output=True, text=True,
            cwd=ONTSERVE_PATH,
        )
        print("  Refreshed proethica-intermediate-extended in OntServe DB")
    else:
        print("  WARNING: refresh script or venv not found, skipping DB refresh")

    print("\nCleanup complete.")


EXPECTED_TYPES = [
    "canonical_decision_point", "capabilities", "causal_normative_link",
    "code_provision_reference", "constraints", "ethical_conclusion",
    "ethical_question", "obligations", "precedent_case_reference",
    "principles", "question_emergence", "resolution_pattern",
    "resources", "roles", "states", "temporal_dynamics_enhanced",
]


def verify_case(case_id, classes_before):
    """
    Post-extraction verification for a case.

    Checks:
    1. All 16 extraction types present
    2. Published count matches total
    3. Extended TTL class accumulation
    4. OntServe DB registration
    """
    issues = []
    classes_after = count_extended_classes()
    new_classes = classes_after - classes_before

    # 1. Check all 16 extraction types present
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
                type_counts[parts[0]] = int(parts[1])
                total += int(parts[1])

    missing = [t for t in EXPECTED_TYPES if type_counts.get(t, 0) == 0]
    if missing:
        issues.append(f"Missing extraction types: {', '.join(missing)}")

    # 2. Published vs total
    published = psql(
        f"SELECT COUNT(*) FROM temporary_rdf_storage "
        f"WHERE case_id = {case_id} AND is_published = true;"
    )
    published = int(published) if published else 0
    if total != published:
        issues.append(f"Publish mismatch: {total} total vs {published} published")

    # 3. TTL accumulation
    discovered = 0
    if os.path.exists(EXTENDED_TTL):
        with open(EXTENDED_TTL) as f:
            for line in f:
                if f"discoveredInCase {case_id} " in line or f"firstDiscoveredInCase {case_id} " in line:
                    discovered += 1
    if new_classes == 0:
        issues.append(f"No new classes added to extended TTL")
    if discovered == 0 and new_classes > 0:
        issues.append(f"No discoveredInCase references in TTL")

    # 4. OntServe DB
    ont_count = psql(
        f"SELECT COUNT(*) FROM ontology_entities oe "
        f"JOIN ontologies o ON oe.ontology_id = o.id "
        f"WHERE o.name = 'proethica-case-{case_id}';",
        db="ontserve"
    )
    ont_count = int(ont_count) if ont_count else 0
    if ont_count == 0:
        issues.append(f"Case ontology not registered in OntServe DB")

    print(f"  Verification: {total} entities ({published} published), "
          f"{classes_before}->{classes_after} classes (+{new_classes}), "
          f"OntServe={ont_count}")
    if missing:
        print(f"  MISSING TYPES: {', '.join(missing)}")

    return issues


def run_batch(start_from=None, skip_clean=False):
    """
    Run the full batch extraction pipeline.

    1. Clean all state (unless --skip-clean)
    2. Get case order (Year DESC, case_number ASC)
    3. Process each case: full pipeline + commit + accumulation check
    4. Print summary report
    """
    batch_start = time.time()

    if not skip_clean:
        run_cleanup()

    case_ids = get_case_order()
    if not case_ids:
        print("ERROR: No cases found in database")
        return 1

    # Handle --start-from: skip cases before the start point
    if start_from is not None:
        if start_from not in case_ids:
            print(f"ERROR: Case {start_from} not found in case list")
            print(f"Available: {case_ids[:10]}...")
            return 1
        idx = case_ids.index(start_from)
        skipped = case_ids[:idx]
        case_ids = case_ids[idx:]
        print(f"\nResuming from case {start_from} (skipping {len(skipped)} already-processed cases)")

    total_cases = len(case_ids)
    print(f"\nBatch processing {total_cases} cases")
    print(f"Order: {case_ids[:5]}... {case_ids[-3:]}" if total_cases > 8 else f"Order: {case_ids}")
    print("=" * 60)

    results = []
    failed = []

    for i, case_id in enumerate(case_ids, 1):
        classes_before = count_extended_classes()

        print(f"\n[{i}/{total_cases}] Case {case_id} (TTL classes: {classes_before})")
        print("-" * 50)

        try:
            elapsed = run_full_pipeline(case_id)

            # Verify accumulation
            issues = verify_case(case_id, classes_before)
            if issues:
                for issue in issues:
                    print(f"  WARNING: {issue}")

            results.append({
                'case_id': case_id,
                'success': True,
                'elapsed': elapsed,
                'classes_after': count_extended_classes(),
                'issues': issues,
            })

        except Exception as e:
            print(f"  FAILED: {e}")
            failed.append({'case_id': case_id, 'error': str(e)})
            results.append({
                'case_id': case_id,
                'success': False,
                'elapsed': 0,
                'error': str(e),
            })
            # Continue with next case
            continue

    # Print summary
    batch_elapsed = time.time() - batch_start
    successful = [r for r in results if r['success']]
    print(f"\n{'=' * 60}")
    print(f"BATCH COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total: {len(results)}, Successful: {len(successful)}, Failed: {len(failed)}")
    print(f"Total time: {batch_elapsed:.0f}s ({batch_elapsed/60:.1f}m, {batch_elapsed/3600:.1f}h)")
    if successful:
        avg = sum(r['elapsed'] for r in successful) / len(successful)
        print(f"Average per case: {avg:.0f}s ({avg/60:.1f}m)")
    print(f"Final TTL classes: {count_extended_classes()}")

    if failed:
        print(f"\nFailed cases:")
        for f in failed:
            print(f"  Case {f['case_id']}: {f['error'][:100]}")

    with_issues = [r for r in successful if r.get('issues')]
    if with_issues:
        print(f"\nCases with accumulation issues:")
        for r in with_issues:
            print(f"  Case {r['case_id']}: {'; '.join(r['issues'])}")

    return 0 if not failed else 1


def print_status(case_id):
    """Print extraction status for a case."""
    rows = psql(
        f"SELECT extraction_type, COUNT(*) FROM temporary_rdf_storage "
        f"WHERE case_id = {case_id} GROUP BY extraction_type ORDER BY extraction_type;"
    )
    if rows:
        print(f"\nEntity counts for case {case_id}:")
        total = 0
        for line in rows.split("\n"):
            parts = line.split("|")
            if len(parts) == 2:
                etype, count = parts[0], int(parts[1])
                total += count
                print(f"  {etype:40s} {count:4d}")
        print(f"  {'TOTAL':40s} {total:4d}")
    else:
        print(f"\nNo entities found for case {case_id}")

    models = psql(f"SELECT DISTINCT llm_model FROM extraction_prompts WHERE case_id = {case_id};")
    if models:
        print(f"\nModels used: {', '.join(models.split(chr(10)))}")


def list_unextracted():
    """List cases that have not been extracted yet."""
    rows = psql(
        "SELECT d.id, LEFT(d.title, 70) as title, LENGTH(d.content) as chars "
        "FROM documents d "
        "WHERE d.document_type IN ('case', 'case_study') "
        "  AND d.id NOT IN (SELECT DISTINCT case_id FROM temporary_rdf_storage WHERE case_id IS NOT NULL) "
        "  AND d.id NOT IN (SELECT DISTINCT case_id FROM extraction_prompts WHERE case_id IS NOT NULL) "
        "  AND d.content IS NOT NULL AND LENGTH(d.content) > 100 "
        "ORDER BY d.id;"
    )
    if rows:
        print("Unextracted cases:")
        print(f"  {'ID':>4s}  {'Title':70s}  {'Chars':>6s}")
        print(f"  {'--':>4s}  {'-----':70s}  {'-----':>6s}")
        for line in rows.split("\n"):
            parts = line.split("|")
            if len(parts) >= 3:
                print(f"  {parts[0]:>4s}  {parts[1]:70s}  {parts[2]:>6s}")
    else:
        print("No unextracted cases found (or database error)")


def check_server():
    """Check if ProEthica server is running."""
    try:
        resp = urllib.request.urlopen(f"{BASE_URL}/", timeout=5)
        return resp.status == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Run ProEthica extraction pipeline")
    parser.add_argument("case_id", nargs="?", type=int, help="Case ID to process")
    parser.add_argument("--step", choices=["1", "2", "3", "reconcile", "commit", "uncommit", "4", "qc"],
                        help="Run a specific step only")
    parser.add_argument("--section", choices=["facts", "discussion"],
                        help="Section type for Steps 1-2 (default: both)")
    parser.add_argument("--list", action="store_true", help="List unextracted cases")
    parser.add_argument("--status", action="store_true", help="Show extraction status")
    parser.add_argument("--batch", action="store_true",
                        help="Run full batch: clean all state + extract all cases in order")
    parser.add_argument("--skip-clean", action="store_true",
                        help="Skip cleanup step in batch mode (for resuming)")
    parser.add_argument("--start-from", type=int, metavar="CASE_ID",
                        help="Resume batch from this case ID (implies --skip-clean)")
    parser.add_argument("--clean", action="store_true",
                        help="Run cleanup only (reset TTL, clear DB state)")
    parser.add_argument("--injection-mode", choices=["full", "label_only"],
                        default="full",
                        help="Ontology injection mode: full (Phase 1) or label_only (Phase 2)")

    args = parser.parse_args()

    if args.list:
        list_unextracted()
        return 0

    if args.clean:
        run_cleanup()
        return 0

    if args.batch:
        if not check_server():
            print("ERROR: ProEthica server not running on localhost:5000")
            return 1
        # Set injection mode on the Flask server for batch
        if args.injection_mode != 'full':
            resp = http_post(
                "/pipeline/api/set_injection_mode",
                {"mode": args.injection_mode},
            )
            if resp and resp.status == 200:
                print(f"Injection mode set to: {args.injection_mode}")
        skip_clean = args.skip_clean or args.start_from is not None
        return run_batch(start_from=args.start_from, skip_clean=skip_clean)

    if not args.case_id:
        parser.print_help()
        return 1

    if args.status:
        print_status(args.case_id)
        return 0

    if not check_server():
        print("ERROR: ProEthica server not running on localhost:5000")
        print("Start with: cd proethica && source venv-proethica/bin/activate && python run.py")
        return 1

    # Set injection mode on the Flask server
    if args.injection_mode != 'full':
        resp = http_post(
            "/pipeline/api/set_injection_mode",
            {"mode": args.injection_mode},
        )
        if resp and resp.status == 200:
            print(f"Injection mode set to: {args.injection_mode}")
        else:
            print(f"WARNING: Failed to set injection mode to {args.injection_mode}")

    case_id = args.case_id

    if args.step is None:
        run_full_pipeline(case_id)
    elif args.step == "1":
        sections = [args.section] if args.section else ["facts", "discussion"]
        for s in sections:
            run_step1(case_id, s)
        print_status(case_id)
    elif args.step == "2":
        sections = [args.section] if args.section else ["facts", "discussion"]
        for s in sections:
            run_step2(case_id, s)
        print_status(case_id)
    elif args.step == "3":
        run_step3(case_id)
        print_status(case_id)
    elif args.step == "reconcile":
        run_reconcile(case_id)
    elif args.step == "commit":
        run_commit(case_id)
    elif args.step == "uncommit":
        run_uncommit(case_id)
    elif args.step == "4":
        run_step4(case_id)
        print_status(case_id)
    elif args.step == "qc":
        run_qc(case_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())
