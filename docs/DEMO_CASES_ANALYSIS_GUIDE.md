# Demo Cases Analysis Guide

Quick guide for analyzing cases 8, 10, and 13 for production deployment.

## Step 1: Clean Existing Data

```bash
cd /home/chris/onto/proethica
./scripts/clean_demo_cases.sh 8 10 13
```

This removes all existing extraction data from:
- ProEthica database (temporary_rdf_storage, extraction_prompts)
- OntServe case ontologies (if any)

## Step 2: Analyze Each Case

For each case (8, 10, 13), run the complete workflow:

### Case 8: Stormwater Management Dilemma

**Step 1 - Pass 1**: http://localhost:5000/scenario_pipeline/case/8/step1
- Click "Run Pass 1 Extraction" (or equivalent button)
- Wait for completion (~2-3 minutes)
- Verify: Roles, States, Resources extracted from Facts + Discussion

**Step 2 - Pass 2**: http://localhost:5000/scenario_pipeline/case/8/step2
- Click "Run Pass 2 Extraction"
- Wait for completion (~2-3 minutes)
- Verify: Principles, Obligations, Constraints, Capabilities extracted

**Step 3 - Pass 3**: http://localhost:5000/scenario_pipeline/case/8/step3
- Click "Run Pass 3 Extraction" or "Enhanced Temporal (Beta)"
- Wait for completion (~3-5 minutes for Enhanced Temporal)
- Verify: Actions, Events extracted

**Step 4 - Synthesis**: http://localhost:5000/scenario_pipeline/case/8/step4
- Click "Run Whole-Case Synthesis"
- Wait for completion (~3-5 minutes)
- Verify synthesis saved (should see message about saving questions/conclusions)
- Click "View Step 4 Review" to verify results

### Case 10: Post-Public Employment

Repeat the same steps:
- Step 1: http://localhost:5000/scenario_pipeline/case/10/step1
- Step 2: http://localhost:5000/scenario_pipeline/case/10/step2
- Step 3: http://localhost:5000/scenario_pipeline/case/10/step3
- Step 4: http://localhost:5000/scenario_pipeline/case/10/step4

### Case 13: Lawn Irrigation Design

Repeat the same steps:
- Step 1: http://localhost:5000/scenario_pipeline/case/13/step1
- Step 2: http://localhost:5000/scenario_pipeline/case/13/step2
- Step 3: http://localhost:5000/scenario_pipeline/case/13/step3
- Step 4: http://localhost:5000/scenario_pipeline/case/13/step4

## Step 3: Verify All Cases

Check each case's Step 4 review page:
- Case 8: http://localhost:5000/scenario_pipeline/case/8/step4/review
- Case 10: http://localhost:5000/scenario_pipeline/case/10/step4/review
- Case 13: http://localhost:5000/scenario_pipeline/case/13/step4/review

Verify each shows:
- Code Provisions
- Questions with entity tagging
- Conclusions with Q→C links
- Entity graph visualization

## Step 4: Create Database Backup

```bash
cd /home/chris/onto/proethica
./scripts/backup_demo_database.sh
```

This creates: `backups/proethica_demo_YYYYMMDD_HHMMSS.sql`

## Step 5: Deploy to Production

Follow: [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

## Estimated Time

- Cleanup: 1 minute
- Analysis per case: 10-15 minutes
- Total for 3 cases: 30-45 minutes
- Database backup: 1 minute
- Deployment: 10-15 minutes

**Total: ~50-70 minutes**

## Notes

- Run analyses during off-peak hours to ensure good LLM response times
- Monitor browser console for any JavaScript errors
- If Step 4 synthesis fails, check that Passes 1-3 completed successfully
- Keep browser tab open during each extraction (don't navigate away)
