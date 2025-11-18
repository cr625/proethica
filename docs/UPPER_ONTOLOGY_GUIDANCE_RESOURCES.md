# Upper Ontology Guidance for Resource vs. Reference Distinction

**Date**: 2025-10-07
**Question**: Can BFO, IAO, or PROV-O help distinguish Resources from References?

---

## Short Answer: YES - IAO is Perfect for This!

**IAO (Information Artifact Ontology) already provides exactly what we need:**

### Relevant IAO Classes

1. **`iao:0000300` - document**
   - An information content entity that is intended to be a self-sufficient unit of information
   - Examples: journal article, patent application, report
   - **Use for**: NSPE Code of Ethics, BER case precedents

2. **`iao:0000310` - document part**
   - A part of a document
   - **Use for**: Specific NSPE Code sections (II.4.a, III.4, etc.)

3. **`iao:0000119` - definition source** (annotation property)
   - Formal citation to indicate source(s)
   - **Use for**: Tracking which Code section was cited

4. **`iao:0000136` - is about** (object property)
   - Relates an information artifact to an entity
   - **Use for**: Linking conclusions to the entities they discuss

---

## Recommended Approach Using IAO

### Option 4 (NEW): Use IAO Document Hierarchy

**Better than our Option 3** because it uses established upper ontology:

```turtle
# NSPE Code is a document (IAO class)
:NSPE_Code a iao:0000300 ;  # document
    rdfs:label "NSPE Code of Ethics" ;
    dc:title "NSPE Code of Ethics" ;
    iao:0000136 :ProfessionalEthics .  # is about

# Specific code sections are document parts
:NSPE_II_4_a a iao:0000310 ;  # document part
    rdfs:label "NSPE Code Section II.4.a" ;
    bfo:0000050 :NSPE_Code ;  # part of (BFO relation)
    iao:0000219 "Engineers shall disclose all known or potential conflicts..." .  # has text value

# Resource can reference documents
proeth-core:Resource
    # Can have property: hasDocumentReference
    proeth:hasDocumentReference :NSPE_II_4_a .

# Or use existing IAO properties
proeth-case:EthicalConclusion
    iao:0000119 :NSPE_II_4_a .  # definition source (citation)
```

### Why This is Better

1. **Alignment with Upper Ontology**: Uses IAO's established document hierarchy
2. **No new classes needed**: `document` and `document part` already exist
3. **Standard properties**: `is about`, `definition source` are IAO standard
4. **BFO integration**: Uses `part of` (BFO relation)
5. **Research community**: IAO is widely used in biomedical and information science

---

## How This Solves Our Problem

### The Distinction

**Resources in Case Context** (Pass 1 - Facts/Discussion):
```turtle
# What engineers in the scenario have available
:NSPE_Code_Available a proeth-core:Resource ;
    rdfs:label "NSPE Code of Ethics" ;
    proeth:hasDocument :NSPE_Code ;  # links to IAO document
    proeth:availableTo :EngineerD ;
    proeth:extractedFromSection proeth-case:DiscussionSection .
```

**Citations in References Section** (Pass 1/2 - References):
```turtle
# What the BER explicitly cites
:BER_Citation_1 a iao:0000300 ;  # document (or use iao:citation if exists)
    iao:0000136 :NSPE_II_4_a ;  # is about this code section
    proeth:extractedFromSection proeth-case:ReferencesSection .

# Link conclusion to citation
:Conclusion_1 a proeth-case:EthicalConclusion ;
    iao:0000119 :NSPE_II_4_a .  # definition source (this is how BER justifies it)
```

### Key Insight

**We don't need `hasResourceFunction`**! Instead:

1. **Resources** (Pass 1) = What participants have
   - Modeled as `proeth-core:Resource` with `hasDocument` property

2. **Citations** (References section) = What BER cites
   - Modeled using IAO's `definition source` or similar citation property
   - Direct link from Conclusion/Principle to the cited document part

---

## PROV-O: Two Different Provenance Chains - Keep Separate!

**⚠️ CRITICAL DISTINCTION**: We use PROV-O for **TWO DIFFERENT purposes** - they must NOT be mixed:

### 1. Extraction Provenance (Current Use - Keep As Is)
**Tracks WHO extracted WHAT and WHEN** (computational process):
```turtle
# Our existing use - provenance of the AI extraction process
:ExtractionActivity_123 a prov:Activity ;
    prov:wasAssociatedWith :ClaudeAgent ;
    prov:used :DiscussionSectionText ;
    prov:generated :ExtractedPrinciple_1 ;
    prov:startedAtTime "2025-10-07T10:00:00Z" ;
    prov:endedAtTime "2025-10-07T10:05:00Z" .

:ExtractedPrinciple_1 a prov:Entity ;
    prov:wasGeneratedBy :ExtractionActivity_123 .
```

**Purpose**: Track the AI extraction workflow (auditing, debugging, reproducibility)

### 2. Document Provenance (New Use - Different Namespace!)
**Tracks WHERE the BER's reasoning came from** (intellectual content):
```turtle
# New use - provenance of the Board's ethical reasoning
:BER_Conclusion_1 a proeth-case:EthicalConclusion ;
    # DO NOT USE prov:wasDerivedFrom here - that's for extraction!
    # Instead use IAO citation properties:
    iao:0000119 :NSPE_II_4_a .  # definition source (authority cited)
```

**Purpose**: Track the intellectual citations in the BER's analysis

### Why Keeping Them Separate is Critical

| Aspect | Extraction Provenance | Document Provenance |
|--------|---------------------|---------------------|
| **What** | AI agent extracted an entity | BER cited a code section |
| **Who** | Claude/Gemini LLM | Board of Ethical Review |
| **When** | 2025-10-07 10:00 | Written in the case (historical) |
| **Purpose** | Audit AI process | Track reasoning authority |
| **Properties** | `prov:wasGeneratedBy` | `iao:0000119` (definition source) |

**If we mix them**: We can't distinguish "this was extracted by AI" from "this cites Code II.4.a"

**Solution**:
- ✅ **PROV-O** = Extraction provenance ONLY
- ✅ **IAO properties** = Document citations and authority

---

## Recommended Implementation

### Approach: IAO for Documents + Citations (NOT PROV-O for citations!)

```turtle
# 1. NSPE Code as IAO document
:NSPE_Code a iao:0000300 ;  # document
    dc:title "NSPE Code of Ethics" ;
    dc:publisher "National Society of Professional Engineers" .

:NSPE_II_4_a a iao:0000310 ;  # document part
    bfo:0000050 :NSPE_Code ;  # part of
    dc:title "Section II.4.a - Conflict Disclosure" ;
    iao:0000219 "Engineers shall disclose all known or potential conflicts..." .  # has text value

# 2. Resource (Pass 1 - available to case participants)
:NSPE_Code_Resource a proeth-core:Resource ;
    rdfs:label "NSPE Code of Ethics" ;
    proeth:refersToDocument :NSPE_Code ;
    proeth:availableTo :EngineerD ;
    proeth:extractedFromSection proeth-case:DiscussionSection .

# 3. Citation (References section - BER authority)
:BER_Conclusion_1 a proeth-case:EthicalConclusion ;
    rdfs:label "Engineer D must disclose conflicts" ;
    iao:0000119 :NSPE_II_4_a ;  # definition source (IAO - NOT prov:wasDerivedFrom!)
    proeth:extractedFromSection proeth-case:ConclusionSection .

# 4. References section extraction creates citation links
:RefSection_Resource_1 a proeth-core:Resource ;
    rdfs:label "NSPE Code Section II.4.a" ;
    proeth:refersToDocument :NSPE_II_4_a ;
    proeth:citedByAgent :BoardOfEthicalReview ;  # who cited it
    proeth:extractedFromSection proeth-case:ReferencesSection .

# 5. PROV-O stays for EXTRACTION provenance only
:ExtractionActivity_Conclusion a prov:Activity ;
    prov:wasAssociatedWith :ClaudeAgent ;
    prov:generated :BER_Conclusion_1 ;  # AI extracted this
    prov:used :ConclusionSectionText .  # from this text
```

---

## Implementation Changes

### What to Add to proethica-core.ttl

```turtle
# Link Resource to IAO documents
proeth-core:refersToDocument a owl:ObjectProperty ;
    rdfs:domain proeth-core:Resource ;
    rdfs:range iao:0000300 ;  # document
    rdfs:label "refers to document" ;
    rdfs:comment "Links a resource to the document it represents" .

proeth-core:availableTo a owl:ObjectProperty ;
    rdfs:domain proeth-core:Resource ;
    rdfs:range proeth-core:Role ;  # available to agents in roles
    rdfs:label "available to" ;
    rdfs:comment "Indicates which agent(s) have access to this resource" .

proeth-core:citedBy a owl:ObjectProperty ;
    rdfs:domain proeth-core:Resource ;
    rdfs:range proeth-core:Role ;  # cited by BER (analyst role)
    rdfs:label "cited by" ;
    rdfs:comment "Indicates which agent(s) cited this resource as authority" .
```

### What IAO/PROV-O Provides Already

**No need to create**:
- ✅ `iao:0000300` (document)
- ✅ `iao:0000310` (document part)
- ✅ `iao:0000119` (definition source) - for citations
- ✅ `iao:0000136` (is about)
- ✅ `prov:wasDerivedFrom` - for provenance
- ✅ `bfo:0000050` (part of)

---

## Benefits of This Approach

1. **Standards Compliant**: Uses IAO (OBO Foundry) and PROV-O (W3C)
2. **No Reinvention**: Leverages existing, well-tested ontology classes
3. **Interoperability**: Other systems using IAO can understand our data
4. **Clear Distinction**:
   - Resources link to documents (`refersToDocument`)
   - Conclusions cite documents (`iao:0000119` or `prov:wasDerivedFrom`)
5. **Provenance Built-in**: PROV-O tracks reasoning chain
6. **Research Ready**: IAO is standard in scholarly knowledge representation

---

## Next Steps

1. ✅ Review this analysis
2. ⏳ Decide: IAO+PROV-O approach vs. custom ResourceFunction
3. ⏳ If approved, add IAO document references to proethica-core
4. ⏳ Update Resource extractor to use `refersToDocument`
5. ⏳ Implement References section with IAO citation properties
6. ⏳ Update PROV-O tracking to include document provenance

---

## Recommendation

**Use Option 4 (IAO+PROV-O)** instead of Option 3 (custom ResourceFunction) because:
- Aligns with established standards
- No need to create new classes
- Better interoperability
- Clearer semantic model
- Already using BFO+IAO in proethica-core

**Your observation was spot-on** - the upper ontologies already solved this problem!
