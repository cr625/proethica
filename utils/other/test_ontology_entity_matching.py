#!/usr/bin/env python3
"""
Test ontology entity matching for guideline concepts.
Check if extracted concepts like "Professional Competence" match existing ontology entities.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.models import db
from app.models.entity_triple import EntityTriple

def test_mcp_ontology_matching():
    """Test the MCP server's ontology entity matching capability."""
    print("🔍 TESTING ONTOLOGY ENTITY MATCHING")
    print("=" * 50)
    
    # Test concepts from recent guideline
    test_concepts = [
        {
            "label": "Professional Competence",
            "description": "The requirement to work only within one's areas of expertise and qualifications",
            "category": "Professional Standards"
        },
        {
            "label": "Public Safety",
            "description": "The paramount obligation to prioritize public safety, health, and welfare",
            "category": "Fundamental Duty"
        },
        {
            "label": "Honesty and Integrity", 
            "description": "The fundamental requirement for truthfulness and ethical conduct",
            "category": "Core Values"
        },
        {
            "label": "Environmental Responsibility",
            "description": "The commitment to environmental responsibility in engineering practice", 
            "category": "Environmental Ethics"
        },
        {
            "label": "Professional Accountability",
            "description": "Taking responsibility for professional actions and decisions",
            "category": "Professional Responsibility"
        }
    ]
    
    # Check if MCP server is running
    mcp_url = "http://localhost:5001"
    try:
        response = requests.post(
            f"{mcp_url}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "match_concepts_to_ontology",
                    "arguments": {
                        "concepts": test_concepts,
                        "ontology_source": "engineering-ethics"
                    }
                },
                "id": 1
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if "result" in result:
                matches = result["result"].get("matches", [])
                print(f"✅ Found {len(matches)} ontology matches:")
                
                for match in matches:
                    concept = match.get("concept_label", "Unknown")
                    entity = match.get("ontology_entity", "Unknown")
                    match_type = match.get("match_type", "unknown")
                    confidence = match.get("confidence", 0)
                    explanation = match.get("explanation", "No explanation")
                    
                    status = "🎯" if confidence >= 0.8 else "✅" if confidence >= 0.6 else "⚠️"
                    
                    print(f"\n  {status} {concept}")
                    print(f"     → {entity} ({match_type}, {confidence:.2f})")
                    print(f"     {explanation}")
                
                return matches
            elif "error" in result:
                print(f"❌ MCP server error: {result['error']}")
                return []
        else:
            print(f"❌ MCP server HTTP error: {response.status_code}")
            return []
            
    except requests.exceptions.ConnectionError:
        print("❌ MCP server not running at localhost:5001")
        return []
    except Exception as e:
        print(f"❌ Error testing ontology matching: {e}")
        return []

def test_ontology_query():
    """Test querying the ontology for existing entities."""
    print(f"\n🔍 TESTING ONTOLOGY QUERY")
    print("=" * 30)
    
    mcp_url = "http://localhost:5001"
    
    # Test queries for concepts that might exist
    test_queries = [
        "professional competence",
        "public safety", 
        "integrity",
        "accountability",
        "environmental",
        "responsibility"
    ]
    
    for query in test_queries:
        try:
            response = requests.post(
                f"{mcp_url}/jsonrpc",
                json={
                    "jsonrpc": "2.0",
                    "method": "call_tool", 
                    "params": {
                        "name": "query_ontology",
                        "arguments": {
                            "sparql_query": f"""
                                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                                SELECT ?entity ?label ?type WHERE {{
                                    ?entity rdfs:label ?label .
                                    ?entity a ?type .
                                    FILTER(CONTAINS(LCASE(?label), "{query.lower()}"))
                                }}
                                LIMIT 5
                            """
                        }
                    },
                    "id": 1
                },
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result and "bindings" in result["result"]:
                    bindings = result["result"]["bindings"]
                    if bindings:
                        print(f"\n🔍 Query: '{query}' ({len(bindings)} results)")
                        for binding in bindings[:3]:  # Show first 3
                            entity = binding.get("entity", {}).get("value", "Unknown")
                            label = binding.get("label", {}).get("value", "Unknown")
                            type_uri = binding.get("type", {}).get("value", "Unknown")
                            print(f"   ✅ {label} ({type_uri.split('#')[-1] if '#' in type_uri else type_uri})")
                    else:
                        print(f"   ❌ No matches for '{query}'")
                        
        except Exception as e:
            print(f"   ❌ Query error for '{query}': {e}")
            break

def analyze_current_vs_ontology():
    """Analyze current extracted concepts vs what exists in ontology."""
    print(f"\n📊 ANALYSIS: CURRENT CONCEPTS VS ONTOLOGY")
    print("=" * 50)
    
    app = create_app('config')
    with app.app_context():
        # Get recent concepts from database
        recent_concepts = EntityTriple.query.filter_by(
            entity_type='guideline_concept'
        ).filter(
            EntityTriple.subject_label.isnot(None)
        ).order_by(EntityTriple.id.desc()).limit(10).all()
        
        unique_concepts = set()
        for triple in recent_concepts:
            if triple.subject_label:
                unique_concepts.add(triple.subject_label)
        
        print(f"Recent extracted concepts ({len(unique_concepts)}):")
        for concept in sorted(unique_concepts):
            print(f"  • {concept}")
        
        print(f"\n🎯 RECOMMENDATION:")
        print(f"We should:")
        print(f"1. Check if these concepts exist in engineering-ethics ontology")
        print(f"2. Link to existing entities where matches found")
        print(f"3. Only create new entities for genuinely new concepts")
        print(f"4. This will improve semantic consistency and avoid duplication")

def main():
    """Test ontology entity matching capabilities."""
    print("🧪 ONTOLOGY ENTITY MATCHING TEST")
    print("=" * 60)
    
    try:
        # Test the MCP matching functionality
        matches = test_mcp_ontology_matching()
        
        # Test ontology querying
        test_ontology_query()
        
        # Analyze current situation
        analyze_current_vs_ontology()
        
        print(f"\n🎉 ONTOLOGY MATCHING TEST SUMMARY")
        print("=" * 40)
        
        if matches:
            print(f"✅ MCP ontology matching is working")
            print(f"✅ Found {len(matches)} potential matches")
            print(f"Next step: Integrate matching into concept extraction pipeline")
        else:
            print(f"⚠️ MCP ontology matching needs setup or server is down")
            print(f"Alternative: Implement basic matching in GuidelineAnalysisService")
        
        return len(matches) > 0
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)