# ProEthica Demo Walkthrough & Feedback

**Date:** November 19, 2025
**Case:** Case 7 - http://localhost:5000/cases/7
**Context:** See [PROGRESS.md](PROGRESS.md) for recent changes
**Goal:** Complete end-to-end extraction workflow, collect feedback for improvements

---

## Walkthrough Plan

### Step 1 - Contextual Framework (Pass 1)
- [x] Navigate to Step 1 for Case 7
- [x] Extract Facts section (Roles, States, Resources) - 20 entities
- [x] Extract Discussion section (Roles, States, Resources) - 0 roles, 8 states, 8 resources
- [ ] Review extracted entities
- [ ] Test "Clear & Re-run" functionality

### Step 2 - Normative Requirements (Pass 2)
- [ ] Extract Facts section (Principles, Obligations, Constraints, Capabilities)
- [ ] Extract Discussion section
- [ ] Review extracted entities
- [ ] Test clear functionality

### Step 3 - Temporal Dynamics (Pass 3)
- [ ] Run Actions extraction
- [ ] Run Events extraction
- [ ] Review timeline, causal chains, Allen relations
- [ ] Test clear functionality

### Step 4 - Whole Case Synthesis
- [ ] Run synthesis
- [ ] Review code provisions, questions, conclusions
- [ ] Check entity graph visualization
- [ ] Test "Refresh from OntServe" button
- [ ] Test clear functionality

---

## Feedback Collection

### 🐛 ERRORS (Fix Immediately)
*Critical bugs that block workflow*

1.

---

### 💡 IMPROVEMENTS (Collect for Later)
*Functionality enhancements*

1.

---

### 📝 UI/UX FEEDBACK (Collect for Later)
*Interface improvements, confusing elements*

1. **Step 1 Facts Review - Confusing "No new roles" message**
   - Location: [entity_review.html](app/templates/entity_review/entity_review.html) - Roles section
   - Issue: Message says "All roles were already captured in the Facts section" when viewing Facts section itself
   - Current text suggests checking Facts section, but user IS on Facts section
   - Better message: "Roles from ontology identified. Individuals extracted and linked to role types."
   - Or context-aware: Show different message for Facts vs Discussion sections

2. **Step 1 Warning Banners Should Be Section-Specific**
   - Location: Step 1 extraction page - Facts and Discussion sections
   - Issue: Warning banner for "re-run will create duplicates" should be specific to each section
   - Expected behavior:
     - Facts warning: Only show if Facts extraction has been run before
     - Discussion warning: Only show if Discussion extraction has been run before
   - Current behavior appears to be pass-wide (showing for entire Pass 1)
   - Need section-level tracking of extraction status

---

### ⚠️ WARNINGS/ISSUES (Collect for Later)
*Non-blocking issues, edge cases*

1.

---

## Notes

*Use this section for general observations during the walkthrough*

**Step 1 - Facts Section (Completed)**
- 20 RDF entities extracted successfully
- Warning banner for duplicate prevention working correctly
- Review page accessible at `/scenario_pipeline/case/7/entities/review/pass1?section_type=facts`
- Note: Review page shows ONLY Pass 1 Facts entities (section-specific)

**Step 1 - Discussion Section (Completed)**
- 0 Roles (expected - no new roles in discussion)
- 3 State classes, 5 individuals
- 3 Resource classes, 5 individuals
- Total: 16 new entities from Discussion section
- Review page will show ONLY Pass 1 Discussion entities (section-specific)

---

## Summary

**Total Issues Found:**
- Errors: 0
- Improvements: 0
- UI/UX: 2
- Warnings: 0

**Status:** Ready to address feedback

---

**END OF DEMO FEEDBACK**
