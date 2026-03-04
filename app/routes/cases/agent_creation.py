"""Agent-assisted case creation routes."""

import uuid
import logging
from flask import request, jsonify, render_template, redirect, url_for, flash
from flask_login import current_user
from app.utils.environment_auth import auth_optional, auth_required_for_write, auth_required_for_llm
from app.services.agents.case_creation_agent import CaseCreationAgent
from app.services.conversation_to_case_service import ConversationToCaseService
from app.models.agent_conversation import AgentConversation
from app import db

logger = logging.getLogger(__name__)


def register_agent_creation_routes(bp):

    @bp.route('/new/agent', methods=['GET'])
    @auth_required_for_write
    def agent_assisted_creation():
        """Display agent-assisted case creation interface with ontology integration."""
        try:
            from app.models.world import World
            worlds = World.query.all()

            default_world = worlds[0] if worlds else None

            case_agent = CaseCreationAgent(world_id=default_world.id if default_world else None)

            ontology_categories = []
            if default_world:
                entities = case_agent.ontology_service.get_entities_for_world(default_world)
                for category_name, concepts in entities.get("entities", {}).items():
                    ontology_categories.append({
                        "name": category_name,
                        "count": len(concepts),
                        "concepts": concepts[:5]
                    })

            if not ontology_categories:
                fallback_categories = ["Role", "Principle", "Obligation", "State", "Resource", "Action", "Event", "Capability"]
                ontology_categories = [{"name": cat, "count": 0, "concepts": []} for cat in fallback_categories]

            return render_template('agent_case_creation.html',
                                 worlds=worlds,
                                 ontology_categories=ontology_categories,
                                 default_world=default_world,
                                 current_user=current_user)

        except Exception as e:
            logger.error(f"Error loading agent case creation interface: {e}")
            flash(f"Error loading AI assistant: {str(e)}", 'error')
            return redirect(url_for('cases.case_options'))

    @bp.route('/new/agent/api', methods=['POST'])
    @auth_required_for_llm
    def agent_creation_api():
        """API endpoint for agent interactions with ontology integration."""
        try:
            data = request.get_json()

            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No data provided'
                }), 400

            prompt = data.get('prompt', '')
            world_id = data.get('world_id')
            selected_categories = data.get('selected_categories', [])
            selected_concepts = data.get('selected_concepts', {})
            conversation_history = data.get('conversation_history', [])

            if not prompt:
                return jsonify({
                    'success': False,
                    'error': 'No prompt provided'
                }), 400

            case_agent = CaseCreationAgent(world_id=world_id)
            case_agent.set_selected_categories(selected_categories)
            case_agent.set_selected_concepts(selected_concepts)

            scenario_data = {
                'world_id': world_id,
                'conversation_history': conversation_history,
                'request_type': 'case_creation'
            }

            analysis = case_agent.analyze(
                scenario_data=scenario_data,
                decision_text=prompt,
                options=[],
                previous_results=None
            )

            formatted_response = case_agent.format_response_for_ui(analysis)

            return jsonify({
                'success': True,
                'response': formatted_response
            })

        except Exception as e:
            logger.error(f"Error in agent creation API: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/new/agent/concepts/<category>', methods=['GET'])
    @auth_optional
    def get_category_concepts(category):
        """Get concepts for a specific ontological category."""
        try:
            world_id = request.args.get('world_id', type=int)

            if not world_id:
                return jsonify({
                    'success': False,
                    'error': 'World ID required'
                }), 400

            case_agent = CaseCreationAgent(world_id=world_id)

            concepts = case_agent.get_category_concepts(category, world_id)

            return jsonify({
                'success': True,
                'category': category,
                'concepts': concepts
            })

        except Exception as e:
            logger.error(f"Error getting concepts for category {category}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/new/agent/generate', methods=['POST'])
    @auth_required_for_llm
    def generate_case_from_conversation():
        """Generate NSPE-format case from agent conversation."""
        try:
            data = request.get_json()

            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No conversation data provided'
                }), 400

            world_id = data.get('world_id')
            conversation_history = data.get('conversation_history', [])
            selected_concepts = data.get('selected_concepts', {})
            conversation_metadata = data.get('conversation_metadata', {})

            if not conversation_history:
                return jsonify({
                    'success': False,
                    'error': 'No conversation history provided'
                }), 400

            session_id = str(uuid.uuid4())

            conversation = AgentConversation(
                session_id=session_id,
                user_id=current_user.username if current_user else None,
                world_id=world_id,
                title="Language Model-Assisted Case Creation",
                metadata=conversation_metadata
            )

            for msg in conversation_history:
                conversation.add_message(
                    content=msg.get('content', ''),
                    role=msg.get('type', 'user'),
                    metadata=msg.get('metadata', {})
                )

            for category, concepts in selected_concepts.items():
                if concepts:
                    conversation.update_ontology_selections(category, concepts)

            db.session.add(conversation)
            db.session.flush()

            case_service = ConversationToCaseService()
            generated_case = case_service.generate_case_from_conversation(conversation)

            if not generated_case:
                return jsonify({
                    'success': False,
                    'error': 'Failed to generate case from conversation'
                }), 500

            return jsonify({
                'success': True,
                'case_id': generated_case.id,
                'case_title': generated_case.title,
                'case_url': url_for('cases.view_case', id=generated_case.id),
                'conversation_id': conversation.id,
                'message': 'Case generated successfully from conversation'
            })

        except Exception as e:
            logger.error(f"Error generating case from conversation: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
