#!/usr/bin/env python3
"""
Direct NSPE Case Importer for Case 23-4
---------------------------------------
Imports the 'Acknowledging Errors in Design' case directly into the database,
bypassing web scraping which may be blocked by Cloudflare protection.

Usage:
    python import_nspe_case_23_4.py
"""

import os
import sys
import json
import logging
import psycopg2
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("direct_nspe_importer")

# Database connection parameters
DB_PARAMS = {
    "dbname": "ai_ethical_dm",
    "user": "postgres",
    "password": "PASS",
    "host": "localhost",
    "port": "5433"
}

# Case data - manually structured
CASE_DATA = {
    "title": "Acknowledging Errors in Design",
    "case_number": "23-4",
    "year": "2023",
    "url": "https://www.nspe.org/career-growth/ethics/board-ethical-review-cases/acknowledging-errors-design",
    "full_text": """Acknowledging Errors in Design

BER Case 23-4

Facts:
Engineer T, a senior structural engineer who designs commercial buildings in the employ of XYZ Consulting Engineers, was in responsible charge of the design of major structural modifications to an existing building. In establishing the project scope for the structural modifications, Engineer T selected a straightforward approach that required making structural connections immediately beneath floor level on an upper floor, in a tightly constrained space. Engineer T proceeded with the project per these parameters and did not explore alternative design approaches. Rather, Engineer T completed the design within the identified constraints and issued construction documents for the modifications.

The contractor began the project using the design criteria. Once the existing floors were exposed at the connection locations, the contractor determined that, due to field conditions related to the age and condition of the building, construction of the design would be far more time-consuming, disruptive, and complex than Engineer T had anticipated in his design. The contractor specifically pointed out the challenges of access in the tight space, the need to support the existing floor during construction, the requirement to use specialized equipment, and the need to perform much of the work from underneath the floor while working from a scaffold.

Engineers U and V, also of XYZ Consulting Engineers, became involved to review potential alternate solutions. Engineer U was involved in a limited capacity to clarify the design intent and requirements. Engineer V was brought in to provide independent review of the overall design, and to explore alternative approaches. Engineer V quickly identified a more effective approach utilizing typical structural framing connections at the side of existing beams. This approach was consistent with the overall requirements of the project but could be more readily constructed with less costly temporary works and less disruption to the building. The advantages of the alternate approach—which would save the client money and accomplish the required structural modifications more effectively, on a more efficient schedule—were obvious to Engineers U and V, who questioned why the alternate approach had not been selected during the design phase.

After reviewing the issue, Engineer T maintained that his design was appropriate, structurally sound, and constructible, and he initially refused to acknowledge the inappropriateness of his approach, both to Engineer V and to the client. Only after the client requested that Engineer V's design be implemented did Engineer T reluctantly agree to implement Engineer V's approach.

Question:
1. What are Engineer T's ethical obligations when it is pointed out that his approach is flawed?

References:
NSPE Code of Ethics - Section I, paragraph 4 - "Engineers, in the fulfillment of their professional duties, shall act for each employer or client as faithful agents or trustees." 
NSPE Code of Ethics - Section II, paragraph 1.a. - "Engineers shall hold paramount the safety, health, and welfare of the public." 
NSPE Code of Ethics - Section II, paragraph 3.a. - "Engineers shall be objective and truthful in professional reports, statements, or testimony. They shall include all relevant and pertinent information in such reports, statements, or testimony, which should bear the date indicating when it was current."
NSPE Code of Ethics - Section II, paragraph 4 - "Engineers shall act for each employer or client as faithful agents or trustees."
NSPE Code of Ethics - Section III, paragraph 1.a. - "Engineers shall be guided in all their relations by the highest standards of honesty and integrity."
NSPE Code of Ethics - Section III, paragraph 1.c. - "Engineers shall not attempt to injure, maliciously or falsely, directly or indirectly, the professional reputation, prospects, practice, or employment of other engineers. Engineers who believe others are guilty of unethical or illegal practice shall present such information to the proper authority for action."
NSPE Code of Ethics - Section III, paragraph 2.a. - "Engineers shall undertake assignments only when qualified by education or experience in the specific technical fields involved."
NSPE Code of Ethics - Section III, paragraph 2.b. - "Engineers shall not affix their signatures to any plans or documents dealing with subject matter in which they lack competence, nor to any plan or document not prepared under their direction and control."
NSPE Code of Ethics - Section III, paragraph 3.a. - "Engineers shall avoid the use of statements containing a material misrepresentation of fact or omitting a material fact."
NSPE Code of Ethics - Section III, paragraph 9.a. - "Engineers shall, whenever possible, name the person or persons who may be individually responsible for designs, inventions, writings, or other accomplishments."

Discussion:
Engineers must always be cognizant of their responsibility to act as faithful agents or trustees of their clients. They are obligated to apply their knowledge and skill to each project based on the client's needs for that project. For each project, engineers should first identify the client's goals and constraints. Understanding the client's goals will inform the engineer's design approach and solution, and highlight the project drivers—that is, the most important factors for success, such as constructability, the structural solution, schedule, budget, visual effect, operational constraints, etc. For Engineer T's project, the goals were to provide structural modifications that would meet the structural requirements in a way that was cost-effective and minimally disruptive to the building owner/occupants.

In this case, it appears that Engineer T fell somewhat short in developing his design approach. While his structural design was technically sound, it was not well suited to the project constraints, and in fact created unnecessary constructability issues that added cost, would have required more complex temporary works than necessary, and would have been more disruptive to the building owner and occupants.

One possible reason for this is that Engineer T did not fully think through the implementation of his approach during construction. It is possible that, had he more thoroughly evaluated his approach, he would have realized the challenges his approach would create for the contractor. This problem could have been exacerbated by his lack of coordination with the contractor during the design process—had the contractor been engaged earlier, constructability issues might have been identified and resolved in the design phase.

However, once those constructability issues were identified, Engineer T had a responsibility to reconsider his design approach in light of the identified constraints, which were not new to the project but simply not fully considered. In fact, the decision-making for this project should have gone further to explore alternative design options.

Design is not simply about creating a technically adequate structural system that performs the function—design requires that engineers identify, weigh, and balance a wide variety of engineering, construction, economic, environmental, societal, and project factors, which include code compliance, structural load paths, constructability, client preferences, budget, schedule, visual preferences, and many other factors. This analysis is inherent to the design process. Once Engineer T was made aware that he had not adequately considered construction issues, it was incumbent upon him to acknowledge those issues, and to revise his approach, if necessary, to better meet the client's needs. The fact that this revision might imply to the client that Engineer T had not done a thorough job was not a valid reason for him to insist on implementing a less than optimal approach.

Instead, Engineer T dug in to his position and insisted that his design was constructible—implying that it was appropriate for the project constraints, which it clearly was not, as he and the client would ultimately acknowledge. In doing so, Engineer T was not acting as a faithful agent to his client. His insistence on continuing with a design that created constructability challenges that increased cost and would have prolonged the schedule and expanded the level of disruption to the building was out of concern for himself and his reputation, not for the client's best interests.

We take no issue with Engineer T's original design approach, which could have been arrived at for a variety of justifiable reasons. However, once the constructability issues were identified, and a more appropriate design approach was identified, it was incumbent upon him to acknowledge the issue and embrace the revised design if it better solved the client's problem. The Board of Ethical Review acknowledges that some degree of personal pride and attachment to one's design approach is natural and appropriate. Perhaps equally natural is the reluctance to acknowledge a shortcoming in one's approach, particularly when that shortcoming is pointed out by another engineer. Nonetheless, engineers must act as faithful agents and trustees of their clients; we must always place our client's best interests ahead of our own pride.

Engineer T was likely in a difficult position: his design was under substantial criticism, his judgment was being questioned, and his mistake was apparent to the clients as well as his colleagues. What Engineer T should have done, once Engineer V identified a more suitable design approach, was to recognize and acknowledge that his approach was difficult to construct in the actual conditions, and to embrace the more suitable approach that Engineer V had identified. From a practical standpoint, most engineers will at some point in their careers need to acknowledge errors in their work, and how they manage that acknowledgment is important—an honest admission of error, coupled with a sincere desire to correct the error, will typically generate greater trust from clients, even if some trust was lost by the error itself. Engineer T's unwillingness to acknowledge the error, until forced to do so by the client, will likely cause the client to have a lower level of trust in Engineer T in the future.

Engineers must also examine the issue of honest representation of project participants. It is unclear whether Engineer T was slated to be identified as the responsible engineer on the final design, but it would have been ethically problematic for him to take full ownership of the final design if it incorporated Engineer V's approach. Section III.9.a. of the NSPE Code of Ethics requires that engineers, "whenever possible, name the person or persons who may be individually responsible for designs, inventions, writings, or other accomplishments." Thus, once Engineer V's design approach is adopted, Engineer V should be recognized appropriately for his contribution.

Conclusions:
It was not ethical for Engineer T to refuse to acknowledge the alternative solution proposed by Engineer V, even after the advantages of the alternative approach were pointed out by Engineers U and V. As engineers, we must act as faithful agents and trustees of our clients, even when doing so requires that we acknowledge errors (or less-than-optimal approaches) and accept that our ego may be bruised in the process.</discourse>
""",
    "description": """Engineer T, a senior structural engineer who designs commercial buildings in the employ of XYZ Consulting Engineers, was in responsible charge of the design of major structural modifications to an existing building. In establishing the project scope for the structural modifications, Engineer T selected a straightforward approach that required making structural connections immediately beneath floor level on an upper floor, in a tightly constrained space. Engineer T proceeded with the project per these parameters and did not explore alternative design approaches. Rather, Engineer T completed the design within the identified constraints and issued construction documents for the modifications.

The contractor began the project using the design criteria. Once the existing floors were exposed at the connection locations, the contractor determined that, due to field conditions related to the age and condition of the building, construction of the design would be far more time-consuming, disruptive, and complex than Engineer T had anticipated in his design. The contractor specifically pointed out the challenges of access in the tight space, the need to support the existing floor during construction, the requirement to use specialized equipment, and the need to perform much of the work from underneath the floor while working from a scaffold.

Engineers U and V, also of XYZ Consulting Engineers, became involved to review potential alternate solutions. Engineer U was involved in a limited capacity to clarify the design intent and requirements. Engineer V was brought in to provide independent review of the overall design, and to explore alternative approaches. Engineer V quickly identified a more effective approach utilizing typical structural framing connections at the side of existing beams. This approach was consistent with the overall requirements of the project but could be more readily constructed with less costly temporary works and less disruption to the building. The advantages of the alternate approach—which would save the client money and accomplish the required structural modifications more effectively, on a more efficient schedule—were obvious to Engineers U and V, who questioned why the alternate approach had not been selected during the design phase.

After reviewing the issue, Engineer T maintained that his design was appropriate, structurally sound, and constructible, and he initially refused to acknowledge the inappropriateness of his approach, both to Engineer V and to the client. Only after the client requested that Engineer V's design be implemented did Engineer T reluctantly agree to implement Engineer V's approach.""",
    "decision": """It was not ethical for Engineer T to refuse to acknowledge the alternative solution proposed by Engineer V, even after the advantages of the alternative approach were pointed out by Engineers U and V. As engineers, we must act as faithful agents and trustees of our clients, even when doing so requires that we acknowledge errors (or less-than-optimal approaches) and accept that our ego may be bruised in the process.""",
    "sections": {
        "facts": "Engineer T, a senior structural engineer who designs commercial buildings in the employ of XYZ Consulting Engineers, was in responsible charge of the design of major structural modifications to an existing building. In establishing the project scope for the structural modifications, Engineer T selected a straightforward approach that required making structural connections immediately beneath floor level on an upper floor, in a tightly constrained space. Engineer T proceeded with the project per these parameters and did not explore alternative design approaches. Rather, Engineer T completed the design within the identified constraints and issued construction documents for the modifications.",
        "question": "What are Engineer T's ethical obligations when it is pointed out that his approach is flawed?",
        "references": "NSPE Code of Ethics - Section I, paragraph 4 - \"Engineers, in the fulfillment of their professional duties, shall act for each employer or client as faithful agents or trustees.\"",
        "discussion": "Engineers must always be cognizant of their responsibility to act as faithful agents or trustees of their clients. They are obligated to apply their knowledge and skill to each project based on the client's needs for that project.",
        "conclusion": "It was not ethical for Engineer T to refuse to acknowledge the alternative solution proposed by Engineer V, even after the advantages of the alternative approach were pointed out by Engineers U and V. As engineers, we must act as faithful agents and trustees of our clients, even when doing so requires that we acknowledge errors (or less-than-optimal approaches) and accept that our ego may be bruised in the process."
    },
    "metadata": {
        "imported_directly": True,
        "scraped_at": None,
        "imported_at": datetime.now().isoformat()
    }
}

def get_db_connection():
    """Create a connection to the database."""
    try:
        logger.debug(f"Connecting to database: {DB_PARAMS['dbname']} on {DB_PARAMS['host']}:{DB_PARAMS['port']}")
        conn = psycopg2.connect(**DB_PARAMS)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        return None

def store_case(case_data):
    """
    Store a case in the database.
    
    Args:
        case_data: Dictionary containing case information
        
    Returns:
        int: The ID of the document in the database, or None if failed
    """
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cur = conn.cursor()
        
        # Extract core fields
        title = case_data.get('title', '')
        case_number = case_data.get('case_number', '')
        year = case_data.get('year', '')
        full_text = case_data.get('full_text', '')
        description = case_data.get('description', '')
        decision = case_data.get('decision', '')
        url = case_data.get('url', '')
        
        # Prepare metadata
        metadata = {
            "case_number": case_number,
            "year": year,
            "sections": case_data.get("sections", {})
        }
        
        # Add any additional metadata
        if 'metadata' in case_data and isinstance(case_data['metadata'], dict):
            for key, value in case_data['metadata'].items():
                metadata[key] = value
                
        metadata_json = json.dumps(metadata)
        
        # Check if the case already exists in the database
        cur.execute(
            """
            SELECT id FROM documents 
            WHERE doc_metadata->>'case_number' = %s
            """,
            (case_number,)
        )
        
        existing_id = cur.fetchone()
        
        if existing_id:
            # Update existing case
            document_id = existing_id[0]
            logger.info(f"Updating existing case {case_number} with ID {document_id}")
            
            cur.execute(
                """
                UPDATE documents
                SET title = %s,
                    content = %s,
                    doc_metadata = %s,
                    source = %s,
                    updated_at = %s
                WHERE id = %s
                RETURNING id
                """,
                (
                    title,
                    full_text,
                    metadata_json,
                    url,
                    datetime.now(),
                    document_id
                )
            )
            
            # Also update the case data in documents_content
            cur.execute(
                """
                SELECT id FROM documents_content
                WHERE document_id = %s
                """,
                (document_id,)
            )
            
            existing_content = cur.fetchone()
            
            if existing_content:
                # Update existing content
                cur.execute(
                    """
                    UPDATE documents_content
                    SET description = %s,
                        decision = %s,
                        updated_at = %s
                    WHERE document_id = %s
                    """,
                    (
                        description,
                        decision,
                        datetime.now(),
                        document_id
                    )
                )
            else:
                # Insert new content
                cur.execute(
                    """
                    INSERT INTO documents_content
                    (document_id, description, decision, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        document_id,
                        description,
                        decision,
                        datetime.now()
                    )
                )
        else:
            # Insert new case
            logger.info(f"Inserting new case: {title}")
            
            cur.execute(
                """
                INSERT INTO documents
                (title, content, document_type, source, doc_metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    title,
                    full_text,
                    "case",
                    url,
                    metadata_json,
                    datetime.now()
                )
            )
            
            document_id = cur.fetchone()[0]
            
            # Insert into documents_content
            cur.execute(
                """
                INSERT INTO documents_content
                (document_id, description, decision, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    document_id,
                    description,
                    decision,
                    datetime.now()
                )
            )
            
            logger.info(f"Inserted new case with ID {document_id}")
        
        # Commit the transaction
        conn.commit()
        
        # Close connection
        cur.close()
        conn.close()
        
        return document_id
        
    except Exception as e:
        logger.error(f"Error storing case: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Rollback transaction if an error occurred
        if 'conn' in locals() and conn:
            conn.rollback()
            
            # Close connections
            if 'cur' in locals() and cur:
                cur.close()
                
            conn.close()
            
        return None

def main():
    """Main execution function."""
    logger.info(f"Starting direct import of NSPE Case #{CASE_DATA['case_number']}: {CASE_DATA['title']}")
    
    # Store the case in the database
    document_id = store_case(CASE_DATA)
    
    if document_id:
        logger.info(f"Successfully imported case with ID {document_id}")
        logger.info(f"Case can be viewed at: http://127.0.0.1:3333/cases/{document_id}")
    else:
        logger.error("Failed to import case")
        sys.exit(1)
    
    logger.info("Import completed successfully")
    return document_id

if __name__ == "__main__":
    main()
