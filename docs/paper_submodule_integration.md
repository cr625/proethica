# ISWC 2025 Paper Submodule Integration

## Overview

The ProEthica project includes integration with a research paper repository targeting the International Semantic Web Conference (ISWC) 2025. This paper documents the ontology editor component of ProEthica, specifically focusing on semantic web technologies used within the application.

## Submodule Details

- **Repository**: https://github.com/cr625/ISWC_2025
- **Local Path**: `papers/ISWC_2025/`
- **Purpose**: Academic documentation of the ontology editor component
- **Conference Target**: [ISWC 2025](https://iswc2025.semanticweb.org/#/calls/research)

## Workflow for Updating Paper Content

When significant improvements are made to the ontology editor component, the paper content should be updated to reflect these changes:

1. **Document implementation details** in the main ProEthica repository
2. **Navigate to the paper submodule**:
   ```bash
   cd papers/ISWC_2025
   ```
3. **Make changes to the LaTeX files** to document the improvements
4. **Commit and push the changes** to the paper repository:
   ```bash
   git add .
   git commit -m "Update with latest ontology editor improvements"
   git push origin main
   ```
5. **Update the submodule reference** in the main repository:
   ```bash
   cd ../../  # Return to main repository root
   git add papers/ISWC_2025  # This adds the updated submodule reference
   git commit -m "Update ISWC paper to reflect latest ontology editor improvements"
   git push
   ```

## Paper Organization

The ISWC 2025 paper content is organized using the ACM conference format:

- `sigconf-anon.tex` - Main LaTeX document
- `references.bib` - Bibliography file
- `software-references.bib` - Software-specific references
- `acmart.cls` and other `.bbx`/`.cbx` files - LaTeX style and formatting

## Key Topics to Document

When updating the paper, focus on documenting:

1. **Ontology Editor Architecture** - Technical design of the editor component
2. **Semantic Web Technologies** - RDF, OWL, SPARQL, and other semantic technologies used
3. **User Interaction Design** - How users interact with ontology concepts
4. **Integration with LLMs** - How Claude and other LLMs interact with the ontology
5. **Evaluation & Results** - Performance and usability metrics of the ontology editor
6. **Future Directions** - Planned improvements and research directions

## Building the Paper

After making changes, you may want to build the PDF to verify the paper formatting:

```bash
cd papers/ISWC_2025
pdflatex sigconf-anon
bibtex sigconf-anon
pdflatex sigconf-anon
pdflatex sigconf-anon
```

This will generate `sigconf-anon.pdf` with your updated content.

## Related Documentation

- See [CLAUDE.md](../CLAUDE.md) for a history of significant improvements to the project
- See [docs/ontology_comprehensive_guide.md](ontology_comprehensive_guide.md) for details about the ontology system
- See [docs/ontology_editor/README.md](../ontology_editor/README.md) for ontology editor documentation
