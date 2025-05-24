# 4.6 Participant Review Protocol

The participant review protocol implements a streamlined online evaluation system designed to collect reliable comparative assessments while minimizing participant burden and maximizing data quality. The protocol emphasizes simplicity and clarity to ensure consistent evaluation across diverse participant backgrounds.

## Online Platform Design

**Interface Simplicity**: The evaluation platform presents clean, side-by-side comparisons of original NSPE content with system predictions. Participants view cases in a standardized format with clear section labels and consistent presentation structure across all evaluations.

**Progressive Disclosure**: Information is presented incrementally to avoid cognitive overload. Participants first read case facts and questions, then view paired reasoning outputs, and finally complete evaluation questions before proceeding to the next comparison.

**Responsive Design**: The platform functions across desktop and mobile devices, enabling convenient participation while maintaining consistent presentation quality and user experience.

## Participant Recruitment and Demographics

**Target Population**: Adult participants with post-secondary education representing diverse professional backgrounds. This demographic provides educated assessment capability without specialized ethics expertise that might create evaluation bias.

**Sample Size Planning**: Target enrollment of 60-80 participants to ensure adequate statistical power for detecting meaningful differences while accounting for potential dropout and incomplete responses.

**Recruitment Strategy**: Online recruitment through academic networks, professional organizations, and general survey platforms ensures diverse participant pool without systematic bias toward particular professional or educational backgrounds.

**Screening Criteria**: Basic screening ensures participants can read and evaluate complex professional content in English and have sufficient time to provide thoughtful assessments.

## Evaluation Session Structure

**Session Length**: Individual evaluation sessions require approximately 20-25 minutes, balancing comprehensive assessment with participant engagement and completion rates.

**Randomized Assignment**: Participants are randomly assigned to evaluate different case subsets across the three comparison conditions, ensuring balanced coverage while preventing individual participant fatigue.

**Condition Distribution**: Each participant evaluates 2-3 cases from each condition (conclusion, discussion, combined) for a total of 6-8 comparisons per session, providing sufficient data while maintaining manageable workload.

## Evaluation Questions and Response Format

**Structured Rating Questions**: 
- "Which reasoning do you find more logically coherent?" (7-point scale from strongly prefer left to strongly prefer right)
- "Which reasoning is more persuasive and convincing?" (7-point scale)
- "Which reasoning appears more thorough and complete?" (7-point scale)
- "Overall, which reasoning do you prefer?" (Binary choice with optional explanation)

**Clarity Assessment**: Participants rate reasoning accessibility using a single 7-point scale: "How clear and understandable is each reasoning approach?" This captures practical communication effectiveness for non-expert audiences.

**Open-Ended Feedback**: Optional text boxes allow participants to explain preferences and identify specific strengths or weaknesses in reasoning approaches. This qualitative data provides insights into evaluation reasoning and system improvement opportunities.

## Randomization and Blinding Procedures

**Output Randomization**: System outputs (ProEthica vs. baseline) are randomly assigned to left/right presentation positions for each comparison, preventing systematic position bias in preference ratings.

**Case Order Randomization**: The sequence of case presentations is randomized for each participant to control for order effects and ensure balanced evaluation across all cases.

**System Anonymization**: All system outputs are presented without identifying labels or system names. Participants evaluate "Reasoning A" vs. "Reasoning B" without knowledge of which system generated each output.

**Double-Blind Design**: Neither participants nor data collection interface reveal system identities, ensuring unbiased evaluation based solely on reasoning content quality.

## Data Quality Assurance

**Attention Checks**: Periodic comprehension questions and consistency checks identify participants who are not engaging thoughtfully with evaluation materials, enabling data quality filtering without compromising participant experience.

**Response Time Monitoring**: Tracking of evaluation completion times identifies unusually fast responses that may indicate insufficient consideration, while avoiding penalties for participants who work efficiently.

**Consistency Analysis**: Within-participant consistency across similar cases provides reliability assessment and identifies potential evaluation errors or systematic response patterns.

## Alternative Assessment Approaches Considered

**LLM-Based Evaluation**: Automated evaluation using additional LLM systems could provide consistent assessment but would introduce systematic biases based on training data and model preferences. Human evaluation provides more reliable assessment of practical reasoning quality for diverse audiences.

**Expert Panel Review**: Professional ethicists or engineers could provide specialized assessment but would create potential conflicts of interest and limit evaluation to narrow expert perspectives rather than broader practical effectiveness.

**Crowdsourced Evaluation**: Large-scale crowdsourcing could provide extensive data but would sacrifice assessment quality and introduce noise from inattentive or unqualified participants.

The chosen approach balances assessment quality with practical implementation while avoiding systematic biases that could compromise evaluation validity.

## Data Collection and Analysis Preparation

**Automated Data Recording**: All participant responses, response times, and evaluation metadata are automatically recorded in structured format for statistical analysis.

**Privacy Protection**: Participant data collection follows standard research ethics protocols with informed consent and data anonymization to protect participant privacy while enabling meaningful analysis.

**Analysis-Ready Format**: Data collection produces analysis-ready datasets with appropriate coding for statistical software, enabling efficient transition from data collection to results analysis.

The participant review protocol provides systematic, unbiased evaluation of ontology-constrained reasoning effectiveness while maintaining practical implementation feasibility and participant accessibility.
