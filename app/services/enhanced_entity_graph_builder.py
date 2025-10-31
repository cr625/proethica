"""
Enhanced Entity Graph Builder

Builds a comprehensive entity graph showing:
- Code provisions and their relationships
- Precedent cases and how they relate to provisions
- Questions and conclusions
- Principle tensions and obligation conflicts from institutional analysis
- All entities (roles, states, resources, principles, obligations, constraints, capabilities, actions, events)

This is the FINAL step in Step 4 synthesis, run after all Parts A-D complete.
"""

import logging
from typing import Dict, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EnhancedEntityNode:
    """A node in the enhanced entity graph."""
    node_id: str
    node_type: str  # provision, precedent, question, conclusion, principle, obligation, constraint, role, etc.
    label: str
    definition: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnhancedEntityEdge:
    """An edge between nodes in the enhanced entity graph."""
    edge_id: str
    source_id: str
    target_id: str
    edge_type: str  # informs, applies_to, conflicts_with, similar_to, answered_by, etc.
    label: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class EnhancedEntityGraphBuilder:
    """
    Builds a comprehensive entity graph from all Step 4 synthesis results.

    Includes:
    - Provisions (from Part A)
    - Precedent citations (from Part A-bis)
    - Questions and Conclusions (from Part B)
    - All 9-concept entities (from Pass 1-3)
    - Institutional analysis (from Part D): tensions, conflicts, constraints
    """

    def __init__(self):
        self.nodes: Dict[str, EnhancedEntityNode] = {}
        self.edges: List[EnhancedEntityEdge] = []

    def build_graph(
        self,
        provisions: List[Any],
        precedent_citations: List[Dict],
        questions: List[Any],
        conclusions: List[Any],
        all_entities: Dict[str, List[Any]],
        institutional_analysis: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Build the complete entity graph from all synthesis components.

        Returns:
            Dictionary with nodes and edges for visualization
        """
        logger.info("[Enhanced Graph Builder] Building comprehensive entity graph...")

        # 1. Add provision nodes
        self._add_provision_nodes(provisions)

        # 2. Add precedent citation nodes and link to provisions
        self._add_precedent_nodes(precedent_citations, provisions)

        # 3. Add question and conclusion nodes
        self._add_question_conclusion_nodes(questions, conclusions, provisions)

        # 4. Add entity nodes (9-concept entities)
        self._add_entity_nodes(all_entities, provisions)

        # 5. Add institutional analysis (tensions, conflicts, constraints)
        if institutional_analysis:
            self._add_institutional_analysis(institutional_analysis, all_entities)

        logger.info(f"[Enhanced Graph Builder] Graph complete: {len(self.nodes)} nodes, {len(self.edges)} edges")

        return {
            'nodes': [self._node_to_dict(n) for n in self.nodes.values()],
            'edges': [self._edge_to_dict(e) for e in self.edges],
            'stats': {
                'total_nodes': len(self.nodes),
                'total_edges': len(self.edges),
                'node_types': self._count_node_types()
            }
        }

    def _add_provision_nodes(self, provisions: List[Any]):
        """Add NSPE Code provision nodes."""
        for prov in provisions:
            node_id = f"prov_{prov.id}"
            code = prov.rdf_json_ld.get('codeProvision', prov.entity_label) if hasattr(prov, 'rdf_json_ld') and prov.rdf_json_ld else prov.entity_label

            self.nodes[node_id] = EnhancedEntityNode(
                node_id=node_id,
                node_type='provision',
                label=code,
                definition=prov.entity_definition or "",
                metadata={'db_id': prov.id}
            )

    def _add_precedent_nodes(self, precedent_citations: List[Dict], provisions: List[Any]):
        """Add precedent case nodes and link to related provisions."""
        for pc in precedent_citations:
            case_num = pc.get('caseNumber', '')
            node_id = f"precedent_{case_num.replace('-', '_')}"

            self.nodes[node_id] = EnhancedEntityNode(
                node_id=node_id,
                node_type='precedent',
                label=pc.get('fullCitation', f"Case {case_num}"),
                definition=pc.get('caseTitle', ''),
                metadata={
                    'year': pc.get('yearDecided'),
                    'sourceUrl': pc.get('sourceUrl'),
                    'context': pc.get('citationContext', '')[:200]  # Truncate for graph
                }
            )

            # Link precedent to related provisions
            related_provisions = pc.get('relatedProvisions', [])
            for prov_code in related_provisions:
                # Find provision with this code
                prov = next((p for p in provisions if prov_code in (
                    p.rdf_json_ld.get('codeProvision', '') if hasattr(p, 'rdf_json_ld') and p.rdf_json_ld else ''
                ) or prov_code in p.entity_label), None)

                if prov:
                    edge_id = f"prov_{prov.id}_to_{node_id}"
                    self.edges.append(EnhancedEntityEdge(
                        edge_id=edge_id,
                        source_id=f"prov_{prov.id}",
                        target_id=node_id,
                        edge_type='similar_to_precedent',
                        label='similar to'
                    ))

    def _add_question_conclusion_nodes(self, questions: List[Any], conclusions: List[Any], provisions: List[Any]):
        """Add question and conclusion nodes with relationships."""
        # Add questions
        for idx, q in enumerate(questions):
            q_num = getattr(q, 'question_number', idx + 1)
            node_id = f"question_{q_num}"
            self.nodes[node_id] = EnhancedEntityNode(
                node_id=node_id,
                node_type='question',
                label=getattr(q, 'question_text', str(q))[:50],  # Truncate for display
                definition=getattr(q, 'question_text', str(q)),
                metadata={'question_number': q_num}
            )

            # Link questions to related provisions
            related_provs = getattr(q, 'related_provisions', [])
            for prov_code in related_provs:
                prov = next((p for p in provisions if prov_code in (
                    p.rdf_json_ld.get('codeProvision', '') if hasattr(p, 'rdf_json_ld') and p.rdf_json_ld else ''
                ) or prov_code in p.entity_label), None)

                if prov:
                    edge_id = f"prov_{prov.id}_to_{node_id}"
                    self.edges.append(EnhancedEntityEdge(
                        edge_id=edge_id,
                        source_id=f"prov_{prov.id}",
                        target_id=node_id,
                        edge_type='provision_informs_question',
                        label='informs'
                    ))

        # Add conclusions
        for idx, c in enumerate(conclusions):
            c_num = getattr(c, 'conclusion_number', idx + 1)
            node_id = f"conclusion_{c_num}"
            self.nodes[node_id] = EnhancedEntityNode(
                node_id=node_id,
                node_type='conclusion',
                label=getattr(c, 'conclusion_text', str(c))[:50],
                definition=getattr(c, 'conclusion_text', str(c)),
                metadata={'conclusion_number': c_num}
            )

            # Link conclusions to questions they answer
            answers = getattr(c, 'answers_questions', [])
            for q_num in answers:
                q_node_id = f"question_{q_num}"
                if q_node_id in self.nodes:
                    edge_id = f"{q_node_id}_to_{node_id}"
                    self.edges.append(EnhancedEntityEdge(
                        edge_id=edge_id,
                        source_id=q_node_id,
                        target_id=node_id,
                        edge_type='question_answered_by_conclusion',
                        label='answered by'
                    ))

    def _add_entity_nodes(self, all_entities: Dict[str, List[Any]], provisions: List[Any]):
        """Add 9-concept entity nodes (roles, principles, obligations, etc.)."""
        # Focus on key entity types for the graph
        key_types = ['principles', 'obligations', 'constraints', 'roles', 'capabilities']

        for entity_type in key_types:
            entity_list = all_entities.get(entity_type, [])
            for entity in entity_list:
                node_id = f"{entity_type[:-1]}_{entity.id}"  # Remove plural 's'

                self.nodes[node_id] = EnhancedEntityNode(
                    node_id=node_id,
                    node_type=entity_type[:-1],  # singular form
                    label=entity.entity_label[:50],
                    definition=entity.entity_definition or "",
                    metadata={'db_id': entity.id}
                )

        # Link provisions to entities they establish/apply to
        for prov in provisions:
            if hasattr(prov, 'rdf_json_ld') and prov.rdf_json_ld:
                applies_to = prov.rdf_json_ld.get('appliesTo', [])
                for entity_ref in applies_to:
                    entity_type = entity_ref.get('entity_type', '')
                    entity_label = entity_ref.get('entity_label', '')

                    # Find matching entity node
                    matching_node = next((
                        node_id for node_id, node in self.nodes.items()
                        if entity_label in node.label and entity_type in node.node_type
                    ), None)

                    if matching_node:
                        edge_id = f"prov_{prov.id}_applies_to_{matching_node}"
                        self.edges.append(EnhancedEntityEdge(
                            edge_id=edge_id,
                            source_id=f"prov_{prov.id}",
                            target_id=matching_node,
                            edge_type='provision_applies_to_entity',
                            label='applies to'
                        ))

    def _add_institutional_analysis(self, institutional_analysis: Dict[str, Any], all_entities: Dict[str, List[Any]]):
        """Add principle tensions and obligation conflicts as edges."""
        # Add principle tension edges
        principle_tensions = institutional_analysis.get('principle_tensions', [])
        for tension in principle_tensions:
            p1_label = tension.get('principle1', '')
            p2_label = tension.get('principle2', '')

            # Find matching principle nodes
            p1_node = next((
                node_id for node_id, node in self.nodes.items()
                if node.node_type == 'principle' and p1_label in node.label
            ), None)

            p2_node = next((
                node_id for node_id, node in self.nodes.items()
                if node.node_type == 'principle' and p2_label in node.label
            ), None)

            if p1_node and p2_node:
                edge_id = f"tension_{p1_node}_{p2_node}"
                self.edges.append(EnhancedEntityEdge(
                    edge_id=edge_id,
                    source_id=p1_node,
                    target_id=p2_node,
                    edge_type='principle_tension',
                    label='conflicts with',
                    metadata={'description': tension.get('tension_description', '')}
                ))

        # Add obligation conflict edges
        obligation_conflicts = institutional_analysis.get('obligation_conflicts', [])
        for conflict in obligation_conflicts:
            o1_label = conflict.get('obligation1', '')
            o2_label = conflict.get('obligation2', '')

            # Find matching obligation nodes
            o1_node = next((
                node_id for node_id, node in self.nodes.items()
                if node.node_type == 'obligation' and o1_label in node.label
            ), None)

            o2_node = next((
                node_id for node_id, node in self.nodes.items()
                if node.node_type == 'obligation' and o2_label in node.label
            ), None)

            if o1_node and o2_node:
                edge_id = f"conflict_{o1_node}_{o2_node}"
                self.edges.append(EnhancedEntityEdge(
                    edge_id=edge_id,
                    source_id=o1_node,
                    target_id=o2_node,
                    edge_type='obligation_conflict',
                    label='conflicts with',
                    metadata={'description': conflict.get('conflict_description', '')}
                ))

    def _count_node_types(self) -> Dict[str, int]:
        """Count nodes by type."""
        type_counts = {}
        for node in self.nodes.values():
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1
        return type_counts

    def _node_to_dict(self, node: EnhancedEntityNode) -> Dict:
        """Convert node to dictionary for JSON serialization."""
        return {
            'id': node.node_id,
            'type': node.node_type,
            'label': node.label,
            'definition': node.definition,
            'metadata': node.metadata
        }

    def _edge_to_dict(self, edge: EnhancedEntityEdge) -> Dict:
        """Convert edge to dictionary for JSON serialization."""
        return {
            'id': edge.edge_id,
            'source': edge.source_id,
            'target': edge.target_id,
            'type': edge.edge_type,
            'label': edge.label,
            'metadata': edge.metadata
        }
