# ProEthica Color Scheme

This document defines the color scheme used throughout ProEthica visualizations for consistency and clarity.

## Entity Type Colors

ProEthica extracts 9 entity types organized into 4 passes. Each type has a distinct color for easy identification.

### Pass 1 - Context (Foundation)

| Type | Code | Color |
|------|------|-------|
| Role | R | <span style="display:inline-block;width:80px;height:24px;background:#0d6efd;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Blue</span> |
| State | S | <span style="display:inline-block;width:80px;height:24px;background:#6f42c1;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Purple</span> |
| Resource | Rs | <span style="display:inline-block;width:80px;height:24px;background:#20c997;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Teal</span> |

### Pass 2 - Normative (Requirements)

| Type | Code | Color |
|------|------|-------|
| Principle | P | <span style="display:inline-block;width:80px;height:24px;background:#fd7e14;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Orange</span> |
| Obligation | O | <span style="display:inline-block;width:80px;height:24px;background:#dc3545;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Red</span> |
| Constraint | Cs | <span style="display:inline-block;width:80px;height:24px;background:#6c757d;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Gray</span> |
| Capability | Ca | <span style="display:inline-block;width:80px;height:24px;background:#0dcaf0;border-radius:4px;vertical-align:middle;color:#212529;text-align:center;line-height:24px;font-size:12px;">Cyan</span> |

### Pass 3 - Temporal (Dynamics)

| Type | Code | Color |
|------|------|-------|
| Action | A | <span style="display:inline-block;width:80px;height:24px;background:#198754;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Green</span> |
| Event | E | <span style="display:inline-block;width:80px;height:24px;background:#ffc107;border-radius:4px;vertical-align:middle;color:#212529;text-align:center;line-height:24px;font-size:12px;">Yellow</span> |

### Step 4 - Synthesis (Analysis)

| Type | Color |
|------|-------|
| Code Provision | <span style="display:inline-block;width:80px;height:24px;background:#6c757d;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Gray</span> |
| Ethical Question | <span style="display:inline-block;width:80px;height:24px;background:#0dcaf0;border-radius:4px;vertical-align:middle;color:#212529;text-align:center;line-height:24px;font-size:12px;">Cyan</span> |
| Ethical Conclusion | <span style="display:inline-block;width:80px;height:24px;background:#198754;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Green</span> |

## Pipeline Step Colors (Standardized Terminology)

The extraction pipeline uses consistent colors for each step. Each step contains Pass 1 (Facts) and Pass 2 (Discussion) extractions.

| Step | Name | Hex | Entities Extracted |
|------|------|-----|-------------------|
| Step 1 | Contextual Framework | #3b82f6 (Blue) | Roles (R), States (S), Resources (Rs) |
| Step 2 | Normative Framework | #8b5cf6 (Purple) | Principles (P), Obligations (O), Constraints (Cs), Capabilities (Ca) |
| Step 3 | Temporal Framework | #14b8a6 (Teal) | Actions (A), Events (E) |
| Step 4 | Synthesis & Analysis | #64748b (Slate) | Provisions, Questions, Conclusions, Decision Points |

### Terminology Reference

| Term | Meaning |
|------|---------|
| **Step** | Major pipeline stage (1-4) |
| **Pass 1** | Facts section extraction within a step |
| **Pass 2** | Discussion section extraction within a step |
| **Phase** | Sub-stages within Step 4 (2A, 2B, 2C, 2D, 3, 4) |

### Step 4 Phases

| Phase | Name | Description |
|-------|------|-------------|
| 2A | Code Provisions | NSPE code references |
| 2B | Questions & Conclusions | Ethical questions and board conclusions |
| 2C | Transformation | Case transformation analysis |
| 2D | Rich Analysis | Arguments and causal links |
| 3 | Decision Points | E1-E3 algorithmic synthesis |
| 4 | Narrative | Case narrative construction |

## Pass Filter Colors

The graph filter buttons use neutral colors that group entity types by their extraction pass.

| Pass | Name | Color | Includes |
|------|------|-------|----------|
| 1 | Context | <span style="display:inline-block;width:80px;height:24px;background:#3b82f6;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Blue</span> | R, S, Rs |
| 2 | Normative | <span style="display:inline-block;width:80px;height:24px;background:#8b5cf6;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Purple</span> | P, O, Cs, Ca |
| 3 | Temporal | <span style="display:inline-block;width:80px;height:24px;background:#14b8a6;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Teal</span> | A, E |
| 4 | Synthesis | <span style="display:inline-block;width:80px;height:24px;background:#64748b;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Slate</span> | Provisions, Q, C |

## Flow Graph (Reasoning Flow)

The Flow tab shows how NSPE provisions inform questions and conclusions.

| Node Type | Color | Shape |
|-----------|-------|-------|
| Provision | <span style="display:inline-block;width:80px;height:24px;background:#495057;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Dark Gray</span> | Rectangle |
| Question | <span style="display:inline-block;width:80px;height:24px;background:#0dcaf0;border-radius:4px;vertical-align:middle;color:#212529;text-align:center;line-height:24px;font-size:12px;">Cyan</span> | Diamond |
| Conclusion | <span style="display:inline-block;width:80px;height:24px;background:#198754;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Green</span> | Rounded |
| Entity | <span style="display:inline-block;width:80px;height:24px;background:#1d4ed8;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Blue</span> | Circle/Rounded |

## Precedent Network

The Similarity Network uses colors to indicate case outcomes.

| Outcome | Color |
|---------|-------|
| Ethical | <span style="display:inline-block;width:80px;height:24px;background:#198754;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Green</span> |
| Unethical | <span style="display:inline-block;width:80px;height:24px;background:#dc3545;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Red</span> |
| Mixed | <span style="display:inline-block;width:80px;height:24px;background:#fd7e14;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Orange</span> |
| Current Case | <span style="display:inline-block;width:80px;height:24px;background:#0d6efd;border-radius:4px;vertical-align:middle;color:white;text-align:center;line-height:24px;font-size:12px;">Blue</span> |

Edge thickness indicates similarity strength between cases.
