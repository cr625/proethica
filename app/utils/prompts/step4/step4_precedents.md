---
{
  "name": "Step 4 Precedent Case Reference Extraction",
  "description": "Phase 2B: identifies prior BER cases cited by the board, with citation treatment terms. The treatment block is built at render time from CITATION_TREATMENTS (precedents.py), which tests/unit/test_precedent_vocabulary.py binds to the proethica-cases.ttl CitationTreatment skos:definitions.",
  "phase": "2B",
  "extractor_file": "app/routes/scenario_pipeline/step4/precedents.py",
  "prompt_method": "build_precedent_prompt",
  "output_schema": {
    "type": "array",
    "items": {
      "caseCitation": "string, citation exactly as it appears in the text",
      "caseNumber": "string, normalized case number, exactly one per entry",
      "citationContext": "string, 1-2 sentences on why the board cited the case",
      "citationType": "supporting | distinguishing | analogizing | overruling",
      "principleEstablished": "string, holding or precedent the cited case establishes",
      "relevantExcerpts": [
        {
          "section": "facts | discussion | question | conclusion",
          "text": "string, exact passage up to 200 characters"
        }
      ]
    }
  },
  "variable_builders": {
    "case_text": {
      "description": "All case sections concatenated with === SECTION === headers",
      "source": "caller (doc_metadata sections_dual: facts, discussion, question, conclusion)"
    },
    "citation_treatments_block": {
      "description": "Indented treatment-term lines built from the CITATION_TREATMENTS dict",
      "source": "_treatments_block() in precedents.py (ontology-drift-tested dict stays in code)"
    }
  }
}
---
You are analyzing an ethics case from the NSPE Board of Ethical Review (BER).
Identify ALL prior cases, decisions, or rulings cited by the board in their discussion.

CASE TEXT:
{{ case_text }}

For each cited case, extract:
1. caseCitation: The exact citation as it appears in the text (e.g., "BER Case 94-8", "Case No. 85-3")
2. caseNumber: Normalized case number (e.g., "94-8", "85-3"). EXACTLY ONE case number
   per entry: when the board cites several cases jointly ("Cases 65-9 and 73-9"),
   emit one entry per case, repeating the shared context.
3. citationContext: A 1-2 sentence summary of WHY the board cited this case -- what point it supports
4. citationType: One of the following treatment terms, by the board's actual use of the citation:
{{ citation_treatments_block }}
5. principleEstablished: The key principle, holding, or precedent that the cited case establishes
6. relevantExcerpts: Array of objects with "section" (facts/discussion/question/conclusion) and "text" (the exact passage where the citation appears, up to 200 characters)

Return a JSON array. If no prior cases are cited, return an empty array [].

Example output:
[
  {
    "caseCitation": "BER Case 94-8",
    "caseNumber": "94-8",
    "citationContext": "The Board cited this case to establish that engineers must have an objective basis to assess another engineer's competency before delegating work.",
    "citationType": "supporting",
    "principleEstablished": "Engineers must verify that colleagues have sufficient education, experience, and training before delegating professional responsibilities.",
    "relevantExcerpts": [
      {"section": "discussion", "text": "In BER Case 94-8, Engineer A, a professional engineer, was working with..."}
    ]
  }
]

Respond ONLY with the JSON array, no other text.
