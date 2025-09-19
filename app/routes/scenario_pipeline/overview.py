"""
Step 1: Content Review Route

Handles the first step of the interactive scenario pipeline - content review and analysis.
Uses the segmentation infrastructure from scenario_pipeline for consistent section processing.
Formats sections optimally for LLM consumption with enumerated questions and conclusions.
"""

import logging
from flask import render_template, redirect, url_for, flash
from app.models import Document
from app.services.scenario_pipeline.segmenter import segment_sections
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def _clean_text_whitespace(text):
    """
    Clean up excessive whitespace from extracted text while preserving readable structure.
    """
    if not text:
        return ""
    
    import re
    
    # Remove PostgreSQL line continuation markers and similar artifacts
    cleaned = re.sub(r'\s*\+\s*', ' ', text)
    
    # First pass: normalize all whitespace to single spaces
    cleaned = re.sub(r'\s+', ' ', cleaned.strip())
    
    # Handle sentence breaks: period followed by capital letter gets a line break
    cleaned = re.sub(r'\.([A-Z])', r'.\n\n\1', cleaned)
    
    # Handle other common sentence endings
    cleaned = re.sub(r'([.!?])\s+([A-Z])', r'\1\n\n\2', cleaned)
    
    # Clean up excessive line breaks (max 2 consecutive newlines = 1 blank line)
    cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
    cleaned = re.sub(r'\n\s+', '\n', cleaned)  # Remove spaces after newlines
    
    # Final cleanup
    return cleaned.strip()

def _extract_individual_questions(html):
    """
    Extract individual questions from HTML content, particularly from ordered lists.
    Adapted from NSPECaseExtractionStep for LLM-optimal formatting.
    """
    if not html:
        return []
        
    # Parse the HTML
    soup = BeautifulSoup(html, 'html.parser')
    questions = []
    
    # Look for ordered lists first (most common format for multiple questions)
    ordered_list = soup.find('ol')
    if ordered_list:
        for item in ordered_list.find_all('li'):
            questions.append(item.get_text().strip())
        return questions
    
    # If no ordered list, check for unordered lists
    unordered_list = soup.find('ul')
    if unordered_list:
        for item in unordered_list.find_all('li'):
            questions.append(item.get_text().strip())
        return questions
    
    # If no lists, try to split on numbered patterns
    text = soup.get_text()
    if any(pattern in text for pattern in ['1.', '2.', '1)', '2)']):
        # Split on numbered patterns and clean up
        import re
        parts = re.split(r'\d+[\.\)]\s*', text)
        questions = [part.strip() for part in parts if part.strip()]
        return questions[1:] if len(questions) > 1 else questions  # Skip empty first part
    
    # If no numbered patterns, try to split on question marks
    if '?' in text:
        import re
        # Split on question marks and reconstruct questions
        parts = text.split('?')
        questions = []
        for i, part in enumerate(parts[:-1]):  # Exclude the last empty part after final ?
            question = part.strip()
            if question:  # Skip empty parts
                question += '?'  # Add the question mark back
                questions.append(question)
        
        # If the original text doesn't end with ?, the last part might be a question too
        last_part = parts[-1].strip()
        if last_part and not text.strip().endswith('?'):
            questions.append(last_part)
            
        return [q.strip() for q in questions if q.strip()]
    
    return []

def _extract_individual_conclusions(html):
    """
    Extract individual conclusion items from HTML content.
    Uses the same logic as NSPECaseExtractionStep._extract_individual_conclusions().
    """
    if not html:
        return []
        
    # Parse the HTML
    soup = BeautifulSoup(html, 'html.parser')
    conclusions = []
    
    # Look for ordered lists first (most common format for multiple conclusion items)
    ordered_list = soup.find('ol')
    if ordered_list:
        # Extract each list item as a separate conclusion item
        for item in ordered_list.find_all('li'):
            conclusions.append(item.get_text().strip())
        return conclusions
    
    # If no ordered list is found, check for unordered lists
    unordered_list = soup.find('ul')
    if unordered_list:
        for item in unordered_list.find_all('li'):
            conclusions.append(item.get_text().strip())
        return conclusions
    
    # If no list is found, try to find numbered items in the text
    # This handles cases where numbers are used but not in HTML list format
    text_content = soup.get_text().strip()
    if text_content:
        import re
        # Look for patterns like "1.", "2.", "(1)", "(2)" at the beginning of lines or sentences
        numbered_items = re.findall(r'(?:^|\n|\.\s+)(\(\d+\)|\d+\.)\s+([^\(\d\n\.]+?)(?=\n\s*\(\d+\)|\n\s*\d+\.|\Z)', text_content)
        if numbered_items:
            for _, item_text in numbered_items:
                conclusions.append(item_text.strip())
            return conclusions
        
        # If no numbered items found, use the entire content as a single conclusion
        conclusions.append(text_content)
        
    return conclusions

def _format_section_for_llm(section_key, section_data, case_doc=None):
    """
    Format section data optimally for LLM consumption.
    Preserves original enumerated HTML and creates clean text versions.
    """
    if not section_data:
        return None
    
    # Handle both dict and string section data
    original_section_data = section_data  # Preserve original for later access
    if isinstance(section_data, dict):
        title = section_data.get('title', section_key.replace('_', ' ').title())
        html_content = section_data.get('html', section_data.get('content', ''))
        # Check if there are already extracted questions/conclusions from NSPE processing
        existing_questions = section_data.get('questions', [])
        existing_conclusions = section_data.get('conclusions', [])
    else:
        title = section_key.replace('_', ' ').title()
        html_content = str(section_data) if section_data else ''
        existing_questions = []
        existing_conclusions = []
    
    formatted_section = {
        'title': title,
        'html': html_content,  # Preserve original enumerated HTML
        'raw_key': section_key
    }
    
    # Special processing for questions and conclusions
    if 'question' in section_key.lower():
        # Use existing extracted questions if available, otherwise extract them
        questions_list = existing_questions or _extract_individual_questions(html_content)
        
        # Fallback if primary extraction didn't work
        if not questions_list and html_content and '?' in html_content:
            # General fallback - split on question marks
            parts = html_content.split('?')
            questions_list = [part.strip() + '?' for part in parts[:-1] if part.strip()]
        
        if questions_list:
            formatted_section['individual_questions'] = questions_list
            # Create clean LLM text without HTML markup
            formatted_section['llm_text'] = f"{title}:\n" + "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions_list))
        else:
            # Fallback: Remove HTML tags for clean LLM text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove empty elements that contribute to whitespace
            for element in soup.find_all():
                if not element.get_text(strip=True):
                    element.decompose()
            
            clean_text = _clean_text_whitespace(soup.get_text(separator=' ', strip=True))
            formatted_section['llm_text'] = f"{title}:\n{clean_text}"
    
    elif 'conclusion' in section_key.lower():
        # For conclusions, use the same logic as cases.py - check for pre-parsed conclusion_items first
        case_conclusion_items = []
        if case_doc and case_doc.doc_metadata:
            case_conclusion_items = case_doc.doc_metadata.get('conclusion_items', [])
        
        # Use pre-parsed conclusion items if available, otherwise extract from HTML
        conclusions_list = case_conclusion_items or existing_conclusions or _extract_individual_conclusions(html_content)
        if conclusions_list:
            formatted_section['individual_conclusions'] = conclusions_list
            # Create clean LLM text without HTML markup
            formatted_section['llm_text'] = f"{title}:\n" + "\n".join(f"{i+1}. {c}" for i, c in enumerate(conclusions_list))
        else:
            # Fallback: Remove HTML tags for clean LLM text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove empty elements that contribute to whitespace
            for element in soup.find_all():
                if not element.get_text(strip=True):
                    element.decompose()
            
            clean_text = _clean_text_whitespace(soup.get_text(separator=' ', strip=True))
            formatted_section['llm_text'] = f"{title}:\n{clean_text}"
    
    else:
        # For other sections, provide clean text
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Special handling for References section - use text version if available
        if section_key.lower() == 'references' and isinstance(original_section_data, dict) and 'text' in original_section_data:
            # Use the pre-extracted text version from NSPE extraction
            text_content = original_section_data['text']
            if text_content:
                # Clean the text version which already has structured content
                clean_text = _clean_text_whitespace(text_content)
                
                # Further structure the references by splitting on code patterns  
                import re
                # Split on NSPE code patterns (I.1., II.3.a., etc.)
                parts = re.split(r'(\b[IVX]+\.\d+\.?[a-z]?\.)\s+', clean_text)
                references = {}  # Use dict to avoid duplicates
                
                for i in range(1, len(parts), 2):  # Skip first empty part, then take pairs
                    if i + 1 < len(parts):
                        code = parts[i].strip()
                        content = parts[i + 1].strip()
                        # Remove "Subject Reference" and all subsequent metadata text
                        content = re.sub(r'\s*Subject Reference.*$', '', content, flags=re.DOTALL | re.IGNORECASE)
                        
                        # Enhanced deduplication: remove repetitive phrases and sentences
                        # First, split into sentences and remove duplicates
                        sentences = re.split(r'(?<=[.!?])\s+', content)
                        unique_sentences = []
                        seen_sentences = set()
                        
                        for sentence in sentences:
                            sentence_clean = sentence.strip().rstrip('.!?')
                            # Normalize whitespace and case for comparison
                            sentence_normalized = re.sub(r'\s+', ' ', sentence_clean.lower())
                            
                            # Skip if we've seen this sentence before or if it's too short
                            if sentence_normalized and sentence_normalized not in seen_sentences and len(sentence_normalized) > 10:
                                unique_sentences.append(sentence.strip())
                                seen_sentences.add(sentence_normalized)
                        
                        content = ' '.join(unique_sentences)
                        
                        # Additional cleanup: remove repeated phrases within the content
                        # Look for patterns where the same phrase appears multiple times
                        words = content.split()
                        if len(words) > 20:  # Only apply to longer content
                            # Find and remove repeated segments of 5+ words
                            for window_size in range(10, 5, -1):
                                i = 0
                                while i < len(words) - window_size:
                                    segment = ' '.join(words[i:i+window_size])
                                    # Look for this segment later in the text
                                    remaining_text = ' '.join(words[i+window_size:])
                                    if segment in remaining_text:
                                        # Remove the duplicate occurrence
                                        words_after = ' '.join(words[i+window_size:]).replace(segment, '', 1).split()
                                        words = words[:i+window_size] + words_after
                                        break
                                    i += 1
                            content = ' '.join(words)
                        
                        # Final cleanup: ensure proper sentence structure
                        content = re.sub(r'\s+', ' ', content).strip()
                        if content and not content.endswith('.'):
                            content += '.'
                        
                        if content and code not in references:
                            references[code] = content
                
                if references:
                    # Sort by NSPE code order (I.1, I.4, II.1.a, etc.)
                    sorted_refs = sorted(references.items(), key=lambda x: (
                        len(x[0].split('.')),  # Primary sort: I.1 before II.1.a
                        x[0]  # Secondary sort: alphabetical
                    ))
                    clean_text = '\n\n'.join([f"{code}: {content}" for code, content in sorted_refs])
            else:
                # Fallback to HTML processing
                clean_text = _clean_text_whitespace(soup.get_text(separator=' ', strip=True))
        else:
            # Remove empty elements that contribute to whitespace
            for element in soup.find_all():
                if not element.get_text(strip=True):
                    element.decompose()
            
            clean_text = _clean_text_whitespace(soup.get_text(separator=' ', strip=True))
        
        formatted_section['llm_text'] = f"{title}:\n{clean_text}"
    
    return formatted_section

def step1(case_id):
    """
    Step 1: Content Review
    Shows case content divided by sections for review and analysis.
    """
    try:
        # Get the case
        case = Document.query.get_or_404(case_id)
        
        # Extract and normalize sections from case metadata - prioritize sections_dual for LLM formatting
        raw_sections = {}
        if case.doc_metadata:
            # Priority 1: sections_dual (contains formatted HTML with enumerated lists)
            if 'sections_dual' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections_dual']
            # Priority 2: sections (basic sections)
            elif 'sections' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections']
            # Priority 3: document_structure sections
            elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
                raw_sections = case.doc_metadata['document_structure']['sections']
        
        # If no sections found, create basic structure
        if not raw_sections:
            raw_sections = {
                'full_content': case.content or 'No content available'
            }
        
        # Process sections for LLM-optimal display with enumerated questions/conclusions
        sections = {}
        
        # Debug: Log the structure of sections_dual for case 8
        if case_id == 8 and raw_sections:
            logger.info(f"Case 8 sections_dual structure:")
            for key, section in raw_sections.items():
                logger.info(f"  {key}: {type(section)} - {list(section.keys()) if isinstance(section, dict) else 'not dict'}")
                if isinstance(section, dict) and 'html' in section:
                    logger.info(f"    html preview: {section['html'][:100]}...")
        
        for section_key, section_content in raw_sections.items():
            # Format each section for LLM consumption, passing the case document for metadata access
            formatted_section = _format_section_for_llm(section_key, section_content, case_doc=case)
            if formatted_section:
                sections[section_key] = formatted_section
        
        # Use segmentation infrastructure for additional processing if needed
        if len(sections) > 1:
            try:
                # This adds paragraph and sentence segmentation for advanced processing
                segmentation_data = segment_sections(raw_sections)
                logger.debug(f"Segmentation identified {len(segmentation_data.get('sentences', []))} sentences and {len(segmentation_data.get('paragraphs', []))} paragraphs")
            except Exception as e:
                logger.warning(f"Segmentation processing failed: {e}")
        
        # Template context
        context = {
            'case': case,
            'sections': sections,
            'current_step': 1,
            'next_step_url': url_for('scenario_pipeline.step2', case_id=case_id),  # Go to Step 2
            'prev_step_url': None  # No previous step
        }
        
        return render_template('scenarios/overview.html', **context)
        
    except Exception as e:
        logger.error(f"Error loading step 1 for case {case_id}: {str(e)}")
        flash(f'Error loading step 1: {str(e)}', 'danger')
        return redirect(url_for('cases.view_case', id=case_id))

def debug_step1(case_id):
    """Debug endpoint to see section processing"""
    try:
        case = Document.query.get_or_404(case_id)
        raw_sections = {}
        if case.doc_metadata and 'sections_dual' in case.doc_metadata:
            raw_sections = case.doc_metadata['sections_dual']
        
        result = []
        for section_key, section_content in raw_sections.items():
            if 'question' in section_key.lower():
                formatted_section = _format_section_for_llm(section_key, section_content, case_doc=case)
                result.append({
                    'section_key': section_key,
                    'section_type': type(section_content).__name__,
                    'section_keys': list(section_content.keys()) if isinstance(section_content, dict) else None,
                    'html_content': section_content.get('html', '')[:200] if isinstance(section_content, dict) else str(section_content)[:200],
                    'has_individual_questions': 'individual_questions' in formatted_section,
                    'questions_count': len(formatted_section.get('individual_questions', [])),
                    'questions': formatted_section.get('individual_questions', [])
                })
        
        from flask import jsonify
        return jsonify(result)
        
    except Exception as e:
        from flask import jsonify
        return jsonify({'error': str(e)})