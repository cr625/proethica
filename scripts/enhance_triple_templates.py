#!/usr/bin/env python3
"""
Script to enhance the triple templates in the edit_case_triples.html template.
This adds more categorized template examples based on namespaces to help users
understand what terms are available when editing triples.
"""

import os
import re
import sys
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Path to the template file
TEMPLATE_PATH = Path("app/templates/edit_case_triples.html")

# New templates to add, categorized by namespace
NEW_TEMPLATES = {
    "Dublin Core": [
        {
            "subject": "Case:ThisCase",
            "predicate": "dc:creator",
            "object": "Engineer",
            "description": "Engineer as creator",
            "is_literal": True
        },
        {
            "subject": "Case:ThisCase", 
            "predicate": "dc:subject", 
            "object": "Engineering Ethics",
            "description": "Subject: Engineering Ethics",
            "is_literal": True
        },
        {
            "subject": "Case:ThisCase", 
            "predicate": "dc:date", 
            "object": "2025-04-06",
            "description": "Date Published",
            "is_literal": True
        }
    ],
    "Basic Formal Ontology": [
        {
            "subject": "Case:ThisCase", 
            "predicate": "bfo:hasParticipant", 
            "object": "ENG_ETHICS:Engineer",
            "description": "Has Participant: Engineer",
            "is_literal": False
        },
        {
            "subject": "ENG_ETHICS:Decision", 
            "predicate": "bfo:occursIn", 
            "object": "Case:ThisCase",
            "description": "Decision occurs in Case",
            "is_literal": False
        }
    ],
    "Time-Based Relations": [
        {
            "subject": "Case:ThisCase", 
            "predicate": "time:hasBeginning", 
            "object": "2025-01-01",
            "description": "Case Start Date",
            "is_literal": True
        },
        {
            "subject": "ENG_ETHICS:Event1", 
            "predicate": "time:before", 
            "object": "ENG_ETHICS:Event2",
            "description": "Event1 before Event2",
            "is_literal": False
        }
    ],
    "Engineering Ethics Context": [
        {
            "subject": "Case:ThisCase", 
            "predicate": "involves:Context", 
            "object": "ENG_ETHICS:Professional",
            "description": "Professional Context",
            "is_literal": False
        },
        {
            "subject": "Case:ThisCase", 
            "predicate": "involves:Context", 
            "object": "ENG_ETHICS:Academic",
            "description": "Academic Context",
            "is_literal": False
        },
        {
            "subject": "Case:ThisCase", 
            "predicate": "involves:Context", 
            "object": "ENG_ETHICS:Government",
            "description": "Government Context",
            "is_literal": False
        }
    ],
    "Ethics Reasoning": [
        {
            "subject": "Decision:Ethical", 
            "predicate": "eth:basedOn", 
            "object": "ENG_ETHICS:UtilitarianPrinciple",
            "description": "Based on Utilitarian Principle",
            "is_literal": False
        },
        {
            "subject": "Decision:Unethical", 
            "predicate": "eth:conflicts", 
            "object": "NSPE:CodeII.1",
            "description": "Conflicts with Code II.1",
            "is_literal": False
        },
        {
            "subject": "ENG_ETHICS:Action", 
            "predicate": "eth:consequencesInclude", 
            "object": "Public harm",
            "description": "Consequences: Public Harm",
            "is_literal": True
        }
    ],
    "NSPE Code References": [
        {
            "subject": "Case:ThisCase", 
            "predicate": "references:Code", 
            "object": "NSPE:CodeI.1",
            "description": "References Code I.1 (Safety)",
            "is_literal": False
        },
        {
            "subject": "Case:ThisCase", 
            "predicate": "references:Code", 
            "object": "NSPE:CodeII.1.c",
            "description": "References Code II.1.c (Confidentiality)",
            "is_literal": False 
        },
        {
            "subject": "Case:ThisCase", 
            "predicate": "references:Code", 
            "object": "NSPE:CodeII.3.a",
            "description": "References Code II.3.a (Objectivity)",
            "is_literal": False
        }
    ],
    "Relationships": [
        {
            "subject": "Case:ThisCase", 
            "predicate": "belongsTo", 
            "object": "World:1",
            "description": "Belongs to Engineering World",
            "is_literal": False
        },
        {
            "subject": "ENG_ETHICS:Engineer", 
            "predicate": "hasRole", 
            "object": "ENG_ETHICS:Consultant",
            "description": "Engineer has Consultant Role",
            "is_literal": False
        }
    ]
}

def generate_template_button_html(template):
    """Generate HTML for a template button"""
    literal_value = "true" if template["is_literal"] else "false"
    return f"""
    <button type="button" class="btn btn-sm btn-outline-success mb-1 template-btn"
        data-subject="{template['subject']}" data-predicate="{template['predicate']}"
        data-object="{template['object']}" data-is-literal="{literal_value}">
        {template['description']}
    </button>"""

def generate_template_section_html(category, templates):
    """Generate HTML for a category of templates"""
    buttons_html = "\n".join(generate_template_button_html(template) for template in templates)
    return f"""
    <div class="mb-3">
        <h5>{category}</h5>
        {buttons_html}
    </div>"""

def enhance_template():
    """Enhance the edit_case_triples.html template with more triple template examples"""
    try:
        # Read the template file
        with open(TEMPLATE_PATH, 'r') as file:
            content = file.read()
        
        # Find the Triple Templates section
        pattern = r'<div class="card-body">\s*<div class="mb-3">\s*<h5>Common Engineering Ethics Patterns</h5>.*?</div>\s*</div>'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            print("Could not find the Triple Templates section in the template.")
            return False
        
        # Generate new template sections HTML
        new_templates_html = ""
        for category, templates in NEW_TEMPLATES.items():
            new_templates_html += generate_template_section_html(category, templates)
        
        # Create the full replacement content
        replacement = f"""<div class="card-body">
            <div class="mb-3">
                <h5>Common Engineering Ethics Patterns</h5>
                <button type="button" class="btn btn-sm btn-outline-success mb-1 template-btn"
                    data-subject="Case:ThisCase" data-predicate="involves:EthicalPrinciple"
                    data-object="ENG_ETHICS:PublicSafety">
                    Case involves Public Safety
                </button>
                <button type="button" class="btn btn-sm btn-outline-success mb-1 template-btn"
                    data-subject="Case:ThisCase" data-predicate="involves:EthicalPrinciple"
                    data-object="ENG_ETHICS:Confidentiality">
                    Case involves Confidentiality
                </button>
                <button type="button" class="btn btn-sm btn-outline-success mb-1 template-btn"
                    data-subject="Case:ThisCase" data-predicate="hasConflict"
                    data-object="ENG_ETHICS:ConfidentialityVsSafety">
                    Conflict: Confidentiality vs Safety
                </button>
                <button type="button" class="btn btn-sm btn-outline-success mb-1 template-btn"
                    data-subject="Case:ThisCase" data-predicate="references:Code" data-object="NSPE:CodeI.1">
                    References NSPE Code I.1
                </button>
                <button type="button" class="btn btn-sm btn-outline-success mb-1 template-btn"
                    data-subject="NSPE:CodeI.1" data-predicate="overrides" data-object="NSPE:CodeII.1.c">
                    Code I.1 overrides Code II.1.c
                </button>
                <button type="button" class="btn btn-sm btn-outline-success mb-1 template-btn"
                    data-subject="Case:ThisCase" data-predicate="hasDecision" data-object="Decision:Unethical">
                    Decision: Unethical
                </button>
            </div>
            {new_templates_html}
        </div>"""
        
        # Update template button JavaScript to handle the is_literal attribute
        updated_content = content.replace(match.group(0), replacement)
        
        # Update the JavaScript for template buttons to handle the is_literal attribute
        js_pattern = r'document\.querySelectorAll\(\'\.template-btn\'\)\.forEach\(button => \{.*?\}\)\;'
        js_replacement = """document.querySelectorAll('.template-btn').forEach(button => {
            button.addEventListener('click', function () {
                // Get the template data
                const subject = this.getAttribute('data-subject');
                const predicate = this.getAttribute('data-predicate');
                const object = this.getAttribute('data-object');
                const isLiteral = this.getAttribute('data-is-literal') === 'true';

                // Add a new triple row with this data
                const container = document.getElementById('triplesContainer');
                const newRow = document.createElement('div');
                newRow.className = 'triple-row mb-3';
                newRow.innerHTML = `
                    <div class="row g-2">
                        <div class="col-md-3">
                            <input type="text" class="form-control" name="subjects[]" placeholder="Subject" value="${subject}" required>
                        </div>
                        <div class="col-md-3">
                            <input type="text" class="form-control" name="predicates[]" placeholder="Predicate" value="${predicate}" required>
                        </div>
                        <div class="col-md-4">
                            <input type="text" class="form-control" name="objects[]" placeholder="Object" value="${object}" required>
                        </div>
                        <div class="col-md-2">
                            <select class="form-select" name="is_literals[]">
                                <option value="true" ${isLiteral ? 'selected' : ''}>Literal</option>
                                <option value="false" ${!isLiteral ? 'selected' : ''}>URI</option>
                            </select>
                        </div>
                    </div>
                `;
                container.appendChild(newRow);
            });
        });"""
        
        updated_content = re.sub(js_pattern, js_replacement, updated_content, flags=re.DOTALL)
        
        # Write the updated template back to the file
        with open(TEMPLATE_PATH, 'w') as file:
            file.write(updated_content)
        
        print(f"Successfully enhanced the triple templates in {TEMPLATE_PATH}")
        print(f"Added {sum(len(templates) for templates in NEW_TEMPLATES.values())} new template examples in {len(NEW_TEMPLATES)} categories")
        return True
    
    except Exception as e:
        print(f"Error enhancing template: {e}")
        return False

if __name__ == "__main__":
    # Create a backup of the template file first
    backup_path = f"{TEMPLATE_PATH}.bak"
    try:
        with open(TEMPLATE_PATH, 'r') as src, open(backup_path, 'w') as dst:
            dst.write(src.read())
        print(f"Created backup at {backup_path}")
    except Exception as e:
        print(f"Warning: Could not create backup: {e}")
    
    # Enhance the template
    if enhance_template():
        print("Template enhancement completed successfully.")
    else:
        print("Template enhancement failed.")
