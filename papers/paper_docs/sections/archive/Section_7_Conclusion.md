# 7. Conclusion

## 7.1 Summary of Contributions

This paper presents ProEthica, a system that integrates large language models with role-based ontologies to support ethical reasoning in professional contexts. The approach addresses a critical gap in current AI systems by providing structured mechanisms for incorporating domain-specific ethical obligations into automated reasoning processes.

Our primary contribution is the development of bidirectional LLM-ontology integration that constrains model outputs while preserving the generative capabilities needed for complex ethical analysis. The system combines analogical reasoning from precedent cases with formal ontological representations of professional ethical frameworks. This design enables systematic evaluation of ethical scenarios while maintaining transparency in the reasoning process.

The evaluation on 20 NSPE engineering ethics cases demonstrates the practical application of ontology-constrained reasoning. The leave-one-out methodology and participant review provide evidence that structured ethical frameworks can improve the quality and consistency of AI-generated ethical analysis compared to unconstrained text generation approaches.

Three specific technical contributions support these outcomes. First, the multi-metric relevance scoring system enables effective retrieval of analogous cases by combining vector similarity with structural and term-based matching. Second, the FIRAC document structure annotation provides systematic organization of ethical reasoning components. Third, the MCP-based architecture enables reliable ontology access without requiring direct LLM navigation of complex knowledge structures.

## 7.2 Practical and Theoretical Implications

The results suggest that professional ethics applications benefit from explicit constraint mechanisms rather than relying solely on general-purpose language model training. This finding has implications for the deployment of AI systems in domains where ethical considerations are paramount, such as healthcare, engineering, and legal practice.

The approach demonstrates that AI systems can support ethical decision-making without claiming autonomous moral agency. By positioning the LLM as a reasoning tool constrained by formal ethical frameworks, the system preserves human responsibility while providing structured analytical support. This design addresses concerns about delegating ethical judgment to AI systems while leveraging their capabilities for complex text analysis and generation.

The role-based ontological modeling provides a pathway for incorporating diverse professional ethical frameworks into AI systems. The world-based organization enables domain-specific customization while maintaining consistent architectural principles across different professional contexts.

## 7.3 Limitations

Several limitations constrain the generalizability of these findings. The evaluation focuses exclusively on engineering ethics cases from a single professional organization (NSPE). Different professional domains may require alternative ontological structures or reasoning approaches. The English-language case base limits applicability to other linguistic and cultural contexts.

The system requires substantial preprocessing to create domain-specific ontologies and annotate case structures. This requirement may limit practical deployment in domains without established case repositories or codified ethical frameworks. The dependence on expert knowledge for ontology creation introduces potential bias in the constraint mechanisms.

The evaluation methodology, while systematic, relies on a relatively small case base and participant panel. Larger-scale evaluation across multiple domains would strengthen confidence in the approach. The focus on written case analysis may not capture all aspects of real-world ethical decision-making, which often involves time pressure, incomplete information, and interpersonal dynamics.

## 7.4 Future Work

Several research directions emerge from this work. **Richer temporal-reasoning module to capture evolving obligations** addresses the present first-order limitation by developing sophisticated mechanisms for tracking how professional standards change over time through case precedents and evolving social contexts. This would enable more dynamic understanding of how ethical principles adapt while maintaining consistency with established frameworks.

**Multilingual guideline expansion to support cross-cultural adaptation** addresses the language-specific corpus constraint by developing ontological representations that account for cultural variation in ethical frameworks while maintaining computational tractability. To adjust to specific cultures and countries, multilingual capabilities would be needed to ensure broad applicability across diverse professional contexts.

Cross-domain evaluation would test the generalizability of the ontology-constrained approach across different professional contexts. Medical ethics, legal practice, and business ethics each present distinct challenges for automated reasoning support.

Integration with real-time decision support systems represents a practical research direction. Current batch processing approaches would need adaptation for interactive applications where users require immediate ethical guidance. This extension would require addressing latency constraints and user interface design for complex ethical reasoning.

The integration of emotional and interpersonal factors represents another research frontier. Current approaches focus on logical analysis of written scenarios. Real ethical decisions often involve emotional considerations and interpersonal relationships that may require different computational approaches.

## 7.5 Conclusion

ProEthica demonstrates that ontology-constrained reasoning can improve the quality and consistency of AI-generated ethical analysis. The approach provides a practical framework for incorporating professional ethical obligations into AI systems while maintaining human agency in ethical decision-making.

The combination of formal ontological structures with large language model capabilities offers a promising direction for AI ethics applications. Rather than replacing human ethical judgment, such systems can provide structured analytical support that enhances human decision-making in complex professional contexts.

The success of this approach in engineering ethics suggests potential for broader application across professional domains. Future work should focus on expanding domain coverage, improving ontological representation methods, and developing more sophisticated evaluation frameworks for AI-supported ethical reasoning.