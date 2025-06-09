-- Create table for storing ontology term links within document sections
-- This table stores individual words/phrases that match ontology terms

CREATE TABLE IF NOT EXISTS section_term_links (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    section_id VARCHAR(100) NOT NULL, -- e.g., 'facts', 'discussion', 'conclusion'
    term_text VARCHAR(500) NOT NULL, -- The actual word/phrase found in the text
    term_start INTEGER NOT NULL, -- Character position where term starts
    term_end INTEGER NOT NULL, -- Character position where term ends  
    ontology_uri VARCHAR(500) NOT NULL, -- URI of the matching ontology concept
    ontology_label VARCHAR(500), -- Human-readable label from ontology
    definition TEXT, -- Definition/description from ontology
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_section_term_links_document 
        FOREIGN KEY (document_id) REFERENCES documents(id) 
        ON DELETE CASCADE,
    
    -- Indexes for performance
    CONSTRAINT section_term_links_unique 
        UNIQUE (document_id, section_id, term_start, term_end, ontology_uri)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_section_term_links_document_id ON section_term_links(document_id);
CREATE INDEX IF NOT EXISTS idx_section_term_links_section_id ON section_term_links(document_id, section_id);
CREATE INDEX IF NOT EXISTS idx_section_term_links_ontology_uri ON section_term_links(ontology_uri);

-- Add comments
COMMENT ON TABLE section_term_links IS 'Links individual words/phrases in document sections to ontology terms';
COMMENT ON COLUMN section_term_links.term_start IS 'Character position where the term starts in the section text';
COMMENT ON COLUMN section_term_links.term_end IS 'Character position where the term ends in the section text';
COMMENT ON COLUMN section_term_links.ontology_uri IS 'URI of the matching concept in the engineering-ethics ontology';