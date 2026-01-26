"""
Validation Export Service for Krippendorff's Alpha Analysis.

Exports evaluation data in formats suitable for inter-rater reliability calculation.
Supports both CSV and JSON output formats compatible with Python's krippendorff
package and R's irr package.
"""

import csv
import json
import io
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import func
from app import db
from app.models.experiment import ExperimentEvaluation, Prediction


class ValidationExportService:
    """Service for exporting validation study data for statistical analysis."""

    # Metric definitions with their sub-items
    METRICS = {
        'RTI': [
            'rti_premises_clear',
            'rti_steps_explicit',
            'rti_conclusion_supported',
            'rti_alternatives_acknowledged'
        ],
        'PBRQ': [
            'pbrq_precedents_identified',
            'pbrq_principles_extracted',
            'pbrq_adaptation_appropriate',
            'pbrq_selection_justified'
        ],
        'CA': [
            'ca_code_citations_correct',
            'ca_precedents_characterized',
            'ca_citations_support_claims'
        ],
        'DRA': [
            'dra_concerns_relevant',
            'dra_patterns_accepted',
            'dra_guidance_helpful',
            'dra_domain_weighted'
        ]
    }

    def __init__(self):
        pass

    def get_evaluation_data(
        self,
        experiment_run_id: Optional[int] = None,
        domain: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch all evaluation data, optionally filtered by experiment run or domain.

        Args:
            experiment_run_id: Filter by specific experiment run
            domain: Filter by evaluator domain ('engineering' or 'education')

        Returns:
            List of evaluation records with associated prediction data
        """
        query = db.session.query(
            ExperimentEvaluation,
            Prediction
        ).join(
            Prediction,
            ExperimentEvaluation.prediction_id == Prediction.id
        )

        if experiment_run_id:
            query = query.filter(
                ExperimentEvaluation.experiment_run_id == experiment_run_id
            )

        if domain:
            query = query.filter(
                ExperimentEvaluation.evaluator_domain == domain
            )

        results = query.all()

        evaluations = []
        for eval_record, prediction in results:
            evaluations.append({
                'evaluation_id': eval_record.id,
                'evaluator_id': eval_record.evaluator_id,
                'evaluator_domain': eval_record.evaluator_domain,
                'prediction_id': prediction.id,
                'document_id': prediction.document_id,
                'condition': prediction.condition,
                # RTI sub-items
                'rti_premises_clear': eval_record.rti_premises_clear,
                'rti_steps_explicit': eval_record.rti_steps_explicit,
                'rti_conclusion_supported': eval_record.rti_conclusion_supported,
                'rti_alternatives_acknowledged': eval_record.rti_alternatives_acknowledged,
                # PBRQ sub-items
                'pbrq_precedents_identified': eval_record.pbrq_precedents_identified,
                'pbrq_principles_extracted': eval_record.pbrq_principles_extracted,
                'pbrq_adaptation_appropriate': eval_record.pbrq_adaptation_appropriate,
                'pbrq_selection_justified': eval_record.pbrq_selection_justified,
                # CA sub-items
                'ca_code_citations_correct': eval_record.ca_code_citations_correct,
                'ca_precedents_characterized': eval_record.ca_precedents_characterized,
                'ca_citations_support_claims': eval_record.ca_citations_support_claims,
                # DRA sub-items
                'dra_concerns_relevant': eval_record.dra_concerns_relevant,
                'dra_patterns_accepted': eval_record.dra_patterns_accepted,
                'dra_guidance_helpful': eval_record.dra_guidance_helpful,
                'dra_domain_weighted': eval_record.dra_domain_weighted,
                # Overall preference
                'overall_preference': eval_record.overall_preference,
                'preference_justification': eval_record.preference_justification,
                # Computed means
                'rti_mean': eval_record.rti_mean,
                'pbrq_mean': eval_record.pbrq_mean,
                'ca_mean': eval_record.ca_mean,
                'dra_mean': eval_record.dra_mean,
                # Metadata
                'created_at': eval_record.created_at.isoformat() if eval_record.created_at else None,
                'meta_info': eval_record.meta_info
            })

        return evaluations

    def _compute_metric_mean(self, eval_data: Dict, metric: str) -> Optional[float]:
        """Compute mean score for a metric from its sub-items."""
        sub_items = self.METRICS.get(metric, [])
        scores = [eval_data.get(item) for item in sub_items]
        valid_scores = [s for s in scores if s is not None]
        if valid_scores:
            return round(sum(valid_scores) / len(valid_scores), 2)
        return None

    def export_for_krippendorff(
        self,
        experiment_run_id: Optional[int] = None,
        domain: Optional[str] = None,
        use_means: bool = True,
        format: str = 'csv'
    ) -> Tuple[str, str]:
        """
        Export evaluation data in format suitable for Krippendorff's alpha.

        The output format has:
        - Rows = evaluators (anonymous IDs)
        - Columns = items being rated (case_id + condition + metric)
        - Values = 1-7 Likert scores (means or sub-items)

        Args:
            experiment_run_id: Filter by experiment run
            domain: Filter by domain
            use_means: If True, export metric means; if False, export all sub-items
            format: 'csv' or 'json'

        Returns:
            Tuple of (content_string, filename)
        """
        evaluations = self.get_evaluation_data(experiment_run_id, domain)

        if not evaluations:
            if format == 'json':
                return json.dumps({'error': 'No evaluation data found', 'data': []}), 'empty_export.json'
            return 'No evaluation data found', 'empty_export.csv'

        # Organize data by evaluator
        evaluator_data = defaultdict(dict)
        all_columns = set()

        for eval_record in evaluations:
            evaluator_id = eval_record['evaluator_id']
            case_id = eval_record['document_id']
            condition = eval_record['condition']

            if use_means:
                # Export metric means
                for metric in ['RTI', 'PBRQ', 'CA', 'DRA']:
                    col_name = f"case_{case_id:03d}_{condition}_{metric}"
                    mean_key = f"{metric.lower()}_mean"
                    value = eval_record.get(mean_key)
                    if value is None:
                        # Compute from sub-items if not present
                        value = self._compute_metric_mean(eval_record, metric)
                    evaluator_data[evaluator_id][col_name] = value
                    all_columns.add(col_name)

                # Also include overall preference
                pref_col = f"case_{case_id:03d}_{condition}_preference"
                evaluator_data[evaluator_id][pref_col] = eval_record.get('overall_preference')
                all_columns.add(pref_col)
            else:
                # Export all sub-items
                for metric, sub_items in self.METRICS.items():
                    for sub_item in sub_items:
                        col_name = f"case_{case_id:03d}_{condition}_{sub_item}"
                        evaluator_data[evaluator_id][col_name] = eval_record.get(sub_item)
                        all_columns.add(col_name)

                # Include overall preference
                pref_col = f"case_{case_id:03d}_{condition}_preference"
                evaluator_data[evaluator_id][pref_col] = eval_record.get('overall_preference')
                all_columns.add(pref_col)

        # Sort columns for consistent ordering
        sorted_columns = sorted(all_columns)

        # Generate output
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        domain_suffix = f"_{domain}" if domain else ""
        level_suffix = "_means" if use_means else "_subitems"

        if format == 'json':
            output = {
                'metadata': {
                    'export_date': datetime.now().isoformat(),
                    'experiment_run_id': experiment_run_id,
                    'domain': domain,
                    'level': 'means' if use_means else 'sub-items',
                    'n_evaluators': len(evaluator_data),
                    'n_items': len(sorted_columns)
                },
                'columns': sorted_columns,
                'data': []
            }

            for evaluator_id in sorted(evaluator_data.keys()):
                row = {'evaluator_id': evaluator_id}
                for col in sorted_columns:
                    row[col] = evaluator_data[evaluator_id].get(col)
                output['data'].append(row)

            filename = f"krippendorff_export{domain_suffix}{level_suffix}_{timestamp}.json"
            return json.dumps(output, indent=2), filename

        else:  # CSV format
            output = io.StringIO()
            writer = csv.writer(output)

            # Header row
            header = ['evaluator_id'] + sorted_columns
            writer.writerow(header)

            # Data rows
            for evaluator_id in sorted(evaluator_data.keys()):
                row = [evaluator_id]
                for col in sorted_columns:
                    value = evaluator_data[evaluator_id].get(col)
                    row.append(value if value is not None else '')
                writer.writerow(row)

            filename = f"krippendorff_export{domain_suffix}{level_suffix}_{timestamp}.csv"
            return output.getvalue(), filename

    def export_comparison_summary(
        self,
        experiment_run_id: Optional[int] = None,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate summary statistics comparing baseline vs ProEthica.

        Returns:
            Dictionary with summary statistics for each condition and metric
        """
        evaluations = self.get_evaluation_data(experiment_run_id, domain)

        if not evaluations:
            return {'error': 'No evaluation data found'}

        # Organize by condition
        baseline_scores = defaultdict(list)
        proethica_scores = defaultdict(list)
        preference_counts = defaultdict(int)

        for eval_record in evaluations:
            condition = eval_record['condition']
            target = baseline_scores if condition == 'baseline' else proethica_scores

            for metric in ['RTI', 'PBRQ', 'CA', 'DRA']:
                mean_key = f"{metric.lower()}_mean"
                value = eval_record.get(mean_key)
                if value is None:
                    value = self._compute_metric_mean(eval_record, metric)
                if value is not None:
                    target[metric].append(value)

            # Count preferences (only on baseline evaluations to avoid double-counting)
            if condition == 'baseline' and eval_record.get('overall_preference') is not None:
                pref = eval_record['overall_preference']
                if pref < 0:
                    preference_counts['prefer_baseline'] += 1
                elif pref > 0:
                    preference_counts['prefer_proethica'] += 1
                else:
                    preference_counts['no_preference'] += 1

        def compute_stats(scores: List[float]) -> Dict:
            if not scores:
                return {'n': 0, 'mean': None, 'std': None, 'min': None, 'max': None}
            n = len(scores)
            mean = sum(scores) / n
            variance = sum((x - mean) ** 2 for x in scores) / n if n > 1 else 0
            std = variance ** 0.5
            return {
                'n': n,
                'mean': round(mean, 2),
                'std': round(std, 2),
                'min': min(scores),
                'max': max(scores)
            }

        summary = {
            'metadata': {
                'export_date': datetime.now().isoformat(),
                'experiment_run_id': experiment_run_id,
                'domain': domain
            },
            'baseline': {metric: compute_stats(scores) for metric, scores in baseline_scores.items()},
            'proethica': {metric: compute_stats(scores) for metric, scores in proethica_scores.items()},
            'preferences': dict(preference_counts),
            'total_evaluations': len(evaluations)
        }

        return summary

    def get_evaluator_progress(
        self,
        experiment_run_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Get progress summary for each evaluator.

        Returns:
            List of evaluator progress records
        """
        query = db.session.query(
            ExperimentEvaluation.evaluator_id,
            ExperimentEvaluation.evaluator_domain,
            func.count(ExperimentEvaluation.id).label('evaluations_completed'),
            func.min(ExperimentEvaluation.created_at).label('first_evaluation'),
            func.max(ExperimentEvaluation.created_at).label('last_evaluation')
        ).group_by(
            ExperimentEvaluation.evaluator_id,
            ExperimentEvaluation.evaluator_domain
        )

        if experiment_run_id:
            query = query.filter(
                ExperimentEvaluation.experiment_run_id == experiment_run_id
            )

        results = query.all()

        progress = []
        for row in results:
            progress.append({
                'evaluator_id': row.evaluator_id,
                'domain': row.evaluator_domain,
                'evaluations_completed': row.evaluations_completed,
                'first_evaluation': row.first_evaluation.isoformat() if row.first_evaluation else None,
                'last_evaluation': row.last_evaluation.isoformat() if row.last_evaluation else None
            })

        return progress

    # =========================================================================
    # Chapter 4 View Utility Export Methods
    # =========================================================================

    VIEW_UTILITY_METRICS = {
        'PROVISIONS': [
            'prov_standards_identified',
            'prov_connections_clear',
            'prov_normative_foundation'
        ],
        'QUESTIONS': [
            'ques_issues_visible',
            'ques_structure_aided',
            'ques_deliberation_needs'
        ],
        'DECISIONS': [
            'decs_choices_understood',
            'decs_alternatives_context',
            'decs_actions_obligations'
        ],
        'NARRATIVE': [
            'narr_situation_understood',
            'narr_relationships_clear',
            'narr_sequence_clear'
        ],
        'OVERALL': [
            'overall_helped_understand',
            'overall_surfaced_considerations',
            'overall_useful_deliberation'
        ]
    }

    def get_chapter4_evaluation_data(
        self,
        domain: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch Chapter 4 view utility evaluation data.

        Args:
            domain: Filter by evaluator domain ('engineering' or 'education')

        Returns:
            List of view utility evaluation records
        """
        from app.models.view_utility_evaluation import ViewUtilityEvaluation

        query = ViewUtilityEvaluation.query

        if domain:
            query = query.join(
                ViewUtilityEvaluation.session
            ).filter_by(evaluator_domain=domain)

        evaluations = query.all()

        results = []
        for e in evaluations:
            results.append({
                'evaluation_id': e.id,
                'evaluator_id': e.evaluator_id,
                'case_id': e.case_id,
                # Provisions View
                'prov_standards_identified': e.prov_standards_identified,
                'prov_connections_clear': e.prov_connections_clear,
                'prov_normative_foundation': e.prov_normative_foundation,
                'provisions_view_mean': e.provisions_view_mean,
                # Questions View
                'ques_issues_visible': e.ques_issues_visible,
                'ques_structure_aided': e.ques_structure_aided,
                'ques_deliberation_needs': e.ques_deliberation_needs,
                'questions_view_mean': e.questions_view_mean,
                # Decisions View
                'decs_choices_understood': e.decs_choices_understood,
                'decs_alternatives_context': e.decs_alternatives_context,
                'decs_actions_obligations': e.decs_actions_obligations,
                'decisions_view_mean': e.decisions_view_mean,
                # Narrative View
                'narr_situation_understood': e.narr_situation_understood,
                'narr_relationships_clear': e.narr_relationships_clear,
                'narr_sequence_clear': e.narr_sequence_clear,
                'narrative_view_mean': e.narrative_view_mean,
                # Overall Utility
                'overall_helped_understand': e.overall_helped_understand,
                'overall_surfaced_considerations': e.overall_surfaced_considerations,
                'overall_useful_deliberation': e.overall_useful_deliberation,
                'overall_utility_mean': e.overall_utility_mean,
                # Alignment
                'alignment_self_rating': e.alignment_self_rating,
                # Timestamps
                'completed_at': e.completed_at.isoformat() if e.completed_at else None
            })

        return results

    def export_chapter4_for_krippendorff(
        self,
        domain: Optional[str] = None,
        use_means: bool = True,
        format: str = 'csv'
    ) -> Tuple[str, str]:
        """
        Export Chapter 4 view utility data for Krippendorff's alpha calculation.

        Output format:
        - Rows = evaluators
        - Columns = case_id + view metric
        - Values = 1-7 Likert scores

        Args:
            domain: Filter by evaluator domain
            use_means: If True, export view means; if False, export all items
            format: 'csv' or 'json'

        Returns:
            Tuple of (content_string, filename)
        """
        evaluations = self.get_chapter4_evaluation_data(domain)

        if not evaluations:
            if format == 'json':
                return json.dumps({'error': 'No evaluation data found', 'data': []}), 'empty_export.json'
            return 'No evaluation data found', 'empty_export.csv'

        # Organize by evaluator
        evaluator_data = defaultdict(dict)
        all_columns = set()

        for eval_record in evaluations:
            evaluator_id = eval_record['evaluator_id']
            case_id = eval_record['case_id']

            if use_means:
                # Export view means
                for view in ['PROVISIONS', 'QUESTIONS', 'DECISIONS', 'NARRATIVE', 'OVERALL']:
                    col_name = f"case_{case_id:03d}_{view}"
                    mean_key = f"{view.lower()}_view_mean" if view != 'OVERALL' else 'overall_utility_mean'
                    value = eval_record.get(mean_key)
                    evaluator_data[evaluator_id][col_name] = value
                    all_columns.add(col_name)

                # Alignment rating
                align_col = f"case_{case_id:03d}_ALIGNMENT"
                evaluator_data[evaluator_id][align_col] = eval_record.get('alignment_self_rating')
                all_columns.add(align_col)
            else:
                # Export all individual items
                for view, items in self.VIEW_UTILITY_METRICS.items():
                    for item in items:
                        col_name = f"case_{case_id:03d}_{item}"
                        evaluator_data[evaluator_id][col_name] = eval_record.get(item)
                        all_columns.add(col_name)

                # Alignment rating
                align_col = f"case_{case_id:03d}_alignment_self_rating"
                evaluator_data[evaluator_id][align_col] = eval_record.get('alignment_self_rating')
                all_columns.add(align_col)

        sorted_columns = sorted(all_columns)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        domain_suffix = f"_{domain}" if domain else ""
        level_suffix = "_means" if use_means else "_items"

        if format == 'json':
            output = {
                'metadata': {
                    'export_date': datetime.now().isoformat(),
                    'study_type': 'chapter4_view_utility',
                    'domain': domain,
                    'level': 'means' if use_means else 'items',
                    'n_evaluators': len(evaluator_data),
                    'n_items': len(sorted_columns)
                },
                'columns': sorted_columns,
                'data': []
            }

            for evaluator_id in sorted(evaluator_data.keys()):
                row = {'evaluator_id': evaluator_id}
                for col in sorted_columns:
                    row[col] = evaluator_data[evaluator_id].get(col)
                output['data'].append(row)

            filename = f"chapter4_krippendorff{domain_suffix}{level_suffix}_{timestamp}.json"
            return json.dumps(output, indent=2), filename

        else:  # CSV
            output = io.StringIO()
            writer = csv.writer(output)

            header = ['evaluator_id'] + sorted_columns
            writer.writerow(header)

            for evaluator_id in sorted(evaluator_data.keys()):
                row = [evaluator_id]
                for col in sorted_columns:
                    value = evaluator_data[evaluator_id].get(col)
                    row.append(value if value is not None else '')
                writer.writerow(row)

            filename = f"chapter4_krippendorff{domain_suffix}{level_suffix}_{timestamp}.csv"
            return output.getvalue(), filename

    def export_chapter4_summary(
        self,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate summary statistics for Chapter 4 view utility study.

        Returns:
            Dictionary with summary statistics per view
        """
        evaluations = self.get_chapter4_evaluation_data(domain)

        if not evaluations:
            return {'error': 'No evaluation data found'}

        view_scores = {
            'PROVISIONS': [],
            'QUESTIONS': [],
            'DECISIONS': [],
            'NARRATIVE': [],
            'OVERALL': [],
            'ALIGNMENT': []
        }

        for eval_record in evaluations:
            if eval_record.get('provisions_view_mean') is not None:
                view_scores['PROVISIONS'].append(eval_record['provisions_view_mean'])
            if eval_record.get('questions_view_mean') is not None:
                view_scores['QUESTIONS'].append(eval_record['questions_view_mean'])
            if eval_record.get('decisions_view_mean') is not None:
                view_scores['DECISIONS'].append(eval_record['decisions_view_mean'])
            if eval_record.get('narrative_view_mean') is not None:
                view_scores['NARRATIVE'].append(eval_record['narrative_view_mean'])
            if eval_record.get('overall_utility_mean') is not None:
                view_scores['OVERALL'].append(eval_record['overall_utility_mean'])
            if eval_record.get('alignment_self_rating') is not None:
                view_scores['ALIGNMENT'].append(eval_record['alignment_self_rating'])

        def compute_stats(scores: List[float]) -> Dict:
            if not scores:
                return {'n': 0, 'mean': None, 'std': None, 'min': None, 'max': None}
            n = len(scores)
            mean = sum(scores) / n
            variance = sum((x - mean) ** 2 for x in scores) / n if n > 1 else 0
            std = variance ** 0.5
            return {
                'n': n,
                'mean': round(mean, 2),
                'std': round(std, 2),
                'min': min(scores),
                'max': max(scores)
            }

        return {
            'metadata': {
                'export_date': datetime.now().isoformat(),
                'study_type': 'chapter4_view_utility',
                'domain': domain,
                'total_evaluations': len(evaluations)
            },
            'view_utility': {view: compute_stats(scores) for view, scores in view_scores.items()}
        }

    def get_chapter4_retrospective_summary(
        self,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get summary of retrospective reflections including view rankings.

        Returns:
            Dictionary with retrospective summary data
        """
        from app.models.view_utility_evaluation import RetrospectiveReflection

        query = RetrospectiveReflection.query

        if domain:
            query = query.filter_by(evaluator_domain=domain)

        reflections = query.all()

        if not reflections:
            return {'error': 'No retrospective data found'}

        # Aggregate rankings (lower = more valuable)
        rank_totals = {
            'PROVISIONS': [],
            'QUESTIONS': [],
            'DECISIONS': [],
            'NARRATIVE': []
        }

        surfaced_count = {'yes': 0, 'no': 0}

        for r in reflections:
            if r.rank_provisions_view is not None:
                rank_totals['PROVISIONS'].append(r.rank_provisions_view)
            if r.rank_questions_view is not None:
                rank_totals['QUESTIONS'].append(r.rank_questions_view)
            if r.rank_decisions_view is not None:
                rank_totals['DECISIONS'].append(r.rank_decisions_view)
            if r.rank_narrative_view is not None:
                rank_totals['NARRATIVE'].append(r.rank_narrative_view)

            if r.surfaced_missed_considerations is True:
                surfaced_count['yes'] += 1
            elif r.surfaced_missed_considerations is False:
                surfaced_count['no'] += 1

        def mean_rank(ranks):
            return round(sum(ranks) / len(ranks), 2) if ranks else None

        return {
            'metadata': {
                'domain': domain,
                'total_reflections': len(reflections)
            },
            'view_rankings': {
                view: {
                    'mean_rank': mean_rank(ranks),
                    'n': len(ranks)
                }
                for view, ranks in rank_totals.items()
            },
            'surfaced_considerations': surfaced_count
        }
