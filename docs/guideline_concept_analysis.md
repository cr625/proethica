# Engineering Ethics Guideline Concept Analysis

This document analyzes the concepts extracted from Engineering Ethics guideline (ID 43) and maps them to existing or potential classes in our ontologies.

## Concept Grouping and Classification

### Core Ethical Principles

| Guideline Concept | Description | Category | Existing Ontology Match | Domain | Notes |
|-------------------|-------------|----------|-------------------------|--------|-------|
| public-safety-primacy | The principle that engineers must prioritize public safety, health, and welfare above all other considerations | core ethical principle | :PublicSafetyPrinciple, :NSPEPublicSafetyPrinciple | Engineering-specific | This is a fundamental principle in engineering ethics |
| professional-integrity | The commitment to honesty, ethical conduct, and avoiding deceptive practices | core ethical principle | None directly | Domain-general | This could be a proethica-intermediate class |

### Professional Obligations

| Guideline Concept | Description | Category | Existing Ontology Match | Domain | Notes |
|-------------------|-------------|----------|-------------------------|--------|-------|
| professional-competence | The obligation for engineers to only perform work within their areas of expertise | professional obligation | :CompetencyPrinciple, :NSPECompetencyPrinciple | Engineering-specific | Already exists in engineering-ethics |
| confidentiality | The obligation to protect and not disclose confidential information obtained during professional service | professional obligation | :ConfidentialityPrinciple, :NSPEConfidentialityPrinciple | Engineering-specific | Already exists in engineering-ethics |
| fiduciary-duty | The obligation for engineers to act as faithful agents or trustees for their employers or clients | professional relationship | None directly | Engineering-specific | New concept for engineering-ethics |

### Communication Ethics

| Guideline Concept | Description | Category | Existing Ontology Match | Domain | Notes |
|-------------------|-------------|----------|-------------------------|--------|-------|
| truthfulness | The requirement for engineers to communicate honestly and objectively | communication ethics | :HonestyPrinciple | Domain-general | Could enhance proethica-intermediate |

### Professional Ethics

| Guideline Concept | Description | Category | Existing Ontology Match | Domain | Notes |
|-------------------|-------------|----------|-------------------------|--------|-------|
| conflict-of-interest | The ethical issue arising when personal interests could compromise professional judgment | professional ethics | :ConflictOfInterestDilemma | Engineering-specific | Similar concept exists but needs enhancement |
| professional-accountability | The principle that engineers must take responsibility for their professional actions and decisions | professional responsibility | None directly | Engineering-specific | New concept for engineering-ethics |
| public-interest-service | The obligation for engineers to serve the broader public interest through their professional work | None specified | None directly | Engineering-specific | New concept for engineering-ethics |
| intellectual-property-respect | The ethical requirement to properly credit others' work and respect proprietary rights | None specified | None directly | Domain-general | Could be added to proethica-intermediate |

## Ontology Integration Strategy

### For engineering-ethics.ttl

1. **Enhance existing classes**:
   - Add more descriptive rdfs:comment fields
   - Add hasCategory, relatedTo, and hasTextReference properties from guideline concepts
   - Ensure proper hierarchy with proethica-intermediate.ttl

2. **Add new engineering-specific classes**:
   - ProfessionalAccountabilityPrinciple
   - FiduciaryDutyPrinciple
   - PublicInterestServicePrinciple

### For proethica-intermediate.ttl

1. **Add domain-general classes**:
   - ProfessionalIntegrityPrinciple (under EthicalPrinciple)
   - IntellectualPropertyRespectPrinciple (under EthicalPrinciple)

2. **Enhance class definitions**:
   - Add semantic matching properties

## Concept URI Normalization

The guideline concepts use two different URI formats:
- With underscores: http://proethica.org/guidelines/public_safety_primacy
- With hyphens: http://proethica.org/guidelines/public-safety-primacy

The hyphenated versions include additional properties (hasCategory, relatedTo, hasTextReference). We will standardize on the CamelCase format for class names in the ontology.

## Formulaic Prefix Removal

The descriptions in the guideline concepts use formulaic prefixes that should be removed:
- "The principle that..." → Direct statement
- "The obligation for..." → Direct statement
- "The requirement for..." → Direct statement

This will make the descriptions more concise and effective for semantic matching.
