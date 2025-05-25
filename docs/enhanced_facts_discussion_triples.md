# Enhanced Facts and Discussion Triple Generation

## Overview

We've enhanced the document structure annotation to break down Facts and Discussion sections into individual semantic units, following the same pattern used for Questions, Conclusions, and References.

## Implementation Details

### Facts Section Enhancement

**Before**: Facts were stored as a single text block
```turtle
<case_uri/facts> a proethica:FactsSection ;
    proethica:hasTextContent "All facts in one block..." .
```

**After**: Facts are broken into individual statements
```turtle
<case_uri/facts> a proethica:FactsSection ;
    proethica:hasTextContent "All facts..." ;
    proethica:hasPart <case_uri/fact_1>, <case_uri/fact_2> .

<case_uri/fact_1> a proethica:FactStatement ;
    proethica:hasTextContent "Engineer C is the owner of a single-engineer consulting firm." ;
    proethica:hasSequenceNumber 1 ;
    proethica:isPartOf <case_uri/facts> .

<case_uri/fact_2> a proethica:FactStatement ;
    proethica:hasTextContent "He was recently diagnosed with a medical condition." ;
    proethica:hasSequenceNumber 2 ;
    proethica:isPartOf <case_uri/facts> .
```

### Discussion Section Enhancement

**Before**: Discussion was stored as a single HTML block
```turtle
<case_uri/discussion> a proethica:DiscussionSection ;
    proethica:hasTextContent "<p>All discussion paragraphs...</p>" .
```

**After**: Discussion is broken into semantic segments
```turtle
<case_uri/discussion> a proethica:DiscussionSection ;
    proethica:hasTextContent "Full discussion..." ;
    proethica:hasPart <case_uri/discussion_segment_1>, <case_uri/discussion_segment_2> .

<case_uri/discussion_segment_1> a proethica:DiscussionSegment ;
    proethica:hasTextContent "As licensed professionals, engineers have a duty..." ;
    proethica:hasSegmentType "ethical_analysis" ;
    proethica:hasSequenceNumber 1 ;
    proethica:isPartOf <case_uri/discussion> .

<case_uri/discussion_segment_2> a proethica:DiscussionSegment ;
    proethica:hasTextContent "However, the engineer also has privacy rights..." ;
    proethica:hasSegmentType "reasoning" ;
    proethica:hasSequenceNumber 2 ;
    proethica:isPartOf <case_uri/discussion> .
```

## Extraction Logic

### Fact Statement Extraction
- Removes HTML tags
- Splits on sentence boundaries (periods followed by capital letters)
- Combines related sentences (those starting with pronouns)
- Preserves logical groupings of related facts

### Discussion Segment Extraction
- Splits on HTML paragraph boundaries
- Classifies each segment by type:
  - **ethical_analysis**: Contains ethical terms (duty, obligation, responsibility)
  - **reasoning**: Contains logical connectors (however, therefore, because)
  - **code_reference**: References specific codes or standards
  - **general**: Default for other content

## Display in UI

The enhanced structure integrates seamlessly with the combined Structure Triples viewer:

### Facts Section Display
```
Facts
─────
fact_1    Fact    http://proethica.org/document/case_21_4/fact_1
Engineer C is the owner of a single-engineer consulting firm.

fact_2    Fact    http://proethica.org/document/case_21_4/fact_2
He was recently diagnosed with a medical condition that requires ongoing treatment.
```

### Discussion Section Display
```
Discussion
──────────
discussion_segment_1    Discussion Point    [ethical_analysis]    http://proethica.org/document/case_21_4/discussion_segment_1
As licensed professionals, engineers have a duty to their clients and the public to perform at their best...

discussion_segment_2    Discussion Point    [reasoning]    http://proethica.org/document/case_21_4/discussion_segment_2
However, the engineer also has privacy rights and may not need to disclose specific medical details...
```

## Benefits

1. **Granular Similarity Search**: Can find cases with similar specific facts or ethical reasoning
2. **Better LLM Context**: LLMs can reference specific facts or arguments
3. **Consistent Structure**: All sections now follow the same pattern
4. **Semantic Classification**: Discussion segments are typed for better querying
5. **Preserved Order**: Sequence numbers maintain narrative flow

## Future Enhancements

1. **Smarter Fact Grouping**: Use NLP to better identify related facts
2. **More Segment Types**: Add types like "precedent", "stakeholder_analysis", etc.
3. **Cross-References**: Link discussion segments to specific facts they analyze
4. **Extraction Confidence**: Add confidence scores for segment classification