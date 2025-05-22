#!/usr/bin/env python3
"""
Regenerate ontology concept associations for all case documents 
that have fewer than a target threshold of associations per section.

This script:
1. Identifies cases with no associations or fewer than threshold associations per section
2. Regenerates associations using the embedding-based approach with a lower similarity threshold
"""

import os
import sys
import argparse
import subprocess
from sqlalchemy import create_engine, text
from tabulate import tabulate

def find_cases_to_regenerate(threshold=2.0, verbose=True):
    """Find cases that need regeneration of ontology concept associations."""
    
    # Connect to database
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Get all case documents with section counts
        all_cases_query = text("""
            SELECT d.id, d.title, d.doc_metadata->>'case_number' as case_number,
                   COUNT(DISTINCT ds.id) as section_count
            FROM documents d
            JOIN document_sections ds ON d.id = ds.document_id
            WHERE d.document_type = 'case_study' OR d.document_type = 'case' OR d.title LIKE '%Case%'
            GROUP BY d.id, d.title, d.doc_metadata->>'case_number'
            ORDER BY d.id
        """)
        
        # Get association counts by document
        assoc_count_query = text("""
            SELECT ds.document_id, 
                   COUNT(DISTINCT ds.id) as section_count,
                   COUNT(soa.id) as assoc_count,
                   COUNT(soa.id)::float / COUNT(DISTINCT ds.id) as avg_per_section
            FROM document_sections ds
            LEFT JOIN section_ontology_associations soa ON ds.id = soa.section_id
            GROUP BY ds.document_id
        """)
        
        all_cases = [(row[0], row[1], row[2], row[3]) 
                    for row in conn.execute(all_cases_query)]
        
        assoc_counts = {row[0]: {"section_count": row[1], 
                                "assoc_count": row[2], 
                                "avg_per_section": row[3]} 
                        for row in conn.execute(assoc_count_query)}
        
        # Find cases that need regeneration
        cases_to_regenerate = []
        for doc_id, title, case_number, section_count in all_cases:
            # Check if case has no associations or fewer than threshold per section
            if (doc_id not in assoc_counts or 
                assoc_counts[doc_id]["assoc_count"] == 0 or
                assoc_counts[doc_id]["avg_per_section"] < threshold):
                
                # Calculate current avg if available
                current_avg = 0
                if doc_id in assoc_counts:
                    current_avg = assoc_counts[doc_id]["avg_per_section"]
                
                cases_to_regenerate.append((
                    doc_id, 
                    title, 
                    case_number,
                    section_count,
                    assoc_counts.get(doc_id, {}).get("assoc_count", 0),
                    current_avg
                ))
        
        if verbose:
            print(f"Found {len(cases_to_regenerate)} cases that need regeneration:")
            
            # Prepare table data
            table_data = [
                [id, title[:50] + '...' if len(title) > 50 else title, 
                 case_number if case_number else "N/A", 
                 section_count, assoc_count, f"{avg_per_section:.1f}"] 
                for id, title, case_number, section_count, assoc_count, avg_per_section in cases_to_regenerate
            ]
            
            # Print table
            if table_data:
                headers = ["ID", "Title", "Case Number", "Sections", "Associations", "Avg/Section"]
                print(tabulate(table_data, headers=headers, tablefmt="grid"))
            else:
                print("All cases have sufficient associations!")
        
        return cases_to_regenerate

def regenerate_case_associations(document_id, similarity_threshold=0.4, max_matches=10, verbose=True):
    """Regenerate ontology concept associations for a specific case."""
    
    if verbose:
        print(f"\nRegenerating associations for document {document_id}...")
    
    # Delete existing associations
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Get sections for this document
        sections_query = text("""
            SELECT id FROM document_sections
            WHERE document_id = :doc_id
        """)
        
        # Count existing associations
        count_query = text("""
            SELECT COUNT(*) 
            FROM section_ontology_associations soa
            JOIN document_sections ds ON soa.section_id = ds.id
            WHERE ds.document_id = :doc_id
        """)
        
        sections = [row[0] for row in conn.execute(sections_query, {"doc_id": document_id})]
        
        # Get the count before deletion
        count_result = conn.execute(count_query, {"doc_id": document_id}).scalar()
        
        if count_result == 0:
            if verbose:
                print(f"No existing associations found for document {document_id}")
        else:
            # Delete existing associations
            deleted_total = 0
            for section_id in sections:
                delete_query = text("""
                    DELETE FROM section_ontology_associations
                    WHERE section_id = :section_id
                    RETURNING id
                """)
                result = conn.execute(delete_query, {"section_id": section_id})
                deleted = result.rowcount
                deleted_total += deleted
                if verbose:
                    print(f"Deleted {deleted} associations for section {section_id}")
            
            conn.commit()
            if verbose:
                print(f"Total: Deleted {deleted_total} existing associations for document {document_id}")
    
    # Run embedding-based association with custom similarity threshold
    cmd = ["./run_ttl_section_triple_association.sh", 
           "-d", str(document_id), 
           "-t", str(similarity_threshold),
           "-m", str(max_matches)]
    
    if verbose:
        print(f"Running command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd)
    success = result.returncode == 0
    
    # Check new association counts
    with engine.connect() as conn:
        # Count new associations
        count_query = text("""
            SELECT ds.id, COUNT(soa.id) 
            FROM document_sections ds
            LEFT JOIN section_ontology_associations soa ON ds.id = soa.section_id
            WHERE ds.document_id = :doc_id
            GROUP BY ds.id
        """)
        
        results = conn.execute(count_query, {"doc_id": document_id}).fetchall()
        
        if verbose:
            print(f"\nNew association counts for document {document_id}:")
            total_sections = len(results)
            total_associations = sum(row[1] for row in results)
            
            for section_id, count in results:
                print(f"Section {section_id}: {count} associations")
            
            if total_sections > 0:
                print(f"\nTotal: {total_associations} associations across {total_sections} sections")
                print(f"Average: {total_associations / total_sections:.1f} associations per section")
            else:
                print("\nNo sections found for this document")
    
    return success

def main():
    """Main function to regenerate associations for all cases that need it."""
    
    parser = argparse.ArgumentParser(description='Regenerate ontology concept associations for all cases.')
    parser.add_argument('--threshold', type=float, default=2.0, 
                        help='Minimum average associations per section (default: 2.0)')
    parser.add_argument('--similarity', type=float, default=0.4, 
                        help='Similarity threshold for matching (default: 0.4)')
    parser.add_argument('--max-matches', type=int, default=10, 
                        help='Maximum matches per section (default: 10)')
    parser.add_argument('--document-id', type=int, 
                        help='Regenerate specific document ID only')
    parser.add_argument('--quiet', action='store_true', 
                        help='Suppress verbose output')
    
    args = parser.parse_args()
    
    # Find cases to regenerate
    if args.document_id:
        cases = [(args.document_id, "Specified document", None, 0, 0, 0)]
    else:
        cases = find_cases_to_regenerate(args.threshold, not args.quiet)
    
    # Regenerate associations for each case
    success_count = 0
    for doc_id, title, case_number, section_count, assoc_count, avg in cases:
        success = regenerate_case_associations(
            doc_id, 
            similarity_threshold=args.similarity,
            max_matches=args.max_matches,
            verbose=not args.quiet
        )
        if success:
            success_count += 1
    
    # Print summary
    if not args.quiet:
        print(f"\nSummary: Successfully regenerated associations for {success_count} out of {len(cases)} cases")

if __name__ == "__main__":
    main()
