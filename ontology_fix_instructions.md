# Ontology Syntax Error Fix Instructions

## Problem Overview

We've identified that the ontology with ID 1 (domain_id: `engineering-ethics-nspe-extended`) in the database has syntax errors in its Turtle (TTL) format. These errors prevent the MCP server from properly parsing it, which is why no entities are showing up in the world details page.

## Specific Errors Found

The following syntax errors were detected:
1. A missing semicolon after `rdfs:label "Engineering Capability"@en`
2. Newlines inside string literals: `"Engineering ;\n Ethics Ontology"@en`
3. Possibly other Turtle syntax issues that need manual correction

## Solution: Export, Fix, and Re-import

We've created a script to help you export the ontology from the database, fix the syntax issues, and re-import it.

### How to Use the Script

1. Run the script:
   ```bash
   ./export_fix_import_ontology.py
   ```

2. The script will:
   - Export the ontology with ID 1 from the database to a temporary file
   - Validate the file and report any syntax issues
   - Open the file in your default text editor for manual editing
   - Validate your fixes
   - Import the fixed ontology back into the database if it passes validation

3. When editing the file, look for:
   - Missing semicolons between property-value pairs
   - Newlines inside string literals (should not have newlines in quotes)
   - Missing periods at the end of statement blocks
   - Any other syntax issues reported by the validator

### Common Turtle Syntax Rules

1. Each subject-predicate-object statement must end with either:
   - A semicolon (`;`) if followed by more statements about the same subject
   - A period (`.`) if it's the last statement about that subject

2. String literals should be enclosed in quotes and should not contain newlines

3. A typical pattern looks like:
   ```
   <subject> 
       <predicate1> <object1> ;
       <predicate2> <object2> ;
       <predicate3> <object3> .
   ```

4. For labels and comments:
   ```
   rdfs:label "This is a label"@en ;
   rdfs:comment "This is a comment"@en .
   ```

### After Fixing

After the ontology has been fixed and reimported, you should:

1. Restart the ProEthica service to ensure the changes take effect:
   ```bash
   ./restart_server.sh
   ```

2. Visit the world details page to verify that entities are now showing up properly:
   ```
   http://localhost:3333/worlds/1
   ```

If the ontology editor still shows syntax errors after fixing, you may need to check if the editor is using its own validation logic that's different from the RDFLib parser.
