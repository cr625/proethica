#!/usr/bin/env python3
"""
Enrich Ontology Definitions - Generate professional definitions for ontology concepts using LLM.

This script addresses the issue where all 124 entities in proethica-intermediate 
have empty definitions, making contextual annotation impossible.
"""

import os
import sys
import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Set up environment
os.environ.setdefault('SQLALCHEMY_DATABASE_URI', 'postgresql://proethica_user:proethica_development_password@localhost:5432/ai_ethical_dm')
os.environ.setdefault('ONTSERVE_DB_URL', 'postgresql://ontserve_user:ontserve_development_password@localhost:5432/ontserve')

@dataclass
class ConceptEnrichment:
    """Result of concept definition enrichment."""
    uri: str
    label: str
    original_comment: Optional[str]
    generated_definition: str
    skos_definition: str
    confidence: float
    reasoning: str

class OntologyEnricher:
    """LLM-powered ontology concept definition generator."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.batch_size = 10  # Process concepts in batches
        
    def get_llm_client(self):
        """Get LLM client using ProEthica's utility."""
        try:
            # Need to be in Flask app context
            from app import create_app
            from app.utils.llm_utils import get_llm_client
            
            # Check if we're already in app context
            from flask import has_app_context
            if has_app_context():
                return get_llm_client()
            else:
                # Create app context
                app = create_app()
                with app.app_context():
                    return get_llm_client()
                    
        except Exception as e:
            self.logger.error(f"Failed to get LLM client: {e}")
            return None
    
    def generate_definition_prompt(self, concepts: List[Dict]) -> str:
        """Generate prompt for batch definition creation."""
        concept_list = "\n".join([
            f"- {concept['label']} ({concept['uri']})" 
            for concept in concepts
        ])
        
        return f"""You are an expert in professional engineering ethics ontology development.

I need high-quality, professional definitions for these ethical concepts used in engineering practice:

{concept_list}

For each concept, provide:
1. **Definition**: A precise, professional definition (1-2 sentences) suitable for engineering ethics education
2. **Context**: How this concept applies in professional engineering practice
3. **Confidence**: Your confidence level (0.0-1.0) in this definition

Focus on:
- Professional engineering ethics context
- NSPE Code of Ethics alignment where applicable
- Clarity for practicing engineers
- Academic rigor appropriate for ethics courses

Format your response as JSON:
```json
[
  {{
    "label": "concept_label",
    "definition": "Professional definition here",
    "context": "Engineering application context", 
    "confidence": 0.95,
    "reasoning": "Why this definition is appropriate"
  }}
]
```

Ensure definitions are:
- Professionally accurate
- Contextually appropriate for engineering
- Clear and actionable
- Aligned with established ethical frameworks"""

    async def generate_definitions_batch(self, concepts: List[Dict]) -> List[ConceptEnrichment]:
        """Generate definitions for a batch of concepts using LLM."""
        client = self.get_llm_client()
        if not client:
            self.logger.error("No LLM client available")
            return []
            
        prompt = self.generate_definition_prompt(concepts)
        
        try:
            # Call LLM (adapt based on client type)
            if hasattr(client, 'messages'):
                # Anthropic client - use current ProEthica format
                from config.models import ModelConfig
                model = ModelConfig.get_default_model()
                
                response = client.messages.create(
                    model=model,
                    max_tokens=4000,
                    system="You are an expert in professional engineering ethics ontology development. Provide high-quality, professional definitions for ethical concepts used in engineering practice.",
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response.content[0].text
            elif hasattr(client, 'chat'):
                # OpenAI client
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4000
                )
                content = response.choices[0].message.content
            else:
                self.logger.error(f"Unknown client type: {type(client)}")
                return []
            
            # Parse JSON response
            import json
            try:
                # Extract JSON from response
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                else:
                    json_str = content.strip()
                    
                definitions = json.loads(json_str)
                
                # Convert to ConceptEnrichment objects
                enrichments = []
                concept_lookup = {c['label']: c for c in concepts}
                
                for defn in definitions:
                    original_concept = concept_lookup.get(defn['label'])
                    if original_concept:
                        enrichments.append(ConceptEnrichment(
                            uri=original_concept['uri'],
                            label=defn['label'],
                            original_comment=original_concept.get('comment'),
                            generated_definition=defn['definition'],
                            skos_definition=f"{defn['definition']} {defn.get('context', '')}".strip(),
                            confidence=defn.get('confidence', 0.8),
                            reasoning=defn.get('reasoning', 'LLM-generated definition')
                        ))
                
                self.logger.info(f"Generated {len(enrichments)} definitions")
                return enrichments
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse LLM JSON response: {e}")
                self.logger.error(f"Response content: {content[:500]}...")
                return []
                
        except Exception as e:
            self.logger.error(f"Error generating definitions: {e}")
            return []
    
    def update_ontology_entity(self, enrichment: ConceptEnrichment) -> bool:
        """Update ontology entity with generated definition."""
        try:
            # Connect to OntServe database
            import psycopg2
            conn = psycopg2.connect(os.environ['ONTSERVE_DB_URL'])
            cur = conn.cursor()
            
            # Update entity with new definition
            cur.execute("""
                UPDATE ontology_entities 
                SET comment = %s,
                    properties = COALESCE(properties, '{}')::jsonb || %s::jsonb
                WHERE uri = %s
            """, (
                enrichment.generated_definition,
                json.dumps({
                    'skos:definition': enrichment.skos_definition,
                    'generated_definition': {
                        'content': enrichment.generated_definition,
                        'confidence': enrichment.confidence,
                        'reasoning': enrichment.reasoning,
                        'generated_at': str(datetime.datetime.utcnow())
                    }
                }),
                enrichment.uri
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
            self.logger.info(f"Updated definition for {enrichment.label}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update {enrichment.uri}: {e}")
            return False
    
    async def enrich_ontology(self, ontology_name: str = 'proethica-intermediate') -> Dict[str, int]:
        """Enrich an entire ontology with LLM-generated definitions."""
        self.logger.info(f"Starting enrichment of {ontology_name}")
        
        # Get entities without definitions
        import psycopg2
        conn = psycopg2.connect(os.environ['ONTSERVE_DB_URL'])
        cur = conn.cursor()
        
        cur.execute("""
            SELECT oe.uri, oe.label, oe.comment
            FROM ontology_entities oe
            JOIN ontologies o ON oe.ontology_id = o.id
            WHERE o.name = %s 
            AND (oe.comment IS NULL OR oe.comment = '')
            ORDER BY oe.label
        """, (ontology_name,))
        
        entities = [
            {'uri': row[0], 'label': row[1], 'comment': row[2]}
            for row in cur.fetchall()
        ]
        
        cur.close()
        conn.close()
        
        self.logger.info(f"Found {len(entities)} entities needing definitions")
        
        # Process in batches
        total_processed = 0
        total_updated = 0
        total_errors = 0
        
        for i in range(0, len(entities), self.batch_size):
            batch = entities[i:i + self.batch_size]
            self.logger.info(f"Processing batch {i//self.batch_size + 1}: {len(batch)} entities")
            
            enrichments = await self.generate_definitions_batch(batch)
            
            for enrichment in enrichments:
                success = self.update_ontology_entity(enrichment)
                total_processed += 1
                if success:
                    total_updated += 1
                else:
                    total_errors += 1
            
            # Brief pause between batches to avoid rate limiting
            await asyncio.sleep(2)
        
        results = {
            'total_entities': len(entities),
            'total_processed': total_processed,
            'total_updated': total_updated,
            'total_errors': total_errors
        }
        
        self.logger.info(f"Enrichment complete: {results}")
        return results

async def main():
    """Main enrichment workflow."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Starting Ontology Definition Enrichment")
    
    # Create Flask app context for the entire process
    from app import create_app
    app = create_app('config')  # Use the enhanced configuration system
    
    with app.app_context():
        enricher = OntologyEnricher()
        results = await enricher.enrich_ontology('proethica-intermediate')
        
        logger.info("📊 Final Results:")
        logger.info(f"  Total entities: {results['total_entities']}")
        logger.info(f"  Successfully updated: {results['total_updated']}")
        logger.info(f"  Errors: {results['total_errors']}")
        logger.info(f"  Success rate: {results['total_updated']/results['total_entities']*100:.1f}%")
        
        if results['total_updated'] > 0:
            logger.info("✅ Ontology definitions successfully enriched!")
            logger.info("   Annotations will now have rich contextual information.")
        else:
            logger.warning("❌ No definitions were updated. Check LLM configuration.")

if __name__ == "__main__":
    import datetime
    import json
    asyncio.run(main())