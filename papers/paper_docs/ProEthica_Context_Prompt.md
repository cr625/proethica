## Academic Writing Style Guidelines

**Tone and Language Requirements**:
- Use measured, academic language without overly enthusiastic expressions
- Avoid superlatives and promotional language ("novel," "cutting-edge," "revolutionary")
- Write in clear, direct prose suitable for technical academic audience

**Sentence Structure Guidelines**:
- Minimize front-loaded dependent clauses that delay the main point
- Avoid em dashes (—) and minimize colons (:) except in lists
- Use straightforward subject-verb-object construction when possible
- Break complex sentences into simpler, clearer statements

**Academic Precision**:
- Use precise technical terminology without jargon
- Present claims objectively with appropriate evidence
- Maintain professional tone throughout all sections
- Focus on "what the system does" rather than "how amazing it is"

---

# ProEthica Project Context Prompt

## Quick Project Summary
We are collaboratively writing an academic paper titled **"ProEthica: Ontology-Constrained Ethical Reasoning with Large Language Models"** for submission to AAAI or similar AI/ethics venue. The paper presents a system that combines LLMs with role-based ontologies to improve ethical reasoning in professional contexts, specifically evaluated on NSPE engineering ethics cases.

## Key Project Files
**ALWAYS check these files at the start of any session:**
- `D:\OneDrive\Working\AAAI Ethics\paper\ProEthica_Structure_Outline_MASTER.md` - **MASTER** paper structure outline
- `D:\OneDrive\Working\AAAI Ethics\paper\ProEthica_Progress_Tracking.md` - **COMPREHENSIVE** progress tracking with section completion status, reviewer comments integration, and bibliography management
- Individual section files in `/sections/` directory for modular development
- `D:\OneDrive\Working\AAAI Ethics\paper\references\ProEthica_References.bib` - Bibliography database

## Critical File Organization Rules
⚠️ **OUTLINE-SECTION CONSISTENCY**: The `ProEthica_Structure_Outline.md` is the master structure document. If the outline is revised, ALL corresponding section files in `/sections/` must be updated to maintain consistency. Always:
1. Update the outline structure first
2. Revise corresponding individual section files
3. Update progress tracking to reflect changes
4. Maintain consistent file naming patterns

📁 **Section File Organization**: Each subsection has its own markdown file in `/sections/` directory using pattern `Section_X_Y_Title.md`. This enables:
- Parallel development of different sections
- Version control of individual components
- Modular editing and collaboration
- Clear progress tracking

**Current Section Files Status**: See ProEthica_Structure_Outline.md for complete status of all sections (✅ COMPLETE vs ⏳ TO CREATE)

## Core Technical Approach
- **Problem**: LLMs lack structured mechanisms for ethical evaluation in professional contexts
- **Solution**: Constrain LLM generation using role-based ontologies and FIRAC structure
- **Architecture**: MCP server + Claude + pgvector + RDF ontologies
- **Evaluation**: Leave-one-out on 20 NSPE cases, expert panel review
- **Key Innovation**: Dual-layer similarity (embeddings + ontological relationships)

## Current Work Style
- **Iterative**: We work on sections out of order as needed
- **Flexible**: Plans change as insights emerge; tasks may cycle between states
- **Collaborative**: I help with writing, analysis, technical details, and planning
- **Progress-Oriented**: We track what's done but adapt the plan as we go

## Typical Session Pattern
1. Check current progress status in the planning document
2. Identify what we're working on today (may be any section/task)
3. Update progress tracking as we complete work
4. Note any insights or plan changes in the planning document

## Key Context to Maintain
- **Target Audience**: AI researchers, computational ethics community
- **Writing Style**: Academic but accessible, emphasizing practical contributions
- **Technical Depth**: Sufficient detail for reproducibility, but not implementation manual
- **Scope**: Engineering ethics as primary domain, but designed for generalizability

## Common Tasks I Help With
- Literature review and citation integration
- Technical writing and methodology description
- Results analysis and interpretation
- Editing and structure refinement
- Progress tracking and planning adjustments
- Figure/table creation and formatting

## Important Constraints
- Paper length limits (check venue requirements)
- Must maintain academic rigor while being accessible
- Technical claims must be supportable with evidence
- Ethical considerations must be thoughtfully addressed

## Quick Status Check Commands
When starting a session, ask me to:
1. "Check our current progress" - I'll review the progress tracking document
2. "What should we work on today?" - I'll suggest priorities based on current completion status
3. "Update progress for [task]" - I'll mark tasks complete and update tracking
4. "Review section status" - I'll provide detailed status of any specific section
5. "Check bibliography status" - I'll verify citation integration and bibliography completeness

## Last Session Notes
*This section should be updated each session with key decisions/insights*

**May 23, 2025**:
- ✅ Section 1 COMPLETED with full citation integration from LaTeX source
- ✅ Bibliography synchronized with Overleaf (ProEthica_References.bib)
- ✅ Comprehensive progress tracking system established
- ✅ Archive system implemented for version control
- 🎯 Next priorities: Section 2 consolidation, Section 3 integration
- 📊 Overall progress: ~25% complete (2/8 sections finalized)

---

**Instructions for Claude**: 
When this prompt is shared at the start of a new conversation, immediately:
1. Read the current outline and progress documents
2. Ask what we're working on today
3. Provide a brief status update on overall progress
4. Be ready to jump into any section or task as needed

Remember: This is collaborative academic writing with flexible priorities and iterative refinement.
