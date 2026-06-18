# Defeasibility View

The Defeasibility View presents how a case resolves competition between professional obligations. It is reached at `/cases/<id>/defeasibility` and renders the defeasibility edges that the extraction pipeline materializes into each case ontology.

## Background

Professional ethics cases frequently turn on obligations that cannot all be satisfied at once. One obligation prevails, and the competing obligation is defeated under a specific circumstance. ProEthica records this structure with three object properties from `proethica-core` rather than as narrative prose:

| Property | Relation | Characteristic |
|----------|----------|----------------|
| `competesWith` | Obligation to Obligation | Symmetric |
| `prevailsOver` | Winning Obligation to losing Obligation | Asymmetric, irreflexive |
| `defeasibleUnder` | Losing Obligation to the licensing State | Directed |

A resolved conflict reads as a triple: when obligation `O1` `competesWith` `O2`, and a state `S` obtains, then `O1` `prevailsOver` `O2`, which is `defeasibleUnder` `S`. Each edge carries a PROV-O derivation node that attributes it to a verbatim quote from a source field. The property reference is in [Ontology Properties](../concepts/ontology-properties.md), and the materialization step is described in [System Architecture](../admin-guide/architecture.md).

## Reading the View

The view reads edges directly from the committed case ontologies, not from temporary extraction storage, so it reflects the same graph that OntServe serves. It is organized into two bands.

### Band 1: Resolved Conflicts in the Case

The first band shows the conflicts internal to the case being viewed. For each conflict it presents the competing obligations, the obligation that prevails, the state under which the losing obligation is defeated, and the board conclusions that the resolution supports. This band is derived from the anchor case's own committed ontology.

### Band 2: Cross-Case Comparison

The second band places the case's central tension beside the same tension as it appears in other cases. The comparison set is selected by matching the case's defeated-obligation pattern against every other case: candidates are ranked by the similarity of their yielding-obligation label to the anchor's, combined with the overlap of their licensing State contexts, and the closest few are shown. The ranking reads from an index built at commit time from the committed case ontologies, so the band reflects the current corpus without re-reading every case at view time. For a small set of demonstration themes a fixed comparison set is pinned instead, so a walkthrough renders identically. Each row links to the corresponding case and its ontology.

The matching key is the extracted formalism, not the case subject tags: two cases are judged comparable because their obligation-defeat structure aligns, not because they share a topic label.

## Entity Definitions

Labels in both bands carry hover popovers sourced from the committed case ontologies: the entity label, its definition or comment, and its concept category. Because the lookup is built from the committed TTL of each case in the view, the definitions match what OntServe stores and cover every case shown, not only the anchor case.

## Related Documentation

- [Ontology Properties](../concepts/ontology-properties.md) - The defeasibility properties and their domains
- [System Architecture](../admin-guide/architecture.md) - Edge materialization and the conformance gate
- [Nine-Component Framework](../concepts/nine-components.md) - The component types the edges connect
