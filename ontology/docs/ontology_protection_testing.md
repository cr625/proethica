# Testing Base Ontology Protection

This document explains how to verify that base ontologies (like BFO) are protected from editing while still allowing them to be viewed and used as imports by other ontologies.

## 1. Testing Through the API

You can directly test the API protection using curl commands:

```bash
# Try to update a protected ontology (BFO, ID=2)
curl -X PUT -d "Updated content" -H "Content-Type: application/json" http://localhost:3333/ontology-editor/api/ontology/2/content

# Expected result: Error message about ontology not being editable
# {"error": "Ontology 2 is not editable"}

# For comparison, try to update a non-protected ontology (ID=1) 
# (This will fail with validation error, not permission error)
curl -X PUT -d "Valid TTL content" -H "Content-Type: application/json" http://localhost:3333/ontology-editor/api/ontology/1/content
```

The key difference is that protected ontologies will return a specific "not editable" error, while non-protected ontologies will proceed to content validation.

## 2. Testing Through the Web Interface

To test protection in the web interface:

1. Start the application:
   ```bash
   ./start_proethica.sh
   ```

2. Navigate to the ontology editor in your browser:
   ```
   http://localhost:3333/ontology-editor
   ```

3. Test protected ontologies:
   - Select the "Basic Formal Ontology" or "ProEthica Intermediate Ontology" from the list
   - The editor should display the content in read-only mode
   - The "Save" button should be disabled or show a message indicating the ontology is not editable
   - You may see a visual indicator (like a lock icon) showing the ontology is protected

4. Test non-protected ontologies:
   - Select the "Engineering Ethics Nspe Extended" ontology
   - The editor should allow you to modify the content
   - The "Save" button should be enabled and functional

## 3. Verifying Database Flags Directly

You can verify the protection status directly in the database:

```bash
# Run the check script to see ontology status
./scripts/check_ontologies_in_db.py

# Expected output showing is_base and is_editable status:
# ID=1, Name=Engineering Ethics Nspe Extended, Domain=engineering-ethics-nspe-extended, Base: False, Editable: True
# ID=2, Name=Basic Formal Ontology, Domain=bfo, Base: True, Editable: False
# ID=3, Name=ProEthica Intermediate Ontology, Domain=proethica-intermediate, Base: True, Editable: False
```

You can also use the PostgreSQL command line to query directly:

```bash
# Connect to the database (adjust connection details as needed)
psql -h localhost -p 5433 -U postgres -d ai_ethical_dm

# Run query to check protection flags
SELECT id, name, domain_id, is_base, is_editable FROM ontologies;
```

## 4. How the Protection Works

The protection system works at three levels:

1. **Database Level**: The `is_base` and `is_editable` flags in the `ontologies` table control which ontologies can be modified.

2. **API Level**: The API endpoints check the `is_editable` flag before allowing updates:
   ```python
   # In ontology_editor/api/routes.py
   if hasattr(ontology, 'is_editable') and not ontology.is_editable:
       return jsonify({'error': f'Ontology {ontology_id} is not editable'}), 403
   ```

3. **UI Level**: The web interface disables editing capabilities for protected ontologies.

This multi-level protection ensures that base ontologies cannot be accidentally modified, maintaining system integrity while still allowing them to be used as a foundation for domain-specific ontologies.
