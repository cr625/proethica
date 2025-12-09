# Academic References

This page documents the academic sources and theoretical foundations for ProEthica.

## Transformation Classification

### Source

**Marchais-Roubelat, A. and Roubelat, F. (2015)**
*Designing a moving strategic foresight approach: ontological and methodological issues of scenario design*
Foresight, Vol. 17 No. 6, pp. 545-555.
[DOI: 10.1108/FS-12-2014-0085](https://doi.org/10.1108/FS-12-2014-0085)

### Transformation Types

From Table II (p. 550) - "Steering rule" evaluates process transformations to challenge scenario duration.

| Type | Definition (from paper) | Application to NSPE Cases |
|------|-------------------------|---------------------------|
| **Transfer** | "Shifts from a scenario set to a new one" | Resolution transfers obligation/responsibility to another party |
| **Stalemate** | "Stakeholders cannot quit the scenario, as they seem to be trapped in the set of rules" | Competing obligations remain in tension without clear resolution |
| **Oscillation** | "Stakeholders go to and fro between different sets of rules" | Duties shift back and forth between parties over time |
| **Phase Lag** | "Some stakeholders do not follow the set of rules of the scenario where they are engaged, performing parallel scenarios" | Delayed consequences reveal obligations not initially apparent |

Marchais-Roubelat and Roubelat's framework comes from strategic foresight methodology, specifically their "action-based scenarios" approach. ProEthica applies these transformation types to classify how NSPE Board of Ethical Review cases resolve competing ethical obligations.

---

## Nine-Concept Framework

The formal framework D = (R, P, O, S, Rs, A, E, Ca, Cs) synthesizes concepts from computational ethics literature.

### Foundational Works

- **McLaren, B.M. (2003)** - Extensional definition of ethical principles through case-based reasoning (SIROCCO system)
- **Berreby, F. et al. (2017)** - ACE modular architecture for ethical reasoning systems
- **Tolmeijer, S. et al. (2021)** - Requirements taxonomy for ethical decision-making agents

### Roles (R)

Professional roles generate distinctive ethical obligations tied to professional goals and practices.

| Reference | Contribution |
|-----------|--------------|
| Oakley & Cocking (2001) | Role morality and professional duties |
| Dennis et al. (2016) | Roles as filters determining which obligations apply |
| Cointe et al. (2016) | Multi-agent frameworks for role-based principle interpretation |
| Kong et al. (2020) | Identity roles and virtues across engineering, law, accounting |

### Principles (P)

Abstract ethical principles require extensional definition through precedents to achieve concrete meaning.

| Reference | Contribution |
|-----------|--------------|
| McLaren (2003) | Extensional vs intensional principle definition |
| Hallamaa & Kalliokoski (2022) | Context-sensitivity of principles |
| Taddeo et al. (2024) | Principle operationalization steps |
| Anderson & Anderson (2018) | GenEth: learning principles from expert examples |
| Benzmuller et al. (2020) | LogiKEy higher-order logic formalization |

### Obligations (O)

Obligations specify what, when, by whom, and under what conditions - the "moral core" of professional ethics.

| Reference | Contribution |
|-----------|--------------|
| Dennis et al. (2016) | Principles vs obligations distinction |
| Scheutz & Malle (2014) | Obligations as permissible/obligatory/forbidden actions |
| Anderson & Anderson (2006, 2007, 2011) | Prima facie duty framework |
| Ganascia (2007) | Answer set programming for conflicting obligations |
| Dennis & del Olmo (2021) | Defeasible deontic logic |

### States (S)

Context determines which principles activate and how they apply - identical actions receive different moral evaluations.

| Reference | Contribution |
|-----------|--------------|
| Rao et al. (2023) | Context-dependence in moral evaluation |
| Berreby et al. (2017) | Event Calculus for state representation |
| Almpani et al. (2023) | Context as environmental states |
| Sarmiento et al. (2023) | Causal reasoning with state transitions |

### Resources (Rs)

Professional ethical knowledge is largely encoded in cases and codes rather than explicit rules.

| Reference | Contribution |
|-----------|--------------|
| Ashley & McLaren (1995) | Case-based reasoning foundations |
| Guarini (2006) | Neural network case classification |
| Davis (1991) | Multiple functions of professional codes |
| Frankel (1989) | Hierarchical structure in codes |
| Kong et al. (2020) | Computational linguistics for code analysis |

### Actions (A)

Professional actions require multi-criteria assessment across deontological, consequentialist, and virtue dimensions.

| Reference | Contribution |
|-----------|--------------|
| Bonnemains et al. (2018) | Multi-criteria action evaluation |
| Govindarajulu & Bringsjord (2017) | Doctrine of Double Effect formalization |
| Sarmiento et al. (2023) | Causal relationships with NESS test |
| Dawson (1994) | Professional actions as distinct categories |

### Events (E)

Ethical evaluation depends on event sequences - appropriate responses depend on historical context and anticipated future.

| Reference | Contribution |
|-----------|--------------|
| Zhang et al. (2023) | Moral event classification |
| Anderson & Anderson (2018) | Event sequence evaluation |
| Govindarajulu & Bringsjord (2017) | Temporal modal logic |
| Arkin (2008) | "Ethical black box" for event documentation |

### Capabilities (Ca)

Competence transcends technical skill - includes communication, knowledge, reasoning, values, and reflection.

| Reference | Contribution |
|-----------|--------------|
| Epstein (2002) | Multidimensional professional competence |
| Cervantes et al. (2020) | Capacities/capabilities/competencies taxonomy |
| Stenseke (2022) | Functional competence vs moral agency |
| Dennis et al. (2016) | Formal verification for capability sufficiency |

### Constraints (Cs)

Constraints establish inviolable limits - boundaries while obligations specify requirements.

| Reference | Contribution |
|-----------|--------------|
| Ganascia (2007) | Hard vs soft (defeasible) constraints |
| Furbach et al. (2014) | Deontic constraints and prioritization |
| Taddeo et al. (2024) | Legal/regulatory constraint interaction |
| Arkin (2008) | Architectural "ethical governors" |

---

## Precedent Discovery

ProEthica uses sentence embeddings and case-based reasoning to find relevant prior NSPE Board of Ethical Review decisions.

### Foundational Text

**Richter, M.M. & Weber, R.O. (2013)**
*Case-Based Reasoning: A Textbook*
Springer. ISBN: 978-3-642-40166-4.
[SpringerLink](https://link.springer.com/book/10.1007/978-3-642-40167-1)

Textbook covering CBR theory: similarity measures, retrieval, and adaptation. Provides the foundation for experience-based problem solving applied in ProEthica.

### Embedding Methods

**Reimers, N. & Gurevych, I. (2019)**
*Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks*
Proceedings of EMNLP-IJCNLP 2019, pp. 3982-3992.
[DOI: 10.18653/v1/D19-1410](https://doi.org/10.18653/v1/D19-1410) | [ACL Anthology](https://aclanthology.org/D19-1410/)

Sentence-BERT (SBERT) for semantic similarity via dense vectors. ProEthica uses all-MiniLM-L6-v2 for cosine similarity across case sections.

### Legal Case Retrieval

**Sun, Z., Zhang, K., Yu, W., Wang, H. & Xu, J. (2024)**
*Logic Rules as Explanations for Legal Case Retrieval*
Proceedings of LREC-COLING 2024, pp. 10747-10759.
[ACL Anthology](https://aclanthology.org/2024.lrec-main.939/)

Neural-Symbolic Legal Case Retrieval (NS-LCR): combines embeddings with logic rules for explainable retrieval in legal contexts.

**Wiratunga, N., Abeyratne, R., Jayawardena, L., et al. (2024)**
*CBR-RAG: Case-Based Reasoning for Retrieval Augmented Generation in LLMs for Legal Question Answering*
arXiv preprint arXiv:2404.04302.
[arXiv](https://arxiv.org/abs/2404.04302)

Integrates CBR with RAG for legal QA. Compares domain-specific vs general embeddings.

---

## Role-Based Ethics

**Rauch, C.B., Molineaux, M., Mainali, M., Sen, A., Floyd, M.W., & Weber, R.O. (2025)**
*Role-Based Ethics for Decision-Maker Alignment*
2025 IEEE Conference on Artificial Intelligence (CAI), pp. 1209-1212.

Foundational work on precedent-based role ethics that ProEthica extends.

**Oakley, J. & Cocking, D. (2001)**
*Virtue Ethics and Professional Roles*
Cambridge University Press.

Role-generated obligations framework that informs the Roles component.

---

## ProEthica System

**Rauch, C.B. & Weber, R.O. (2026)**
*ProEthica: A Professional Role-Based Ethical Analysis Tool Using LLM-Orchestrated, Ontology Supported Case-Based Reasoning*
Proceedings of the AAAI Conference on Artificial Intelligence. Singapore: AAAI Press.

The primary reference for ProEthica system architecture and methodology.

### BibTeX

```bibtex
@inproceedings{rauch2026proethica,
  title={ProEthica: A Professional Role-Based Ethical Analysis Tool Using
         LLM-Orchestrated, Ontology Supported Case-Based Reasoning},
  author={Rauch, Christopher B. and Weber, Rosina O.},
  booktitle={Proceedings of the AAAI Conference on Artificial Intelligence},
  year={2026},
  organization={AAAI Press},
  address={Singapore}
}
```

---

## Related Guides

- [Nine-Concept Framework](../concepts/nine-concepts.md) - Concept definitions
- [Transformation Types](transformation-types.md) - Classification details
- [Precedent Discovery](../how-to/precedent-discovery.md) - Using similarity search
