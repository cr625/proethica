# Section 1: Introduction

## 1.1 Problem Context

Large language models (LLMs) are now being applied in ethically sensitive domains such as healthcare and engineering, wherein failure may result in substantial material or ethical harm \cite{abbott_reasonable_2020, haltaufderheide_ethics_2024, kampelopoulos_review_2025, waser_implementation_2014}. In medicine and mental health, LLMs are proposed for tasks such as clinical decision support, diagnostic reasoning, and therapeutic dialogue \cite{lawrence_opportunities_2024}. In engineering and construction, they have been used for hazard recognition, energy modeling, and robotic sequencing \cite{kampelopoulos_review_2025}. Applications in these contexts raise concerns about the reliability, accountability, and regulatory adequacy of LLM use in professional environments within established normative constraints \cite{taddeo_ai_2024}. Despite promising performance, documented errors and misuse cases, such as false medical facts and unsafe engineering suggestions, highlight unresolved risks to safety, equity, and trust \cite{haltaufderheide_ethics_2024}.

These models are also increasingly embedded in workflows that interact with legal and institutional frameworks, raising the need for explicit alignment with established codes of conduct \cite{dubber_oxford_2020, zhang_mm-llms_2024, osman_computational_2024}. The introduction of AI-based systems into these domains without corresponding mechanisms for normative validation and explanation has prompted concerns about accountability, transparency, and value alignment \cite{prem_ethical_2023, vishwanath_towards_2023}. A critical failure mode involves treating LLMs as autonomous ethical decision-makers rather than tools that support human judgment within established professional frameworks.

Recent advances have made significant progress in addressing some of these concerns. Current LLMs incorporate tool use, response shaping, and reinforcement learning strategies beyond basic transformer architectures \cite{schick_toolformer_2023, yao_react_2023, hadji-kyriacou_would_2024, li_representation_2024}. These enhancements enable high performance across many domains and represent meaningful steps toward more controlled and transparent AI reasoning. However, despite these advances, current systems still do not provide sufficient transparency or structured control mechanisms for high-stakes ethical applications where professional obligations, legal precedents, and domain-specific constraints must guide reasoning processes.

## 1.2 Gap Analysis

While recent architectural improvements have enhanced LLM capabilities, significant gaps remain in meeting the specific reasoning requirements of professional ethical practice. These limitations fall into three main areas.

First, most systems do not support formal constraint mechanisms. LLMs cannot enforce domain-specific standards without structured knowledge integration. General purpose prompts may reference codes or rules, but there is no mechanism to verify consistency with those standards \cite{puri_moral_2020, dennis_formal_2016}. The absence of formal representation, whether in legal, medical or engineering contexts, undermines trust and limits usability in regulated environments \cite{dubber_oxford_2020, bruckert_next_2020}.

Second, LLMs lack analogical reasoning grounded in precedent. Although some systems retrieve example cases, few compare cases structurally or apply lessons from precedent in a verifiable way \cite{chiarello_future_2024}. Even advanced retrieval systems do not trace or align reasoning paths across cases \cite{fraser_does_2022}. This deficiency is significant in professional domains that rely on analogy, such as law and engineering, where ethical analysis routinely involves comparison to prior decisions and articulated justifications.

Third, most systems do not support bidirectional validation. Although some apply rules to input or postprocess output for compliance, few systems do both. This asymmetry prevents feedback loops and weakens the alignment between system output and professional expectations \cite{chhabra_evaluating_2024}. Without structured interaction between input constraint and output admissibility, the reasoning process remains opaque and unaccountable.

These remaining gaps reflect a deeper symbolic-structural disconnect. Professional duties are compositional, contextual, and often involve weighing conflicting obligations. LLMs, in contrast, rely on pattern completion, shortcut learning, and statistically grounded approximations. Bridging this disconnect requires systems that integrate symbolic knowledge structures, support analogical precedent matching, and enable constraint-based validation during both generation and interpretation.

## 1.3 Proposed Solution Overview

This paper presents ProEthica, a system that combines LLMs with role-based ontologies for structured ethical reasoning in professional contexts. The approach integrates two key components that address the identified gaps: analogical reasoning from precedent cases and evaluative AI frameworks for evidence-based decision support.

Professional ethics relies fundamentally on case-based reasoning where practitioners evaluate current situations by reference to established precedents following the principle of "treat like cases alike" (as detailed in Section 2.1). ProEthica implements analogical reasoning through multi-metric relevance scoring that combines vector similarity, ontological relationships, and case structure analysis to identify relevant precedents and extract applicable principles. This addresses the second gap by providing verifiable case comparison and precedent application mechanisms.

ProEthica implements an evaluative AI approach that emphasizes evidence-based decision support rather than autonomous recommendations \cite{miller2023evaluative}. The system provides structured evidence from professional codes, precedent cases, and ontological relationships to support human ethical decision-making while preserving professional agency and responsibility.

The system architecture employs role-grounded ethical obligations encoded as RDF triples that model scenarios in terms of agents, actions, and outcomes. A Model Context Protocol (MCP) interface \cite{anthropic_mcp_2024} enables bidirectional integration where ontological constraints guide LLM reasoning while validation mechanisms ensure consistency with professional frameworks. This addresses both the first gap through formal constraint mechanisms and the third gap through input constraint and output validation. The system organizes professional knowledge through domain-specific "worlds" that encapsulate complete ethical frameworks, enabling targeted reasoning within established professional boundaries.

## 1.4 Key Contributions

This work makes four primary contributions to AI-assisted professional ethical reasoning:

\begin{enumerate}
\item A role-grounded professional ethics ontology that systematically incorporates institutional codes, precedents, and discipline-specific obligations into AI reasoning processes.

\item Multi-metric precedent retrieval that combines vector similarity, ontological relationships, and case structure analysis to identify relevant cases and extract applicable principles.

\item Bidirectional LLM-ontology integration that enables ontologies to both constrain input reasoning and validate output consistency through structured interfaces.

\item A structured validation framework based on legal reasoning principles (Facts, Issues, Rules, Analysis, Conclusion) that provides systematic evaluation of ethical reasoning quality and professional alignment.
\end{enumerate}

## 1.5 Paper Organization

This paper is organized as follows. Section 2 reviews background and related work in computational ethics, role theory, prior professional ethics systems, LLM-based moral reasoning, and validation methodologies. Section 3 presents our proposed approach, including requirements analysis, conceptual framework, a concrete example scenario, and technical implementation details. Section 4 describes our study design, including research hypothesis, corpus preparation, processing pipeline, validation approach, evaluation metrics, and participant review protocol. Section 5 presents results from our evaluation on NSPE engineering ethics cases. Section 6 discusses implications and positions our work relative to existing validation approaches. Section 7 concludes with summary of contributions, limitations, and future work directions.

---

**Section Status**: Complete with all citations integrated
- ✅ **1.1 Problem Context**: Complete with all LaTeX citations
- ✅ **1.2 Gap Analysis**: Restored to three main areas with all citations  
- ✅ **1.3 Proposed Solution Overview**: Complete
- ✅ **1.4 Key Contributions**: Complete
- ✅ **1.5 Paper Organisation**: Complete

**Citation Updates**: 
- Added all citations from LaTeX source to appropriate locations
- Removed fake Rawte et al. reference
- Maintained three-area gap analysis structure as in original
- Ready for bibliography compilation