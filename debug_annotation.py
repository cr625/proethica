#!/usr/bin/env python3
"""
Debug Annotation System - Identify why annotations are returning 0 results
"""
import sys
import os
import requests
from flask import current_app
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set database URI if not already set
if not os.environ.get('SQLALCHEMY_DATABASE_URI'):
    database_url = os.environ.get('DATABASE_URL', 'postgresql://proethica_user:proethica_development_password@localhost:5432/ai_ethical_dm')
    os.environ['SQLALCHEMY_DATABASE_URI'] = database_url

# Also set DATABASE_URL for config.py
if not os.environ.get('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'postgresql://proethica_user:proethica_development_password@localhost:5432/ai_ethical_dm'

print(f"Debug: SQLALCHEMY_DATABASE_URI = {os.environ.get('SQLALCHEMY_DATABASE_URI')}")
print(f"Debug: DATABASE_URL = {os.environ.get('DATABASE_URL')}")

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.models.guideline import Guideline
from app.models.world import World
from app.services.ontserve_annotation_service import OntServeAnnotationService
from app.services.simple_annotation_service import SimpleAnnotationService

def debug_annotation_system(guideline_id=None):
    """Debug the annotation system step by step."""
    app = create_app()
    
    with app.app_context():
        print("🔍 ANNOTATION SYSTEM DEBUG")
        print("=" * 50)
        
        # Step 1: Get a guideline to test with
        if guideline_id:
            guideline = Guideline.query.get(guideline_id)
        else:
            guideline = Guideline.query.first()
            
        if not guideline:
            print("❌ No guidelines found in database!")
            return
        
        print(f"✅ Testing with guideline: '{guideline.title[:50]}...'")
        print(f"   World ID: {guideline.world_id}")
        print(f"   Content length: {len(guideline.content or '')} chars")
        
        # Step 2: Check content
        if not guideline.content or len(guideline.content) < 50:
            print(f"⚠️  WARNING: Content too short ({len(guideline.content or '')} chars)")
            print("   Annotation requires >50 chars of clean text")
        
        # Step 3: Test OntServe connection
        print(f"\n📡 Testing OntServe Connection...")
        ontserve_service = OntServeAnnotationService()
        
        try:
            # Test basic connectivity
            response = requests.get(f"{ontserve_service.ontserve_url}/health", timeout=5)
            print(f"✅ OntServe health check: {response.status_code}")
        except Exception as e:
            print(f"❌ OntServe connection failed: {e}")
            print("   Make sure OntServe is running on http://localhost:5003")
        
        # Step 4: Check world ontology mapping
        print(f"\n🗺️  Checking World Ontology Mapping...")
        mapping = ontserve_service.get_world_ontology_mapping(guideline.world_id)
        print(f"   Mapping: {mapping}")
        
        # Step 5: Test concept retrieval
        print(f"\n📚 Testing Concept Retrieval...")
        ontology_names = list(mapping.values())
        concepts = ontserve_service.get_ontology_concepts(ontology_names)
        
        total_concepts = sum(len(concept_list) for concept_list in concepts.values())
        print(f"   Total concepts retrieved: {total_concepts}")
        
        for ontology, concept_list in concepts.items():
            print(f"   {ontology}: {len(concept_list)} concepts")
            if len(concept_list) > 0:
                sample = concept_list[0]
                print(f"     Sample concept: {sample.get('label', 'NO_LABEL')}")
        
        if total_concepts == 0:
            print("❌ PROBLEM: No concepts retrieved from any ontology!")
            print("   Check if ontologies exist in OntServe:")
            for ont_name in ontology_names:
                try:
                    url = f"{ontserve_service.ontserve_url}/editor/api/ontologies/{ont_name}/entities"
                    response = requests.get(url, timeout=5)
                    print(f"     {ont_name}: HTTP {response.status_code}")
                except Exception as e:
                    print(f"     {ont_name}: ERROR - {e}")
        
        # Step 6: Test simple annotation service
        print(f"\n🏷️  Testing Simple Annotation...")
        simple_service = SimpleAnnotationService()
        
        try:
            annotations = simple_service.annotate_document(
                'guideline', guideline.id, guideline.world_id, force_refresh=True
            )
            print(f"   Result: {len(annotations)} annotations created")
            
            if len(annotations) == 0:
                print("❌ PROBLEM: SimpleAnnotationService returned 0 annotations")
            else:
                print("✅ Annotations created successfully!")
                for i, ann in enumerate(annotations[:3]):  # Show first 3
                    print(f"     {i+1}. '{ann.text_segment}' → {ann.concept_label}")
        
        except Exception as e:
            print(f"❌ Annotation service error: {e}")
        
        # Step 7: Check for existing annotations
        print(f"\n📋 Checking Existing Annotations...")
        from app.models.document_concept_annotation import DocumentConceptAnnotation
        existing = DocumentConceptAnnotation.get_annotations_for_document('guideline', guideline.id)
        print(f"   Existing annotations: {len(existing)}")
        
        for ann in existing[:3]:  # Show first 3
            print(f"     '{ann.text_segment}' → {ann.concept_label} (status: {ann.validation_status})")

def clear_annotation_flags(guideline_id=None):
    """Clear annotation flags to allow re-annotation."""
    app = create_app()
    
    with app.app_context():
        from app.models.document_concept_annotation import DocumentConceptAnnotation
        from app.models import db
        
        if guideline_id:
            existing = DocumentConceptAnnotation.query.filter_by(
                document_type='guideline',
                document_id=guideline_id
            ).all()
        else:
            existing = DocumentConceptAnnotation.query.filter_by(
                document_type='guideline'
            ).all()
        
        if existing:
            print(f"🗑️  Clearing {len(existing)} existing annotations...")
            for ann in existing:
                db.session.delete(ann)
            db.session.commit()
            print("✅ Annotation flags cleared")
        else:
            print("ℹ️  No existing annotations to clear")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Debug ProEthica Annotation System')
    parser.add_argument('--guideline-id', type=int, help='Specific guideline ID to test')
    parser.add_argument('--clear-flags', action='store_true', help='Clear existing annotation flags')
    
    args = parser.parse_args()
    
    if args.clear_flags:
        clear_annotation_flags(args.guideline_id)
    else:
        debug_annotation_system(args.guideline_id)