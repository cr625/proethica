# NSPE Ethics Cases Import

This document provides an overview of the NSPE cases import process and the extension of the engineering ethics ontology.

## Overview

The National Society of Professional Engineers (NSPE) provides a rich collection of ethics cases that illustrate various ethical dilemmas faced by professional engineers. These cases are valuable resources for the Engineering Ethics world in ProEthica.

This project includes several scripts to:
1. Import NSPE ethics cases into the Engineering Ethics world
2. Fix existing case metadata (URLs and titles)
3. Remove incorrectly imported cases
4. Extend the engineering ethics ontology with concepts from these cases

## Scripts

### 1. `process_nspe_cases.py`

This is the main orchestrator script that runs all the necessary steps in sequence:

```bash
python process_nspe_cases.py [world_id]
```

Where `world_id` is optional and defaults to 1 (Engineering Ethics world).

### 2. `remove_incorrect_nspe_cases.py`

Removes cases with incorrect titles like "Preamble, I.r II.1. 1.2." and those with "Pre Header Utility Links" content that were imported incorrectly.

```bash
python remove_incorrect_nspe_cases.py [world_id]
```

### 3. `fix_nspe_case_imports.py`

Fixes URLs and titles for existing NSPE cases, ensuring they use the correct URL format and have descriptive titles.

```bash
python fix_nspe_case_imports.py [world_id]
```

### 4. `import_missing_nspe_cases.py`

Imports missing NSPE cases from the correct URLs, extracting their content and creating case documents in the database.

```bash
python import_missing_nspe_cases.py [world_id]
```

### 5. `extend_nspe_engineering_ontology.py`

Extends the engineering ethics ontology with new concepts derived from the NSPE cases:

```bash
python extend_nspe_engineering_ontology.py [output_path]
```

## Ontology Extensions

The engineering ethics ontology has been extended with the following new concepts:

### Engineering Roles
- City Engineer Role
- Peer Reviewer Role
- Design-Build Engineer Role
- State Engineer Role

### Engineering Conditions
- Climate Change Condition
- Water Quality Condition
- Stormwater Runoff Condition
- Impaired Practice Condition
- Competence Deficiency Condition

### Engineering Ethical Dilemmas
- Conflict of Interest Dilemma
- Public Safety vs Resource Constraints Dilemma
- Professional Responsibility Dilemma

### Engineering Resources
- As-Built Drawings
- Plan Review
- Building Permit

### Engineering Ethical Principles
- Disclosure Principle
- Objectivity Principle
- Independence Principle
- Good Samaritan Principle
- Professional Responsibility Principle
- Design Responsibility Principle
- Continuing Education Principle
- Peer Review Principle
- Qualifications Principle
- Fair Compensation Principle
- Gifts Principle

## Case URLs

The following NSPE ethics case URLs have been imported:

```
https://www.nspe.org/career-resources/ethics/post-public-employment-city-engineer-transitioning-consultant
https://www.nspe.org/career-resources/ethics/excess-stormwater-runoff
https://www.nspe.org/career-resources/ethics/competence-design-services
https://www.nspe.org/career-resources/ethics/providing-incomplete-self-serving-advice
https://www.nspe.org/career-resources/ethics/independence-peer-reviewer
https://www.nspe.org/career-resources/ethics/impaired-engineering
https://www.nspe.org/career-resources/ethics/professional-responsibility-if-appropriate-authority-fails-act
https://www.nspe.org/career-resources/ethics/review-other-engineer-s-work
https://www.nspe.org/career-resources/ethics/sharing-built-drawings
https://www.nspe.org/career-resources/ethics/unlicensed-practice-nonengineers-engineer-job-titles
https://www.nspe.org/career-resources/ethics/public-welfare-what-cost
https://www.nspe.org/career-resources/ethics/misrepresentation-qualifications
https://www.nspe.org/career-resources/ethics/good-samaritan-laws
https://www.nspe.org/career-resources/ethics/public-safety-health-welfare-avoiding-rolling-blackouts
https://www.nspe.org/career-resources/ethics/internal-plan-reviews-vsthird-party-peer-reviews-duties
https://www.nspe.org/career-resources/ethics/conflict-interest-designbuild-project
https://www.nspe.org/career-resources/ethics/offer-free-or-reduced-fee-services
https://www.nspe.org/career-resources/ethics/public-health-safety-welfare-climate-change-induced-conditions
https://www.nspe.org/career-resources/ethics/equipment-design-certification-plan-stamping
https://www.nspe.org/career-resources/ethics/gifts-mining-safety-boots
https://www.nspe.org/career-resources/ethics/public-health-safety-welfare-drinking-water-quality
https://www.nspe.org/career-resources/ethics/conflict-interest-pes-serving-state-licensure-boards
```

## Ontology Size

The extended engineering ethics ontology remains manageable in size while providing comprehensive coverage of the concepts needed to represent the NSPE ethics cases. The new entities have been carefully designed to integrate with the existing ontology structure.

The new ontology is saved to `mcp/ontology/engineering-ethics-nspe-extended.ttl`.
