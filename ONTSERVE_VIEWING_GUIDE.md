# Viewing Committed Entities in OntServe Web Interface

## Where to Find Your Committed Entities at http://localhost:5003/

### 1. **Main Ontologies List** (http://localhost:5003/)
You will now see two new ontologies in the list:
- **proethica-intermediate-extracted** - Contains new classes extracted from cases
- **proethica-case-18** - Contains individual instances from Case 18

### 2. **Viewing Extracted Classes**
Navigate to: **http://localhost:5003/ontology/proethica-intermediate-extracted**

This will show:
- **TechnicalEvaluationReport** (subClassOf Resource)
- **WaterQualityStandards** (subClassOf Resource)
- Any other classes you've committed from extraction

You can also:
- Click **"View Content"** to see the raw TTL
- Click **"Visualize"** to see a graph representation
- Click **"Edit"** to modify the ontology

### 3. **Viewing Case Individuals**
Navigate to: **http://localhost:5003/ontology/proethica-case-18**

This will show:
- **EngineerB_WaterSource_EvaluationReport** (instance of TechnicalEvaluationReport)
- **EngineerB_PublicHealthRisk_Letter** (instance of TechnicalEvaluationReport)
- Any other individuals you've committed from the case

### 4. **Visualization Options**

#### Graph View
**http://localhost:5003/editor/ontology/proethica-intermediate-extracted/visualize**
- Shows class hierarchy with subClassOf relationships
- Interactive graph with zoom and pan

#### Content View
**http://localhost:5003/ontology/proethica-intermediate-extracted/content**
- Shows raw TTL content
- Useful for verifying exact RDF triples

### 5. **Search Functionality**
Use the search bar at the top of http://localhost:5003/ to find:
- Specific class names (e.g., "TechnicalEvaluationReport")
- Case ontologies (e.g., "case-18")
- Extracted ontologies (e.g., "extracted")

### 6. **Entity Details**
Once you click on an ontology, you'll see:
- **Classes Count**: Number of classes defined
- **Properties Count**: Number of properties
- **Individuals Count**: Number of instances (for case ontologies)
- **Triple Count**: Total RDF triples

### 7. **Relationship View**
In the visualization, you can see:
- **Blue nodes**: Classes
- **Green nodes**: Individuals
- **Arrows**: Relationships (subClassOf, rdf:type, custom properties)

### Troubleshooting

If entities don't appear:
1. Refresh the entity extraction:
   ```bash
   cd /home/chris/onto/OntServe
   python scripts/refresh_entity_extraction.py proethica-intermediate-extracted
   ```

2. Check the database:
   ```sql
   SELECT * FROM ontology_entities
   WHERE ontology_id IN (
     SELECT id FROM ontologies
     WHERE name LIKE '%extracted%' OR name LIKE '%case%'
   );
   ```

3. Restart the OntServe web server:
   ```bash
   cd /home/chris/onto/OntServe
   ./scripts/stop_services.sh
   ./scripts/start_services.sh
   ```

### Integration with ProEthica

The workflow is:
1. **Extract** entities in ProEthica (http://localhost:5000/)
2. **Review** at `/scenario_pipeline/case/N/entities/review`
3. **Commit** selected entities using "Commit Selected to OntServe"
4. **View** in OntServe at http://localhost:5003/

Committed entities show a green "Committed" badge in ProEthica's review interface.