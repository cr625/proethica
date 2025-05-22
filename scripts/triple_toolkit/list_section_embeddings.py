#!/usr/bin/env python3
"""
List and analyze section embeddings.

This utility displays information about section embeddings in the database,
allowing analysis of embedding generation and association with document sections.
"""

import sys
import argparse
import numpy as np
from scripts.triple_toolkit.common import db_utils, formatting, pagination

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='List and analyze section embeddings.')
    parser.add_argument('--document-id', '-d', type=int,
                      help='Filter by document ID')
    parser.add_argument('--section-id', '-s', type=int,
                      help='Filter by section ID')
    parser.add_argument('--case-id', '-c', type=int,
                      help='Filter by case ID')
    parser.add_argument('--limit', '-l', type=int, default=10,
                      help='Limit the number of results (default: 10)')
    parser.add_argument('--format', '-f', choices=['simple', 'detailed', 'stats'],
                      default='simple', help='Output format (default: simple)')
    parser.add_argument('--interactive', '-i', action='store_true',
                      help='Use interactive pager for navigation')
    return parser.parse_args()

def get_section_embeddings(document_id=None, section_id=None, case_id=None, limit=10):
    """Retrieve section embeddings from the database with optional filtering."""
    try:
        # Build query with optional filters
        query = """
        SELECT 
            ds.id, 
            ds.section_id, 
            ds.document_id,
            'pgvector' as embedding_model,
            ds.embedding,
            ds.section_metadata as metadata,
            ds.created_at,
            ds.updated_at,
            ds.section_id as section_title,
            ds.content as section_content,
            ds.section_type as section_type,
            d.id as case_id,
            d.title as document_title
        FROM 
            document_sections ds
        JOIN 
            documents d ON ds.document_id = d.id
        WHERE 
            ds.embedding IS NOT NULL
        """
        
        params = {}
        
        if document_id:
            query += " AND ds.document_id = :document_id"
            params['document_id'] = document_id
            
        if section_id:
            query += " AND ds.id = :section_id"
            params['section_id'] = section_id
            
        if case_id:
            query += " AND d.id = :case_id"
            params['case_id'] = case_id
            
        query += " ORDER BY ds.id LIMIT :limit"
        params['limit'] = limit
        
        results = db_utils.execute_query(query, params)
        
        # Convert to SectionEmbedding objects
        embeddings = []
        for row in results:
            embedding = SectionEmbeddingInfo(*row)
            embeddings.append(embedding)
            
        return embeddings
    except Exception as e:
        print(f"Error retrieving section embeddings: {e}")
        return []

def get_embedding_statistics():
    """Get statistics about section embeddings."""
    try:
        # Since we only have one model (pgvector), we'll count total embeddings
        model_query = """
        SELECT 
            'pgvector' as embedding_model, 
            COUNT(*) as count
        FROM 
            document_sections
        WHERE
            embedding IS NOT NULL
        """
        
        model_results = db_utils.execute_query(model_query)
        
        # Count by document
        document_query = """
        SELECT 
            d.title,
            COUNT(*) as count
        FROM 
            document_sections ds
        JOIN
            documents d ON ds.document_id = d.id
        WHERE
            ds.embedding IS NOT NULL
        GROUP BY 
            d.id, d.title
        ORDER BY 
            count DESC
        LIMIT 10
        """
        
        document_results = db_utils.execute_query(document_query)
        
        # Get total count
        count_query = """
        SELECT COUNT(*) 
        FROM document_sections 
        WHERE embedding IS NOT NULL
        """
        count_result = db_utils.execute_query(count_query)
        total_count = count_result[0][0] if count_result else 0
        
        # Check for sections that should have embeddings but don't
        null_query = """
        SELECT 
            COUNT(*) 
        FROM 
            document_sections 
        WHERE 
            embedding IS NULL AND content IS NOT NULL
        """
        
        null_result = db_utils.execute_query(null_query)
        null_count = null_result[0][0] if null_result else 0
        
        return {
            'total_count': total_count,
            'null_count': null_count,
            'models': model_results,
            'documents': document_results
        }
    except Exception as e:
        print(f"Error retrieving embedding statistics: {e}")
        return {
            'total_count': 0,
            'null_count': 0,
            'models': [],
            'documents': []
        }

class SectionEmbeddingInfo:
    """Class to represent section embedding information from direct query."""
    
    def __init__(self, id, section_id, document_id, embedding_model, embedding, 
                 metadata, created_at, updated_at, section_title, section_content,
                 section_type, case_id, document_title):
        self.id = id
        self.section_id = section_id
        self.document_id = document_id
        self.embedding_model = embedding_model
        self.embedding = embedding
        self.metadata = metadata
        self.created_at = created_at
        self.updated_at = updated_at
        self.section_title = section_title
        self.section_content = section_content
        self.section_type = section_type
        self.case_id = case_id
        self.document_title = document_title
    
    def embedding_dimensions(self):
        """Get the dimensions of the embedding if available."""
        if not self.embedding:
            return 0
        try:
            # Try to parse embedding as array
            if isinstance(self.embedding, str) and self.embedding.startswith('[') and self.embedding.endswith(']'):
                # Parse string representation of array
                values = self.embedding.strip('[]').split(',')
                return len(values)
            elif hasattr(self.embedding, '__len__'):
                return len(self.embedding)
        except:
            pass
        return 0
    
    def get_content_excerpt(self, length=100):
        """Get a short excerpt of the section content."""
        if not self.section_content:
            return "No content"
        if len(self.section_content) <= length:
            return self.section_content
        return self.section_content[:length] + "..."

def format_embedding_simple(embedding):
    """Format a section embedding for simple display."""
    return f"Embedding {embedding.id}: {embedding.section_title} (Model: {embedding.embedding_model})"

def format_embedding_detailed(embedding):
    """Format a section embedding for detailed display."""
    dimensions = embedding.embedding_dimensions()
    
    result = f"Embedding {embedding.id}\n"
    result += f"  Section: {embedding.section_title} (ID: {embedding.section_id})\n"
    result += f"  Document: {embedding.document_title} (ID: {embedding.document_id})\n"
    result += f"  Case ID: {embedding.case_id}\n"
    result += f"  Model: {embedding.embedding_model}\n"
    result += f"  Dimensions: {dimensions}\n"
    result += f"  Section Type: {embedding.section_type}\n"
    result += f"  Content Excerpt: {embedding.get_content_excerpt()}\n"
    result += f"  Created: {formatting.format_datetime(embedding.created_at)}"
    
    return result

def format_embedding_statistics(stats):
    """Format embedding statistics for display."""
    result = "SECTION EMBEDDING STATISTICS\n\n"
    
    result += f"Total Embeddings: {stats['total_count']}\n"
    result += f"Incomplete/Null Embeddings: {stats['null_count']}\n\n"
    
    result += "Embeddings by Model:\n"
    for model_row in stats['models']:
        result += f"  {model_row[0]}: {model_row[1]}\n"
    
    result += "\nTop Documents by Embedding Count:\n"
    for doc_row in stats['documents']:
        result += f"  {doc_row[0]}: {doc_row[1]}\n"
    
    return result

def list_embeddings_simple(embeddings):
    """List embeddings in simple format."""
    if not embeddings:
        print("No section embeddings found matching the criteria.")
        return
    
    formatting.print_header("SECTION EMBEDDINGS")
    
    for embedding in embeddings:
        print(format_embedding_simple(embedding))

def list_embeddings_detailed(embeddings):
    """List embeddings with detailed information."""
    if not embeddings:
        print("No section embeddings found matching the criteria.")
        return
    
    formatting.print_header("SECTION EMBEDDINGS (DETAILED)")
    
    for i, embedding in enumerate(embeddings):
        if i > 0:
            print()  # Add spacing between embeddings
        print(format_embedding_detailed(embedding))

def list_embeddings_interactive(embeddings):
    """List embeddings using an interactive pager."""
    if not embeddings:
        print("No section embeddings found matching the criteria.")
        return
    
    title = "SECTION EMBEDDINGS"
    pagination.interactive_pager(
        embeddings,
        formatter=format_embedding_detailed,
        title=title
    )

def list_embedding_statistics():
    """Display statistics about section embeddings."""
    stats = get_embedding_statistics()
    formatting.print_header("SECTION EMBEDDING STATISTICS")
    print(format_embedding_statistics(stats))

def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        if args.format == 'stats':
            list_embedding_statistics()
            return 0
            
        embeddings = get_section_embeddings(
            document_id=args.document_id,
            section_id=args.section_id,
            case_id=args.case_id,
            limit=args.limit
        )
        
        if args.interactive:
            list_embeddings_interactive(embeddings)
        elif args.format == 'detailed':
            list_embeddings_detailed(embeddings)
        else:
            list_embeddings_simple(embeddings)
            print("\nTips: Use --format detailed for more information or --interactive for navigation")
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
