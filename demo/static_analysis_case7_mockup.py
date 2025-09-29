#!/usr/bin/env python3
"""
Static Analysis Mockup for Case 7: AI Ethics in Engineering Practice

This mockup demonstrates how the static scenario analysis would present
the ethical considerations for each decision point without revealing
NSPE's conclusions, following the ProEthica framework.
"""

import json
from datetime import datetime
from typing import Dict, List, Any

# Mockup data structure for Case 7 static analysis
CASE_7_STATIC_ANALYSIS = {
    "scenario": {
        "id": 7,
        "name": "AI Ethics in Engineering Practice: Engineer A's Dilemma",
        "description": "Engineer A faces ethical decisions about using AI tools for environmental engineering reports and design documents.",
        "case_reference": "NSPE BER Case 24-02"
    },
    "metadata": {
        "generated_at": datetime.utcnow().isoformat(),
        "analysis_version": "1.0",
        "llm_provider": "mcp_server_mockup"
    },
    "timeline": [
        {
            "type": "event",
            "title": "Project Assignment",
            "time": "Day 0",
            "description": "Client W retains Engineer A's environmental engineering firm to prepare a comprehensive report on organic compound contamination and design documents for groundwater infrastructure modifications.",
            "details": "Engineer A is an experienced environmental engineer with PE license. The project requires both strong technical analysis and professional report writing."
        },
        {
            "type": "event", 
            "title": "Loss of Writing Support",
            "time": "Day 5",
            "description": "Engineer B, who previously provided writing guidance, announces retirement.",
            "details": "Engineer A recognizes a gap in writing support but remains confident in technical expertise."
        },
        {
            "type": "event",
            "title": "AI Tool Discovery",
            "time": "Day 10",
            "description": "Engineer A discovers open-source AI writing and drafting tools that could assist with report generation.",
            "details": "The tools promise to help with professional writing while maintaining technical accuracy."
        },
        {
            "type": "decision",
            "title": "Decision Point 1: AI-Generated Report Text",
            "time": "Day 12",
            "question": "Should Engineer A use AI to generate the report text, even with thorough technical review?",
            "context": "Engineer A considers using AI to create the report narrative, planning to input client data and thoroughly review all output.",
            "options": [
                {
                    "id": "opt1",
                    "title": "Use AI with Comprehensive Technical Review",
                    "description": "Generate report text using AI, then conduct thorough technical review to ensure accuracy and completeness.",
                    "arguments_for": [
                        "Maintains technical competence through careful review process <strong>[I.2]</strong>",
                        "Leverages technology to improve efficiency and writing quality <em class='weak-ref'>[III.8.a]</em>",
                        "Ensures accuracy through professional verification <strong>[II.2.a]</strong>",
                        "Allows focus on technical analysis rather than writing mechanics <em class='weak-ref'>[I.2]</em>"
                    ],
                    "arguments_against": [
                        "May violate client confidentiality by sharing data with AI system <strong>[II.1.c]</strong>",
                        "Risks not properly attributing AI-generated content <strong>[III.9]</strong>",
                        "Could miss nuanced technical issues in AI output <strong>[I.2, II.2.a]</strong>",
                        "May not fully understand AI's reasoning process <strong>[II.2.b]</strong>"
                    ],
                    "supporting_codes": ["I.2 - Perform services only in areas of competence"],
                    "precedent_cases": ["BER Case 90-6 - Computer tools acceptable with oversight"]
                },
                {
                    "id": "opt2",
                    "title": "Avoid AI Due to Confidentiality Concerns",
                    "description": "Reject AI use because it requires sharing client's confidential data with external systems.",
                    "arguments_for": [
                        "Protects client confidentiality absolutely <strong>[II.1.c]</strong>",
                        "Maintains full control over work product <strong>[II.2.b]</strong>",
                        "Avoids potential citation and attribution issues <strong>[III.9]</strong>",
                        "Ensures personal understanding of all content <strong>[I.2, II.2.a]</strong>"
                    ],
                    "arguments_against": [
                        "May produce lower quality writing without support <em class='weak-ref'>[I.1]</em>",
                        "Increases time and cost for client <em class='weak-ref'>[I.1]</em>",
                        "Misses opportunity to leverage beneficial technology <em class='weak-ref'>[III.8.a]</em>",
                        "Could impact project timeline <em class='weak-ref'>[I.1]</em>"
                    ],
                    "supporting_codes": ["II.1.c - Maintain client confidentiality", "III.9 - Give proper credit"],
                    "precedent_cases": []
                },
                {
                    "id": "opt3",
                    "title": "Treat AI as Standard Professional Tool",
                    "description": "Use AI freely as just another writing tool like spell-check or grammar assistance.",
                    "arguments_for": [
                        "Embraces technological advancement in profession <em class='weak-ref'>[III.8.a]</em>",
                        "Improves efficiency and productivity <em class='weak-ref'>[I.1]</em>",
                        "Similar to accepted CAD and analysis software <em class='weak-ref'>[II.2.a]</em>",
                        "Enhances report quality and consistency <em class='weak-ref'>[I.1]</em>"
                    ],
                    "arguments_against": [
                        "May oversimplify ethical considerations <strong>[I.5, III.3]</strong>",
                        "Ignores unique aspects of AI technology <strong>[I.2, II.2.a]</strong>",
                        "Could lead to over-reliance on AI <strong>[II.2.b]</strong>",
                        "Minimizes confidentiality concerns <strong>[II.1.c]</strong>"
                    ],
                    "supporting_codes": [],
                    "precedent_cases": ["BER Case 98-3 - Software tools part of practice"]
                }
            ],
            "analysis_summary": "This decision involves balancing technological efficiency with professional responsibilities including confidentiality, attribution, and maintaining competence. The key tension is between leveraging AI capabilities and ensuring full professional oversight."
        },
        {
            "type": "event",
            "title": "Report Creation Process",
            "time": "Day 15",
            "description": "Engineer A proceeds with chosen approach for report creation, incorporating client data and technical analysis.",
            "details": "The report addresses complex contamination patterns and remediation strategies."
        },
        {
            "type": "decision",
            "title": "Decision Point 2: AI-Assisted Design Documents",
            "time": "Day 18",
            "question": "Should Engineer A use AI drafting tools for engineering design documents with high-level review?",
            "context": "Engineer A considers using AI-assisted drafting for groundwater infrastructure modifications, planning only high-level review before sealing.",
            "options": [
                {
                    "id": "opt1",
                    "title": "Use AI Drafting with High-Level Review",
                    "description": "Employ AI drafting tools for design documents, conducting high-level review before applying PE seal.",
                    "arguments_for": [
                        "Increases design productivity and consistency <em class='weak-ref'>[I.1]</em>",
                        "AI can help catch standard design issues <em class='weak-ref'>[I.1]</em>",
                        "Allows focus on critical design decisions <strong>[I.2]</strong>",
                        "Similar to using advanced CAD systems <em class='weak-ref'>[II.2.a]</em>"
                    ],
                    "arguments_against": [
                        "May not maintain 'responsible charge' over work <strong>[II.2.b]</strong>",
                        "High-level review insufficient for sealed documents <strong>[II.2.b]</strong>",
                        "Risks missing critical design details <strong>[I.2, II.2.a]</strong>",
                        "Could violate requirements for personal direction <strong>[II.2.b]</strong>"
                    ],
                    "supporting_codes": ["II.2.b - Documents under personal direction/control"],
                    "precedent_cases": ["NSPE Position Statement 10-1778 - Responsible Charge"]
                },
                {
                    "id": "opt2",
                    "title": "Maintain Full Personal Control",
                    "description": "Create all design documents personally or under direct supervision to maintain responsible charge.",
                    "arguments_for": [
                        "Ensures complete understanding of design details <strong>[I.2, II.2.a]</strong>",
                        "Maintains required 'responsible charge' <strong>[II.2.b]</strong>",
                        "Fulfills PE seal requirements fully <strong>[II.2.b, III.8.a]</strong>",
                        "Provides direct control over critical decisions <strong>[II.2.b]</strong>"
                    ],
                    "arguments_against": [
                        "May slow design process significantly <em class='weak-ref'>[I.1]</em>",
                        "Could miss benefits of AI error checking <em class='weak-ref'>[I.1]</em>",
                        "Increases project costs <em class='weak-ref'>[I.1]</em>",
                        "May seem outdated to tech-forward clients <em class='weak-ref'>[III.8.a]</em>"
                    ],
                    "supporting_codes": ["II.2.b - Personal direction required for sealed work"],
                    "precedent_cases": []
                },
                {
                    "id": "opt3",
                    "title": "Use AI with Comprehensive Detail Review",
                    "description": "Use AI drafting but implement thorough, detailed review process before sealing.",
                    "arguments_for": [
                        "Balances efficiency with responsibility <strong>[I.2, II.2.b]</strong>",
                        "Maintains professional oversight <strong>[II.2.a, II.2.b]</strong>",
                        "Leverages AI while ensuring quality <strong>[I.2]</strong>",
                        "Could establish new best practices <em class='weak-ref'>[III.8.a]</em>"
                    ],
                    "arguments_against": [
                        "Requires significant time for detailed review <em class='weak-ref'>[I.1]</em>",
                        "May negate efficiency benefits <em class='weak-ref'>[I.1]</em>",
                        "Still questions about 'personal creation' <strong>[II.2.b]</strong>",
                        "Review process must be extremely thorough <strong>[I.2, II.2.a]</strong>"
                    ],
                    "supporting_codes": ["I.2 - Competence in review process"],
                    "precedent_cases": ["BER Case 90-6 - Proper oversight critical"]
                }
            ],
            "analysis_summary": "This decision centers on maintaining 'responsible charge' over sealed engineering documents. The tension is between efficiency gains from AI drafting and the professional requirement for personal direction and control over work bearing the PE seal."
        },
        {
            "type": "event",
            "title": "Design Document Creation",
            "time": "Day 22",
            "description": "Engineer A completes the engineering design documents for groundwater infrastructure modifications.",
            "details": "Documents include detailed specifications and drawings requiring PE seal."
        },
        {
            "type": "decision",
            "title": "Decision Point 3: Disclosure of AI Usage",
            "time": "Day 25",
            "question": "Should Engineer A disclose the use of AI tools to Client W?",
            "context": "With project nearing completion, Engineer A considers whether to inform the client about any AI tool usage in creating deliverables.",
            "options": [
                {
                    "id": "opt1",
                    "title": "Voluntary Transparency About AI Role",
                    "description": "Proactively disclose AI usage even without contractual requirement, emphasizing professional oversight.",
                    "arguments_for": [
                        "Builds trust through transparency <strong>[I.5, III.3]</strong>",
                        "Allows client to make informed decisions <strong>[I.5]</strong>",
                        "Demonstrates ethical leadership <strong>[I.5, III.3]</strong>",
                        "May strengthen client relationship <em class='weak-ref'>[I.1]</em>"
                    ],
                    "arguments_against": [
                        "Not contractually required <em class='weak-ref'>[III.8.a]</em>",
                        "May cause unnecessary client concern <em class='weak-ref'>[I.1]</em>",
                        "Could be seen as admitting inadequacy <em class='weak-ref'>[I.5]</em>",
                        "Might complicate project acceptance <em class='weak-ref'>[I.1]</em>"
                    ],
                    "supporting_codes": ["I.5 - Avoid deceptive acts", "III.3 - Avoid deceiving public"],
                    "precedent_cases": []
                },
                {
                    "id": "opt2",
                    "title": "No Disclosure - Standard Tools",
                    "description": "Treat AI as standard professional software not requiring special disclosure.",
                    "arguments_for": [
                        "Consistent with software tool precedents <em class='weak-ref'>[III.8.a]</em>",
                        "Avoids creating unnecessary concerns <em class='weak-ref'>[I.1]</em>",
                        "Maintains focus on deliverable quality <strong>[I.2]</strong>",
                        "Follows established practices <em class='weak-ref'>[III.8.a]</em>"
                    ],
                    "arguments_against": [
                        "May miss opportunity for transparency <strong>[I.5, III.3]</strong>",
                        "Client might prefer to know methodology <strong>[I.5]</strong>",
                        "Could be discovered later <strong>[I.5, III.3]</strong>",
                        "Evolving technology may need new standards <em class='weak-ref'>[III.8.a]</em>"
                    ],
                    "supporting_codes": [],
                    "precedent_cases": ["BER Case 98-3 - No disclosure for CD-ROM tools"]
                },
                {
                    "id": "opt3",
                    "title": "Disclosure Only If Substantial AI Role",
                    "description": "Disclose only if AI played a substantial role beyond basic assistance.",
                    "arguments_for": [
                        "Balances transparency with practicality <strong>[I.5, I.2]</strong>",
                        "Recognizes degrees of AI involvement <strong>[I.2, II.2.a]</strong>",
                        "Allows professional judgment <strong>[I.2]</strong>",
                        "Flexible approach for evolving technology <em class='weak-ref'>[III.8.a]</em>"
                    ],
                    "arguments_against": [
                        "Requires defining 'substantial role' <strong>[I.5, III.3]</strong>",
                        "Subjective determination needed <strong>[I.5]</strong>",
                        "May lead to inconsistent practices <strong>[III.3]</strong>",
                        "Could create gray areas <strong>[I.5, III.3]</strong>"
                    ],
                    "supporting_codes": ["I.5 - Truthfulness in professional reports"],
                    "precedent_cases": []
                }
            ],
            "analysis_summary": "This decision addresses transparency and disclosure obligations regarding AI tool usage. The key consideration is balancing the absence of explicit disclosure requirements with principles of honesty and the evolving nature of AI technology in professional practice."
        },
        {
            "type": "event",
            "title": "Project Delivery",
            "time": "Day 30",
            "description": "Engineer A delivers the comprehensive report and engineering design documents to Client W.",
            "details": "All deliverables meet technical requirements and are submitted on schedule."
        }
    ]
}

def format_static_analysis_text(analysis: Dict[str, Any]) -> str:
    """Format the analysis as a text document for display."""
    output = []
    
    # Header
    output.append("=" * 80)
    output.append(f"STATIC ETHICAL ANALYSIS: {analysis['scenario']['name']}")
    output.append(f"Case Reference: {analysis['scenario']['case_reference']}")
    output.append(f"Generated: {analysis['metadata']['generated_at']}")
    output.append("=" * 80)
    output.append("")
    
    # Overview
    output.append("OVERVIEW")
    output.append("-" * 40)
    output.append(analysis['scenario']['description'])
    output.append("Engineer A is the primary agent facing these ethical decisions.")
    output.append("")
    
    # Timeline
    output.append("TIMELINE ANALYSIS")
    output.append("-" * 40)
    output.append("")
    
    for item in analysis['timeline']:
        if item['type'] == 'event':
            output.append(f"📅 EVENT: {item['title']}")
            output.append(f"Time: {item['time']}")
            output.append(f"Description: {item['description']}")
            if item.get('details'):
                output.append(f"Details: {item['details']}")
            output.append("")
            
        elif item['type'] == 'decision':
            output.append(f"⚖️  DECISION POINT: {item['title']}")
            output.append(f"Time: {item['time']}")
            output.append(f"Ethical Question: {item['question']}")
            output.append(f"Context: {item['context']}")
            output.append("")
            output.append("ETHICAL ANALYSIS OF OPTIONS:")
            output.append("")
            
            for i, option in enumerate(item['options'], 1):
                output.append(f"Option {i}: {option['title']}")
                output.append(f"Description: {option['description']}")
                output.append("")
                
                output.append("Arguments For:")
                for arg in option['arguments_for']:
                    output.append(f"  • {arg}")
                if option.get('supporting_codes'):
                    output.append(f"  Supporting Codes: {', '.join(option['supporting_codes'])}")
                output.append("")
                
                output.append("Arguments Against:")
                for arg in option['arguments_against']:
                    output.append(f"  • {arg}")
                if option.get('precedent_cases'):
                    output.append(f"  Relevant Cases: {', '.join(option['precedent_cases'])}")
                output.append("")
                output.append("-" * 40)
                output.append("")
            
            output.append(f"ANALYSIS SUMMARY: {item['analysis_summary']}")
            output.append("")
            output.append("=" * 80)
            output.append("")
    
    # Conclusion
    output.append("ANALYSIS CONCLUSION")
    output.append("-" * 40)
    output.append("This static analysis has presented the ethical considerations for each")
    output.append("decision point without revealing predetermined outcomes. The goal is to")
    output.append("encourage independent ethical reasoning based on professional codes,")
    output.append("precedents, and stakeholder impacts.")
    output.append("")
    output.append("Key themes across all decisions:")
    output.append("• Balancing technological innovation with professional responsibilities")
    output.append("• Maintaining competence and responsible charge over AI-assisted work")
    output.append("• Navigating confidentiality concerns with cloud-based AI tools")
    output.append("• Determining appropriate transparency about AI usage")
    output.append("")
    output.append("=" * 80)
    output.append("")
    output.append("REFERENCES")
    output.append("-" * 40)
    output.append("")
    output.append("NSPE Code of Ethics")
    output.append("Available at: https://www.nspe.org/career-growth/ethics/code-ethics")
    output.append("")
    output.append("Code Sections Referenced:")
    output.append("• I.2 - Engineers shall perform services only in the areas of their competence")
    output.append("• I.5 - Engineers shall avoid deceptive acts")
    output.append("• II.1.c - Engineers shall not disclose confidential information")
    output.append("• II.2.b - Engineers shall not affix signatures to documents not under their control")
    output.append("• III.3 - Engineers shall avoid conduct that deceives the public")
    output.append("• III.9 - Engineers shall give credit for engineering work")
    output.append("")
    output.append("NSPE Board of Ethical Review Cases")
    output.append("Available at: https://www.nspe.org/career-growth/ethics/board-ethical-review-cases")
    output.append("")
    output.append("Cases Referenced:")
    output.append("• BER Case 24-02 - Use of AI in Engineering Practice (case being analyzed)")
    output.append("• BER Case 90-6 - Use of CADD (computer tools acceptable with oversight)")
    output.append("• BER Case 98-3 - Use of CD-ROM Design Tools (no disclosure required)")
    output.append("")
    output.append("NSPE Position Statements:")
    output.append("• Position Statement 10-1778 - Responsible Charge")
    output.append("")
    
    return "\n".join(output)

def save_analysis_as_html(analysis: Dict[str, Any], filename: str = "case7_static_analysis.html"):
    """Save the analysis as an HTML file."""
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Static Analysis - {title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
            color: white;
            padding: 30px;
            margin: -40px -40px 30px -40px;
            border-radius: 10px 10px 0 0;
            text-align: center;
        }}
        h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .metadata {{
            font-size: 14px;
            opacity: 0.9;
        }}
        .timeline-item {{
            margin-bottom: 40px;
            padding-left: 20px;
            border-left: 3px solid #dee2e6;
        }}
        .event {{
            border-left-color: #17a2b8;
        }}
        .decision {{
            border-left-color: #ffc107;
        }}
        .option {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .arguments-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 15px;
        }}
        .arguments-for, .arguments-against {{
            padding: 15px;
            border-radius: 5px;
        }}
        .arguments-for {{
            background: rgba(40, 167, 69, 0.1);
            border: 1px solid rgba(40, 167, 69, 0.3);
        }}
        .arguments-against {{
            background: rgba(220, 53, 69, 0.1);
            border: 1px solid rgba(220, 53, 69, 0.3);
        }}
        .arguments-for h4 {{
            color: #28a745;
            margin-top: 0;
        }}
        .arguments-against h4 {{
            color: #dc3545;
            margin-top: 0;
        }}
        .alert {{
            background: #d1ecf1;
            border: 1px solid #bee5eb;
            color: #0c5460;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .conclusion {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 30px;
            border-radius: 8px;
            margin-top: 40px;
        }}
        ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        .references {{
            font-size: 12px;
            color: #6c757d;
            margin-top: 10px;
        }}
        .references-section {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 30px;
            border-radius: 8px;
            margin-top: 40px;
        }}
        .references-section h3 {{
            color: #495057;
            margin-top: 25px;
        }}
        .references-section h3:first-of-type {{
            margin-top: 15px;
        }}
        .references-section a {{
            color: #007bff;
            text-decoration: none;
        }}
        .references-section a:hover {{
            text-decoration: underline;
        }}
        .weak-ref {{
            color: #6c757d;
            font-style: italic;
        }}
        .code-ref {{
            position: relative;
            cursor: help;
            border-bottom: 1px dotted #007bff;
            display: inline-block;
        }}
        .code-ref::after {{
            content: "🔍";
            font-size: 0.8em;
            margin-left: 2px;
            opacity: 0.7;
        }}
        .tooltip {{
            position: absolute;
            background: #2c3e50;
            color: white;
            padding: 12px;
            border-radius: 6px;
            font-size: 0.9em;
            line-height: 1.4;
            min-width: 300px;
            max-width: 400px;
            z-index: 1000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            opacity: 0;
            transition: opacity 0.3s ease;
            pointer-events: none;
            white-space: normal;
        }}
        .tooltip.show {{
            opacity: 1;
        }}
        .tooltip::before {{
            content: "";
            position: absolute;
            top: -8px;
            left: 20px;
            border: 8px solid transparent;
            border-bottom-color: #2c3e50;
        }}
        .tooltip-header {{
            font-weight: bold;
            color: #3498db;
            margin-bottom: 6px;
        }}
        .tooltip-footer {{
            margin-top: 8px;
            font-size: 0.8em;
            color: #bdc3c7;
            border-top: 1px solid #34495e;
            padding-top: 6px;
        }}
        @media print {{
            body {{
                background: white;
            }}
            .container {{
                box-shadow: none;
                padding: 20px;
            }}
            .header {{
                background: #6c757d !important;
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <p class="metadata">Case Reference: {case_ref}<br>Generated: {timestamp}</p>
        </div>
        
        <h2>Overview</h2>
        <p>{description}</p>
        <p><strong>Engineer A is the primary agent facing these ethical decisions.</strong></p>
        
        <h2>Timeline Analysis</h2>
        {timeline_content}
        
        <div class="conclusion">
            <h2>Analysis Conclusion</h2>
            <p>This static analysis has presented the ethical considerations for each decision point without revealing predetermined outcomes. The goal is to encourage independent ethical reasoning based on professional codes, precedents, and stakeholder impacts.</p>
            
            <h3>Key Themes Across All Decisions:</h3>
            <ul>
                <li>Balancing technological innovation with professional responsibilities</li>
                <li>Maintaining competence and responsible charge over AI-assisted work</li>
                <li>Navigating confidentiality concerns with cloud-based AI tools</li>
                <li>Determining appropriate transparency about AI usage</li>
            </ul>
        </div>
        
        <div class="references-section">
            <h2>References</h2>
            
            <h3>NSPE Code of Ethics</h3>
            <p>The ethical analysis references the following sections of the 
            <a href="https://www.nspe.org/career-growth/ethics/code-ethics" target="_blank">NSPE Code of Ethics for Engineers</a>:</p>
            <ul>
                <li><strong>I.2</strong> - Engineers shall perform services only in the areas of their competence</li>
                <li><strong>I.5</strong> - Engineers shall avoid deceptive acts</li>
                <li><strong>II.1.c</strong> - Engineers shall not disclose, without consent, confidential information</li>
                <li><strong>II.2.b</strong> - Engineers shall not affix their signatures to plans or documents not prepared under their direction and control</li>
                <li><strong>III.3</strong> - Engineers shall avoid all conduct or practice that deceives the public</li>
                <li><strong>III.9</strong> - Engineers shall give credit for engineering work to those to whom credit is due</li>
            </ul>
            
            <h3>NSPE Board of Ethical Review Cases</h3>
            <p>The following precedent cases inform this analysis:</p>
            <ul>
                <li><strong>BER Case 24-02</strong> - Use of Artificial Intelligence in Engineering Practice 
                    <em>(This is the case being analyzed)</em></li>
                <li><strong>BER Case 90-6</strong> - Use of Computer-Aided Design and Drafting (CADD) 
                    <em>(Established that engineers can use computer tools with proper oversight)</em></li>
                <li><strong>BER Case 98-3</strong> - Use of CD-ROM Design Tools 
                    <em>(Software tools are part of practice and don't require client disclosure)</em></li>
            </ul>
            <p>View all NSPE BER cases at: 
            <a href="https://www.nspe.org/career-growth/ethics/board-ethical-review-cases" target="_blank">
                NSPE Board of Ethical Review Cases
            </a></p>
            
            <h3>NSPE Position Statements</h3>
            <ul>
                <li><strong>Position Statement 10-1778</strong> - Responsible Charge 
                    <em>(Defines requirements for maintaining responsible charge over engineering work)</em></li>
            </ul>
        </div>
    </div>

    <script>
        // NSPE Code of Ethics text data
        const nspeCodeText = {{
            'I.1': {{
                title: 'Fundamental Canon I.1',
                text: 'Hold paramount the safety, health, and welfare of the public.',
                section: 'I. Fundamental Canons'
            }},
            'I.2': {{
                title: 'Fundamental Canon I.2',
                text: 'Perform services only in areas of their competence.',
                section: 'I. Fundamental Canons'
            }},
            'I.5': {{
                title: 'Fundamental Canon I.5',
                text: 'Avoid deceptive acts.',
                section: 'I. Fundamental Canons'
            }},
            'II.1.c': {{
                title: 'Rules of Practice II.1.c',
                text: 'Do not disclose client/employer information without consent or legal obligation.',
                section: 'II. Rules of Practice - Hold paramount the safety, health, and welfare of the public'
            }},
            'II.2.a': {{
                title: 'Rules of Practice II.2.a',
                text: 'Accept only qualified assignments.',
                section: 'II. Rules of Practice - Perform services only in areas of their competence'
            }},
            'II.2.b': {{
                title: 'Rules of Practice II.2.b',
                text: 'Do not sign off on work outside area of expertise.',
                section: 'II. Rules of Practice - Perform services only in areas of their competence'
            }},
            'III.3': {{
                title: 'Professional Obligations III.3',
                text: 'Engineers shall avoid conduct that deceives the public. Avoid material misrepresentations or omissions. Advertise truthfully. Acknowledge contributions of others.',
                section: 'III. Professional Obligations'
            }},
            'III.8.a': {{
                title: 'Professional Obligations III.8.a',
                text: 'Follow registration laws.',
                section: 'III. Professional Obligations - Accept responsibility for their actions'
            }},
            'III.9': {{
                title: 'Professional Obligations III.9',
                text: 'Engineers shall credit others appropriately. Name individuals responsible for work when possible. Respect proprietary rights of clients.',
                section: 'III. Professional Obligations'
            }}
        }};

        // Tooltip functionality
        let currentTooltip = null;

        function createTooltip(element, codes) {{
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            
            let content = '';
            codes.forEach((code, index) => {{
                const codeData = nspeCodeText[code];
                if (codeData) {{
                    if (index > 0) content += '<br><br>';
                    content += `<div class="tooltip-header">${{codeData.title}}</div>`;
                    content += `<div>${{codeData.text}}</div>`;
                }}
            }});
            
            content += `<div class="tooltip-footer">🔍 Click code reference to research further</div>`;
            tooltip.innerHTML = content;
            
            document.body.appendChild(tooltip);
            return tooltip;
        }}

        function positionTooltip(tooltip, element) {{
            const rect = element.getBoundingClientRect();
            const tooltipRect = tooltip.getBoundingClientRect();
            
            let top = rect.bottom + window.scrollY + 10;
            let left = rect.left + window.scrollX;
            
            // Adjust if tooltip would go off screen
            if (left + tooltipRect.width > window.innerWidth) {{
                left = window.innerWidth - tooltipRect.width - 20;
            }}
            
            if (top + tooltipRect.height > window.innerHeight + window.scrollY) {{
                top = rect.top + window.scrollY - tooltipRect.height - 10;
                // Flip arrow to bottom
                tooltip.style.setProperty('--arrow-position', 'bottom');
            }}
            
            tooltip.style.top = top + 'px';
            tooltip.style.left = left + 'px';
        }}

        function showTooltip(element, codes) {{
            hideTooltip();
            currentTooltip = createTooltip(element, codes);
            positionTooltip(currentTooltip, element);
            
            // Use setTimeout to ensure the element is rendered before showing
            setTimeout(() => {{
                currentTooltip.classList.add('show');
            }}, 10);
        }}

        function hideTooltip() {{
            if (currentTooltip) {{
                currentTooltip.remove();
                currentTooltip = null;
            }}
        }}

        // Initialize tooltips when page loads
        document.addEventListener('DOMContentLoaded', function() {{
            // Convert all code references to interactive elements
            document.querySelectorAll('strong, em.weak-ref').forEach(element => {{
                const text = element.textContent;
                const codeMatch = text.match(/\\[([I]+\\.[\\d\\.a-z]+(?:,\\s*[I]+\\.[\\d\\.a-z]+)*)\\]/);
                
                if (codeMatch) {{
                    const codes = codeMatch[1].split(',').map(code => code.trim());
                    const beforeText = text.substring(0, codeMatch.index);
                    const codeText = codeMatch[0];
                    const afterText = text.substring(codeMatch.index + codeMatch[0].length);
                    
                    // Create new HTML with interactive code reference
                    const newHTML = beforeText + 
                        `<span class="code-ref" data-codes="${{codes.join(',')}}">${{codeText}}</span>` + 
                        afterText;
                    
                    element.innerHTML = newHTML;
                }}
            }});
            
            // Add event listeners to code references
            document.querySelectorAll('.code-ref').forEach(element => {{
                const codes = element.dataset.codes.split(',');
                
                element.addEventListener('mouseenter', () => {{
                    showTooltip(element, codes);
                }});
                
                element.addEventListener('mouseleave', () => {{
                    setTimeout(hideTooltip, 300); // Small delay to allow moving to tooltip
                }});
                
                element.addEventListener('click', () => {{
                    // Future: Navigate to detailed code research page
                    window.open('https://www.nspe.org/career-growth/ethics/code-ethics', '_blank');
                }});
            }});
            
            // Hide tooltip when scrolling
            window.addEventListener('scroll', hideTooltip);
        }});
    </script>
</body>
</html>"""
    
    # Generate timeline content
    timeline_content = []
    for item in analysis['timeline']:
        if item['type'] == 'event':
            timeline_content.append(f'''
            <div class="timeline-item event">
                <h3>📅 {item['title']}</h3>
                <p><strong>Time:</strong> {item['time']}</p>
                <p>{item['description']}</p>
                {f"<p><em>{item.get('details', '')}</em></p>" if item.get('details') else ""}
            </div>''')
        
        elif item['type'] == 'decision':
            options_html = []
            for i, option in enumerate(item['options'], 1):
                args_for_html = ''.join([f'<li>{arg}</li>' for arg in option['arguments_for']])
                args_against_html = ''.join([f'<li>{arg}</li>' for arg in option['arguments_against']])
                
                refs = []
                if option.get('supporting_codes'):
                    refs.append(f"Supporting Codes: {', '.join(option['supporting_codes'])}")
                if option.get('precedent_cases'):
                    refs.append(f"Relevant Cases: {', '.join(option['precedent_cases'])}")
                
                options_html.append(f'''
                <div class="option">
                    <h4>Option {i}: {option['title']}</h4>
                    <p>{option['description']}</p>
                    <div class="arguments-grid">
                        <div class="arguments-for">
                            <h4>Arguments For:</h4>
                            <ul>{args_for_html}</ul>
                        </div>
                        <div class="arguments-against">
                            <h4>Arguments Against:</h4>
                            <ul>{args_against_html}</ul>
                        </div>
                    </div>
                    {f'<div class="references">{" | ".join(refs)}</div>' if refs else ''}
                </div>''')
            
            timeline_content.append(f'''
            <div class="timeline-item decision">
                <h3>⚖️ {item['title']}</h3>
                <p><strong>Time:</strong> {item['time']}</p>
                <div class="alert">
                    <strong>Ethical Question:</strong> {item['question']}
                </div>
                <p><strong>Context:</strong> {item['context']}</p>
                <h4>Ethical Analysis of Options:</h4>
                {''.join(options_html)}
                <div class="alert">
                    <strong>Analysis Summary:</strong> {item['analysis_summary']}
                </div>
            </div>''')
    
    # Fill in the template
    html = html_template.format(
        title=analysis['scenario']['name'],
        case_ref=analysis['scenario']['case_reference'],
        timestamp=analysis['metadata']['generated_at'],
        description=analysis['scenario']['description'],
        timeline_content=''.join(timeline_content)
    )
    
    # Save to file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"HTML analysis saved to: {filename}")

def main():
    """Generate and display the static analysis."""
    print("Generating static analysis for Case 7...")
    print()
    
    # Display text version
    text_output = format_static_analysis_text(CASE_7_STATIC_ANALYSIS)
    print(text_output)
    
    # Save as JSON
    with open('case7_static_analysis.json', 'w') as f:
        json.dump(CASE_7_STATIC_ANALYSIS, f, indent=2)
    print("\nJSON analysis saved to: case7_static_analysis.json")
    
    # Save as HTML
    save_analysis_as_html(CASE_7_STATIC_ANALYSIS)
    
    print("\nTo view in browser: python -m http.server 8000")
    print("Then navigate to: http://localhost:8000/case7_static_analysis.html")

if __name__ == "__main__":
    main()