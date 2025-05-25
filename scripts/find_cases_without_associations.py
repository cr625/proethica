#!/usr/bin/env python3
"""
Find cases that don't have ontology concept associations.
"""

import os
import sys
import argparse
from sqlalchemy import create_engine, text
from tabulate import tabulate

def find_cases_without_associations(verbose=True, output_file=None):
    """Find all cases that don't have ontology concept associations."""
    
    # Connect to database
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Get all case documents
        all_cases_query = text("""
            SELECT id, title, doc_metadata->>'case_number' as case_number 
            FROM documents 
            WHERE document_type = 'case' OR title LIKE '%Case%'
            ORDER BY id
        """)
        
        # Get all documents that have associations
        docs_with_assoc_query = text("""
            SELECT DISTINCT ds.document_id 
            FROM section_ontology_associations soa
            JOIN document_sections ds ON soa.section_id = ds.id
        """)
        
        all_cases = [(row[0], row[1], row[2]) for row in conn.execute(all_cases_query)]
        docs_with_assoc = {row[0] for row in conn.execute(docs_with_assoc_query)}
        
        # Find cases without associations
        cases_without_assoc = [(id, title, case_number) for id, title, case_number in all_cases 
                              if id not in docs_with_assoc]
        
        # Calculate statistics
        total_cases = len(all_cases)
        cases_with_assoc = len(docs_with_assoc)
        cases_without = len(cases_without_assoc)
        
        # Prepare results
        if verbose:
            print(f"Total cases: {total_cases}")
            print(f"Cases with associations: {cases_with_assoc}")
            print(f"Cases without associations: {cases_without}")
            if total_cases > 0:
                print(f"Percentage complete: {cases_with_assoc/total_cases*100:.1f}%")
            else:
                print("Percentage complete: N/A (no cases found)")
            print("\nCases without ontology associations:")
            
            # Prepare table data
            table_data = [
                [id, title, case_number if case_number else "N/A"] 
                for id, title, case_number in cases_without_assoc
            ]
            
            # Print table
            if table_data:
                headers = ["ID", "Title", "Case Number"]
                print(tabulate(table_data, headers=headers, tablefmt="grid"))
            else:
                print("All cases have ontology associations!")
        
        # Save to file if requested
        if output_file:
            with open(output_file, 'w') as f:
                f.write(f"Total cases: {total_cases}\n")
                f.write(f"Cases with associations: {cases_with_assoc}\n")
                f.write(f"Cases without associations: {cases_without}\n")
                if total_cases > 0:
                    f.write(f"Percentage complete: {cases_with_assoc/total_cases*100:.1f}%\n\n")
                else:
                    f.write("Percentage complete: N/A (no cases found)\n\n")
                
                f.write("Cases without ontology associations:\n")
                for id, title, case_number in cases_without_assoc:
                    f.write(f"ID: {id}, Case Number: {case_number or 'N/A'}, Title: {title}\n")
            
            print(f"\nResults saved to {output_file}")
        
        return cases_without_assoc

def find_cases_with_few_associations(threshold=3, verbose=True):
    """Find cases that have fewer than threshold associations per section on average."""
    
    # Connect to database
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Get all case documents
        all_cases_query = text("""
            SELECT d.id, d.title, d.doc_metadata->>'case_number' as case_number,
                   COUNT(DISTINCT ds.id) as section_count
            FROM documents d
            JOIN document_sections ds ON d.id = ds.document_id
            WHERE d.document_type = 'case' OR d.title LIKE '%Case%'
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
            HAVING COUNT(soa.id) > 0
        """)
        
        all_cases = {row[0]: {"title": row[1], "case_number": row[2], "section_count": row[3]} 
                    for row in conn.execute(all_cases_query)}
        
        assoc_counts = {row[0]: {"section_count": row[1], "assoc_count": row[2], "avg_per_section": row[3]} 
                        for row in conn.execute(assoc_count_query)}
        
        # Find cases with fewer than threshold associations per section
        cases_with_few = []
        for doc_id, case_info in all_cases.items():
            if doc_id in assoc_counts:
                if assoc_counts[doc_id]["avg_per_section"] < threshold:
                    cases_with_few.append((
                        doc_id, 
                        case_info["title"], 
                        case_info["case_number"],
                        assoc_counts[doc_id]["section_count"],
                        assoc_counts[doc_id]["assoc_count"],
                        assoc_counts[doc_id]["avg_per_section"]
                    ))
        
        if verbose:
            print(f"\nCases with fewer than {threshold} associations per section:")
            
            # Prepare table data
            table_data = [
                [id, title, case_number if case_number else "N/A", section_count, assoc_count, f"{avg_per_section:.1f}"] 
                for id, title, case_number, section_count, assoc_count, avg_per_section in cases_with_few
            ]
            
            # Print table
            if table_data:
                headers = ["ID", "Title", "Case Number", "Sections", "Associations", "Avg/Section"]
                print(tabulate(table_data, headers=headers, tablefmt="grid"))
            else:
                print(f"All cases with associations have at least {threshold} associations per section!")
        
        return cases_with_few

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Find cases without ontology concept associations.')
    parser.add_argument('--output', type=str, help='Output file to save results')
    parser.add_argument('--few-threshold', type=float, default=3.0, 
                        help='Threshold for identifying cases with few associations per section')
    parser.add_argument('--quiet', action='store_true', help='Suppress verbose output')
    
    args = parser.parse_args()
    
    # Find cases without associations
    find_cases_without_associations(
        verbose=not args.quiet,
        output_file=args.output
    )
    
    # Find cases with few associations
    find_cases_with_few_associations(
        threshold=args.few_threshold,
        verbose=not args.quiet
    )
