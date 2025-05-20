"""
Document Structure Annotation Step - Annotates case document structure with ontology concepts.
"""
import logging
import uuid
from bs4 import BeautifulSoup
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL
from .base_step import BaseStep

# Set up logging
logger = logging.getLogger(__name__)

# Define namespaces
PROETHICA = Namespace("http://proethica.org/ontology/intermediate#")

class DocumentStructureAnnotationStep(BaseStep):
    """Step for annotating document structure with ontology concepts."""
    
    def __init__(self):
        super().__init__()
        self.description = "Annotates document structure with ontology concepts"
        
    def validate_input(self, input_data):
        """Validate that the input contains required case data."""
        if not input_data or not isinstance(input_data, dict):
            logger.error("Invalid input: Input must be a dictionary")
            return False
            
        if 'status' not in input_data or input_data.get('status') != 'success':
            logger.error("Invalid input: Previous step did not succeed")
            return False
            
        if 'sections' not in input_data:
            logger.error("Invalid input: 'sections' key is required")
            return False
            
        sections = input_data.get('sections', {})
        if not isinstance(sections, dict):
            logger.error("Invalid input: 'sections' must be a dictionary")
            return False
        
        # Check if at least some of the expected sections exist
        expected_sections = ['facts', 'question', 'references', 'discussion', 'conclusion']
        if not any(section in sections for section in expected_sections):
            logger.error("Invalid input: No valid document sections found")
            return False
            
        return True
        
    def process(self, input_data):
        """
        Process the input data to annotate document structure.
        
        Args:
            input_data: Dict containing case sections from previous step
            
        Returns:
            dict: Results containing document structure annotations
        """
        # Validate input
        if not self.validate_input(input_data):
            return self.get_error_result('Invalid input', input_data)
            
        try:
            # Extract case data
            case_number = input_data.get('case_number')
            year = input_data.get('year')
            title = input_data.get('title')
            sections = input_data.get('sections', {})
            questions_list = input_data.get('questions_list', [])
            conclusion_items = input_data.get('conclusion_items', [])
            
            # Generate document URI
            case_id = case_number.replace('-', '_') if case_number else str(uuid.uuid4())
            document_uri = f"http://proethica.org/document/case_{case_id}"
            
            # Create RDF graph for structure annotations
            structure_graph = self._create_structure_graph(
                document_uri, 
                case_number, 
                year, 
                title, 
                sections, 
                questions_list, 
                conclusion_items
            )
            
            # Serialize graph to turtle format
            structure_triples = structure_graph.serialize(format='turtle')
            
            # Add document structure information to result
            result = input_data.copy()
            result['document_structure'] = {
                'document_uri': document_uri,
                'structure_triples': structure_triples,
                'graph': structure_graph
            }
            
            # Generate section-level embedding metadata
            section_embeddings_metadata = self._prepare_section_embedding_metadata(
                document_uri, 
                sections, 
                questions_list, 
                conclusion_items
            )
            result['section_embeddings_metadata'] = section_embeddings_metadata
            
            logger.info(f"Document structure annotation complete for case {case_number}: {len(structure_graph)} triples generated")
            return result
            
        except Exception as e:
            logger.exception(f"Error processing document structure: {str(e)}")
            return self.get_error_result(f"Error annotating document structure: {str(e)}")
    
    def _create_structure_graph(self, document_uri, case_number, year, title, sections, questions_list, conclusion_items):
        """
        Create RDF graph representing document structure.
        
        Args:
            document_uri: URI for the document
            case_number: Case number
            year: Publication year
            title: Document title
            sections: Dictionary of section content
            questions_list: List of individual questions
            conclusion_items: List of individual conclusions
            
        Returns:
            Graph: RDF graph with document structure triples
        """
        # Initialize graph
        g = Graph()
        
        # Bind namespaces
        g.bind("proethica", PROETHICA)
        g.bind("rdf", RDF)
        g.bind("rdfs", RDFS)
        g.bind("owl", OWL)
        
        # Create document
        document = URIRef(document_uri)
        g.add((document, RDF.type, OWL.NamedIndividual))
        g.add((document, RDF.type, PROETHICA.DocumentElement))
        if title:
            g.add((document, RDFS.label, Literal(title)))
            g.add((document, PROETHICA.hasTextContent, Literal(title)))
        
        # Add document metadata
        if case_number:
            case_number_uri = URIRef(f"{document_uri}/case_number")
            g.add((case_number_uri, RDF.type, OWL.NamedIndividual))
            g.add((case_number_uri, RDF.type, PROETHICA.CaseNumber))
            g.add((case_number_uri, PROETHICA.hasTextContent, Literal(case_number)))
            g.add((case_number_uri, PROETHICA.isPartOf, document))
            g.add((document, PROETHICA.hasPart, case_number_uri))
        
        if year:
            year_uri = URIRef(f"{document_uri}/year")
            g.add((year_uri, RDF.type, OWL.NamedIndividual))
            g.add((year_uri, RDF.type, PROETHICA.CaseYear))
            g.add((year_uri, PROETHICA.hasTextContent, Literal(year)))
            g.add((year_uri, PROETHICA.isPartOf, document))
            g.add((document, PROETHICA.hasPart, year_uri))
        
        if title:
            title_uri = URIRef(f"{document_uri}/title")
            g.add((title_uri, RDF.type, OWL.NamedIndividual))
            g.add((title_uri, RDF.type, PROETHICA.CaseTitle))
            g.add((title_uri, PROETHICA.hasTextContent, Literal(title)))
            g.add((title_uri, PROETHICA.isPartOf, document))
            g.add((document, PROETHICA.hasPart, title_uri))
        
        # Process main document sections
        section_uris = {}
        
        # Facts section
        if sections.get('facts'):
            facts_uri = URIRef(f"{document_uri}/facts")
            g.add((facts_uri, RDF.type, OWL.NamedIndividual))
            g.add((facts_uri, RDF.type, PROETHICA.FactsSection))
            g.add((facts_uri, PROETHICA.hasTextContent, Literal(sections['facts'])))
            g.add((facts_uri, PROETHICA.hasHtmlContent, Literal(sections['facts'])))
            g.add((facts_uri, PROETHICA.isPartOf, document))
            g.add((document, PROETHICA.hasPart, facts_uri))
            section_uris['facts'] = facts_uri
        
        # Questions section
        if sections.get('question'):
            questions_uri = URIRef(f"{document_uri}/questions")
            g.add((questions_uri, RDF.type, OWL.NamedIndividual))
            g.add((questions_uri, RDF.type, PROETHICA.QuestionsSection))
            g.add((questions_uri, PROETHICA.hasTextContent, Literal(sections['question'])))
            g.add((questions_uri, PROETHICA.hasHtmlContent, Literal(sections['question'])))
            g.add((questions_uri, PROETHICA.isPartOf, document))
            g.add((document, PROETHICA.hasPart, questions_uri))
            section_uris['questions'] = questions_uri
            
            # Add individual question items
            for i, question in enumerate(questions_list):
                question_uri = URIRef(f"{document_uri}/question_{i+1}")
                g.add((question_uri, RDF.type, OWL.NamedIndividual))
                g.add((question_uri, RDF.type, PROETHICA.QuestionItem))
                g.add((question_uri, PROETHICA.hasTextContent, Literal(question)))
                g.add((question_uri, PROETHICA.isPartOf, questions_uri))
                g.add((questions_uri, PROETHICA.hasPart, question_uri))
        
        # References section
        if sections.get('references'):
            references_uri = URIRef(f"{document_uri}/references")
            g.add((references_uri, RDF.type, OWL.NamedIndividual))
            g.add((references_uri, RDF.type, PROETHICA.ReferencesSection))
            g.add((references_uri, PROETHICA.hasTextContent, Literal(sections['references'])))
            g.add((references_uri, PROETHICA.hasHtmlContent, Literal(sections['references'])))
            g.add((references_uri, PROETHICA.isPartOf, document))
            g.add((document, PROETHICA.hasPart, references_uri))
            section_uris['references'] = references_uri
            
            # Extract code references from HTML
            if sections['references']:
                code_refs = self._extract_code_references(sections['references'])
                for i, ref in enumerate(code_refs):
                    ref_uri = URIRef(f"{document_uri}/code_reference_{i+1}")
                    g.add((ref_uri, RDF.type, OWL.NamedIndividual))
                    g.add((ref_uri, RDF.type, PROETHICA.CodeReferenceItem))
                    g.add((ref_uri, PROETHICA.hasTextContent, Literal(ref)))
                    g.add((ref_uri, PROETHICA.isPartOf, references_uri))
                    g.add((references_uri, PROETHICA.hasPart, ref_uri))
        
        # Discussion section
        if sections.get('discussion'):
            discussion_uri = URIRef(f"{document_uri}/discussion")
            g.add((discussion_uri, RDF.type, OWL.NamedIndividual))
            g.add((discussion_uri, RDF.type, PROETHICA.DiscussionSection))
            g.add((discussion_uri, PROETHICA.hasTextContent, Literal(sections['discussion'])))
            g.add((discussion_uri, PROETHICA.hasHtmlContent, Literal(sections['discussion'])))
            g.add((discussion_uri, PROETHICA.isPartOf, document))
            g.add((document, PROETHICA.hasPart, discussion_uri))
            section_uris['discussion'] = discussion_uri
        
        # Conclusion section
        if sections.get('conclusion'):
            conclusion_uri = URIRef(f"{document_uri}/conclusion")
            g.add((conclusion_uri, RDF.type, OWL.NamedIndividual))
            g.add((conclusion_uri, RDF.type, PROETHICA.ConclusionSection))
            g.add((conclusion_uri, PROETHICA.hasTextContent, Literal(sections['conclusion'])))
            g.add((conclusion_uri, PROETHICA.hasHtmlContent, Literal(sections['conclusion'])))
            g.add((conclusion_uri, PROETHICA.isPartOf, document))
            g.add((document, PROETHICA.hasPart, conclusion_uri))
            section_uris['conclusion'] = conclusion_uri
            
            # Add individual conclusion items
            for i, conclusion in enumerate(conclusion_items):
                conclusion_item_uri = URIRef(f"{document_uri}/conclusion_item_{i+1}")
                g.add((conclusion_item_uri, RDF.type, OWL.NamedIndividual))
                g.add((conclusion_item_uri, RDF.type, PROETHICA.ConclusionItem))
                g.add((conclusion_item_uri, PROETHICA.hasTextContent, Literal(conclusion)))
                g.add((conclusion_item_uri, PROETHICA.isPartOf, conclusion_uri))
                g.add((conclusion_uri, PROETHICA.hasPart, conclusion_item_uri))
        
        # Add document section sequence relationships
        section_order = ['facts', 'questions', 'references', 'discussion', 'conclusion']
        previous_section = None
        
        for section_name in section_order:
            if section_name in section_uris:
                current_section = section_uris[section_name]
                
                # Link this section to the previous one
                if previous_section:
                    g.add((previous_section, PROETHICA.precedesInDocument, current_section))
                    g.add((current_section, PROETHICA.followsInDocument, previous_section))
                
                previous_section = current_section
        
        return g
    
    def _extract_code_references(self, html_content):
        """
        Extract code references from references section HTML.
        
        Args:
            html_content: HTML content of references section
            
        Returns:
            list: List of code reference strings
        """
        if not html_content:
            return []
            
        references = []
        
        try:
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Try list items first
            list_items = soup.find_all('li')
            if list_items:
                for item in list_items:
                    references.append(item.get_text().strip())
                return references
            
            # If no list items, look for paragraphs
            paragraphs = soup.find_all('p')
            if paragraphs:
                for p in paragraphs:
                    references.append(p.get_text().strip())
                return references
            
            # If no structured content, use the raw text
            text = soup.get_text().strip()
            if text:
                # Split by newlines or semicolons
                for line in text.replace(';', '\n').split('\n'):
                    if line.strip():
                        references.append(line.strip())
        except Exception as e:
            logger.warning(f"Error extracting code references: {str(e)}")
        
        return references
    
    def _prepare_section_embedding_metadata(self, document_uri, sections, questions_list, conclusion_items):
        """
        Prepare metadata for section-level embeddings.
        
        Args:
            document_uri: URI for the document
            sections: Dictionary of section content
            questions_list: List of individual questions
            conclusion_items: List of individual conclusions
            
        Returns:
            dict: Metadata for generating section-level embeddings
        """
        embedding_metadata = {}
        
        # Process main sections
        for section_name, content in sections.items():
            if content:
                section_uri = f"{document_uri}/{section_name}"
                embedding_metadata[section_uri] = {
                    'type': section_name,
                    'content': content
                }
        
        # Process individual questions
        for i, question in enumerate(questions_list):
            question_uri = f"{document_uri}/question_{i+1}"
            embedding_metadata[question_uri] = {
                'type': 'question_item',
                'content': question
            }
        
        # Process individual conclusions
        for i, conclusion in enumerate(conclusion_items):
            conclusion_uri = f"{document_uri}/conclusion_item_{i+1}"
            embedding_metadata[conclusion_uri] = {
                'type': 'conclusion_item',
                'content': conclusion
            }
        
        return embedding_metadata
