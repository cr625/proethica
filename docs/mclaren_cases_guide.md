# NSPE Ethics Case Studies Guide

This document provides an overview of the ethics case studies available in the AI-Ethical-DM system, including both historical cases referenced in McLaren's 2003 paper and modern cases from the NSPE Board of Ethical Review (BER).

## Overview

The AI-Ethical-DM system includes two collections of professional engineering ethics case studies:

1. **Historical McLaren Cases**: A set of landmark cases analyzed in McLaren's 2003 paper on extensional definition of ethical principles. These cases established important precedents and frameworks for ethical decision-making in engineering.

2. **Modern NSPE Cases**: Recent cases from the NSPE Board of Ethical Review that address contemporary ethical challenges in engineering practice, including technological advances, changing professional standards, and evolving societal expectations.

Both collections are structured with rich metadata including ethical principles, related cases, operationalization techniques, and board analyses, making them valuable resources for ethical reasoning and decision-making in the ProEthica system.

## The McLaren 2003 Paper

Bruce McLaren's 2003 paper, "Extensionally Defining Principles and Cases in Ethics: An AI Model," presented a computational approach to ethical reasoning by analyzing how principles are operationalized in real engineering ethics cases. McLaren extracted relationships between cases and ethical principles from NSPE BER cases, identifying patterns of reasoning such as:

- **Principle Instantiation**: How abstract principles are applied to specific situations
- **Case Instantiation**: How precedent cases influence decisions in new cases
- **Conflicting Principles Resolution**: How tensions between competing principles are resolved
- **Case Grouping**: How cases are categorized based on similar ethical issues

These operationalization techniques form the foundation of how the AI-Ethical-DM system represents and reasons about ethical dilemmas.

## Modern NSPE Cases

The modern cases complement the historical McLaren cases by providing contemporary examples that address current ethical challenges in engineering practice:

- **Case 23-4: Acknowledging Errors in Design** - Explores the ethical obligations of engineers to acknowledge design errors when construction safety risks affect workers, highlighting tensions between professional standards and ethical obligations.

- **Case 22-10: Serving as Both Engineer and Building Official** - Examines conflicts of interest when an engineer reviews their own work in an official capacity, highlighting the importance of maintaining objectivity and independent professional judgment.

- **Case 22-5: Duty to Report Unsafe Conditions** - Addresses when an engineer's duty to protect public safety overrides client confidentiality, particularly when there is imminent danger.

These modern cases have been enriched with the same metadata structure as the McLaren cases, allowing for consistent analysis and comparison.

## Using the Case Viewer Tools

The AI-Ethical-DM system provides comprehensive tools for exploring and analyzing ethics cases:

### View and Search Case Studies

Use the `view_mclaren_cases.py` script to interact with both historical and modern cases:

```bash
# List all cases (both historical and modern)
python3 scripts/view_mclaren_cases.py list

# View only historical McLaren cases
python3 scripts/view_mclaren_cases.py list --historical-only

# View only modern NSPE cases
python3 scripts/view_mclaren_cases.py list --modern-only

# View detailed information about a specific case
python3 scripts/view_mclaren_cases.py view "Case 22-5"

# Find cases related to a specific case
python3 scripts/view_mclaren_cases.py related "Case 23-4"

# Search for cases by keyword
python3 scripts/view_mclaren_cases.py search "safety"

# Find cases using a specific operationalization technique
python3 scripts/view_mclaren_cases.py op-technique "Conflicting Principles Resolution"

# Find cases involving a specific ethical principle
python3 scripts/view_mclaren_cases.py principle "confidentiality"

# Show examples of an operationalization technique
python3 scripts/view_mclaren_cases.py examples "Case Instantiation"
```

### Fetch Modern NSPE Cases

The system includes a script for fetching and processing modern NSPE Board of Ethical Review cases:

```bash
# Fetch modern cases and save to data/modern_nspe_cases.json
python3 scripts/fetch_modern_nspe_cases.py --fetch-only

# Add cases to the Engineering Ethics world in the database
python3 scripts/fetch_modern_nspe_cases.py --world-id 2

# Filter cases by year
python3 scripts/fetch_modern_nspe_cases.py --year 2022

# Limit the number of cases to fetch
python3 scripts/fetch_modern_nspe_cases.py --max-cases 5

# Fetch without processing embeddings
python3 scripts/fetch_modern_nspe_cases.py --no-embeddings
```

## Integration with ProEthica

The ethics cases are integrated with the ProEthica system to enhance ethical reasoning in simulations:

1. **Reference Material**: Cases serve as reference material that agents can query when facing ethical dilemmas in simulations.

2. **Precedent-Based Reasoning**: The system can identify similar past cases to help guide decision-making in new scenarios.

3. **Principle Identification**: The rich metadata allows the system to identify which ethical principles are relevant to a given situation.

4. **Reasoning Patterns**: Operationalization techniques from the cases demonstrate how to apply abstract principles to concrete situations.

5. **Simulated Board Analysis**: The system can generate board-style analyses for new ethical dilemmas based on patterns observed in historical and modern cases.

## Extending the Case Library

The case library can be extended with additional modern cases:

1. Use the `fetch_modern_nspe_cases.py` script to automatically retrieve cases from the NSPE website.

2. Manual curation and enrichment can be done by editing the JSON files in the `data` directory.

3. Custom case studies can be added by following the metadata format used in the existing cases.

## Conclusion

The combination of historical McLaren cases and modern NSPE cases provides a comprehensive resource for ethical reasoning in engineering contexts. By analyzing these cases, users can gain insights into how ethical principles are operationalized in practice and develop a deeper understanding of professional ethics in engineering.
