"""
NSPE Code of Ethics provisions with annotated codes and tag vocabulary.

Used by LLM-based feature extraction to identify provisions, outcomes,
and subject tags from case discussion and conclusion text.
"""

# NSPE Code of Ethics with provision numbers annotated.
# Mapped from the sequential paragraphs in nspe_code_for_engineers.txt
# to the standard citation format used in NSPE Board of Ethical Review cases.
NSPE_PROVISIONS_TEXT = """I. Fundamental Canons
I.1: Hold paramount the safety, health, and welfare of the public.
I.2: Perform services only in areas of their competence.
I.3: Issue public statements only in an objective and truthful manner.
I.4: Act for each employer or client as faithful agents or trustees.
I.5: Avoid deceptive acts.
I.6: Conduct themselves honorably, responsibly, ethically, and lawfully so as to enhance the honor, reputation, and usefulness of the profession.

II. Rules of Practice
II.1: Engineers shall hold paramount the safety, health, and welfare of the public.
II.1.a: If engineers' judgment is overruled under circumstances that endanger life or property, they shall notify their employer or client and such other authority as may be appropriate.
II.1.b: Engineers shall approve only those engineering documents that are in conformity with applicable standards.
II.1.c: Engineers shall not reveal facts, data, or information without the prior consent of the client or employer except as authorized or required by law or this Code.
II.1.d: Engineers shall not permit the use of their name or associate in business ventures with any person or firm that they believe is engaged in fraudulent or dishonest enterprise.
II.1.e: Engineers shall not aid or abet the unlawful practice of engineering by a person or firm.
II.1.f: Engineers having knowledge of any alleged violation of this Code shall report thereon to appropriate professional bodies and, when relevant, also to public authorities.
II.2: Engineers shall perform services only in the areas of their competence.
II.2.a: Engineers shall undertake assignments only when qualified by education or experience in the specific technical fields involved.
II.2.b: Engineers shall not affix their signatures to any plans or documents dealing with subject matter in which they lack competence, nor to any plan or document not prepared under their direction and control.
II.2.c: Engineers may accept assignments and assume responsibility for coordination of an entire project and sign and seal the engineering documents for the entire project, provided that each technical segment is signed and sealed only by the qualified engineers who prepared the segment.
II.3: Engineers shall issue public statements only in an objective and truthful manner.
II.3.a: Engineers shall be objective and truthful in professional reports, statements, or testimony. They shall include all relevant and pertinent information in such reports, statements, or testimony.
II.3.b: Engineers may express publicly technical opinions that are founded upon knowledge of the facts and competence in the subject matter.
II.3.c: Engineers shall issue no statements, criticisms, or arguments on technical matters that are inspired or paid for by interested parties, unless they have prefaced their comments by explicitly identifying the interested parties on whose behalf they are speaking.
II.4: Engineers shall act for each employer or client as faithful agents or trustees.
II.4.a: Engineers shall disclose all known or potential conflicts of interest that could influence or appear to influence their judgment or the quality of their services.
II.4.b: Engineers shall not accept compensation, financial or otherwise, from more than one party for services on the same project, unless the circumstances are fully disclosed and agreed to by all interested parties.
II.4.c: Engineers shall not solicit or accept financial or other valuable consideration, directly or indirectly, from outside agents in connection with the work for which they are responsible.
II.4.d: Engineers in public service as members, advisors, or employees of a governmental or quasi-governmental body or department shall not participate in decisions with respect to services solicited or provided by them or their organizations in private or public engineering practice.
II.4.e: Engineers shall not solicit or accept a contract from a governmental body on which a principal or officer of their organization serves as a member.
II.5: Engineers shall avoid deceptive acts.
II.5.a: Engineers shall not falsify their qualifications or permit misrepresentation of their or their associates' qualifications.
II.5.b: Engineers shall not offer, give, solicit, or receive, either directly or indirectly, any contribution to influence the award of a contract by public authority.

III. Professional Obligations
III.1: Engineers shall be guided in all their relations by the highest standards of honesty and integrity.
III.1.a: Engineers shall acknowledge their errors and shall not distort or alter the facts.
III.1.b: Engineers shall advise their clients or employers when they believe a project will not be successful.
III.1.c: Engineers shall not accept outside employment to the detriment of their regular work or interest.
III.1.d: Engineers shall not attempt to attract an engineer from another employer by false or misleading pretenses.
III.1.e: Engineers shall not promote their own interest at the expense of the dignity and integrity of the profession.
III.1.f: Engineers shall treat all persons with dignity, respect, fairness and without discrimination.
III.2: Engineers shall at all times strive to serve the public interest.
III.2.a: Engineers are encouraged to participate in civic affairs; career guidance for youths; and work for the advancement of the safety, health, and well-being of their community.
III.2.b: Engineers shall not complete, sign, or seal plans and/or specifications that are not in conformity with applicable engineering standards.
III.2.c: Engineers are encouraged to extend public knowledge and appreciation of engineering and its achievements.
III.2.d: Engineers are encouraged to adhere to the principles of sustainable development in order to protect the environment for future generations.
III.2.e: Engineers shall continue their professional development throughout their careers and should keep current in their specialty fields.
III.3: Engineers shall avoid all conduct or practice that deceives the public.
III.3.a: Engineers shall avoid the use of statements containing a material misrepresentation of fact or omitting a material fact.
III.3.b: Consistent with the foregoing, engineers may advertise for recruitment of personnel.
III.3.c: Consistent with the foregoing, engineers may prepare articles for the lay or technical press, but such articles shall not imply credit to the author for work performed by others.
III.4: Engineers shall not disclose, without consent, confidential information concerning the business affairs or technical processes of any present or former client or employer, or public body on which they serve.
III.4.a: Engineers shall not, without the consent of all interested parties, promote or arrange for new employment or practice in connection with a specific project for which the engineer has gained particular and specialized knowledge.
III.4.b: Engineers shall not, without the consent of all interested parties, participate in or represent an adversary interest in connection with a specific project or proceeding in which the engineer has gained particular specialized knowledge on behalf of a former client or employer.
III.5: Engineers shall not be influenced in their professional duties by conflicting interests.
III.5.a: Engineers shall not accept financial or other considerations, including free engineering designs, from material or equipment suppliers for specifying their product.
III.5.b: Engineers shall not accept commissions or allowances, directly or indirectly, from contractors or other parties dealing with clients or employers of the engineer in connection with work for which the engineer is responsible.
III.6: Engineers shall not attempt to obtain employment or advancement or professional engagements by untruthfully criticizing other engineers, or by other improper or questionable methods.
III.6.a: Engineers shall not request, propose, or accept a commission on a contingent basis under circumstances in which their judgment may be compromised.
III.6.b: Engineers in salaried positions shall accept part-time engineering work only to the extent consistent with policies of the employer and in accordance with ethical considerations.
III.6.c: Engineers shall not, without consent, use equipment, supplies, laboratory, or office facilities of an employer to carry on outside private practice.
III.7: Engineers shall not attempt to injure, maliciously or falsely, directly or indirectly, the professional reputation, prospects, practice, or employment of other engineers.
III.7.a: Engineers in private practice shall not review the work of another engineer for the same client, except with the knowledge of such engineer, or unless the connection of such engineer with the work has been terminated.
III.7.b: Engineers in governmental, industrial, or educational employ are entitled to review and evaluate the work of other engineers when so required by their employment duties.
III.7.c: Engineers in sales or industrial employ are entitled to make engineering comparisons of represented products with products of other suppliers.
III.8: Engineers shall accept personal responsibility for their professional activities, provided, however, that engineers may seek indemnification for services arising out of their practice for other than gross negligence.
III.8.a: Engineers shall conform with state registration laws in the practice of engineering.
III.8.b: Engineers shall not use association with a nonengineer, a corporation, or partnership as a cloak for unethical acts.
III.9: Engineers shall give credit for engineering work to those to whom credit is due, and will recognize the proprietary interests of others.
III.9.a: Engineers shall, whenever possible, name the person or persons who may be individually responsible for designs, inventions, writings, or other accomplishments.
III.9.b: Engineers using designs supplied by a client recognize that the designs remain the property of the client and may not be duplicated by the engineer for others without express permission.
III.9.c: Engineers, before undertaking work for others in connection with which the engineer may make improvements, plans, designs, inventions, or other records that may justify copyrights or patents, should enter into a positive agreement regarding ownership.
III.10: Engineers' designs, data, records, and notes referring exclusively to an employer's work are the employer's property. The employer should indemnify the engineer for use of the information for any purpose other than the original purpose.
"""

# Subject tag vocabulary from NSPE Board of Ethical Review case categorization.
# Tags are NSPE Code of Ethics subject categories extracted from case HTML metadata.
# This list is used to constrain LLM output to consistent labels.
NSPE_TAG_VOCABULARY = [
    "Advertising",
    "Associating with Others",
    "Community Service/Civic Affairs",
    "Competence",
    "Confidential Information",
    "Conflict of Interest",
    "Credit for Engineering Work",
    "Duty to Disclose",
    "Duty to the Public",
    "Employer",
    "Engineering Document",
    "Errors",
    "Faithful Agents and Trustees",
    "Firm Name",
    "Harassment and Anti-Discrimination",
    "Liability",
    "Licensure Laws",
    "Misrepresentation/Omission of Facts",
    "Opinions",
    "Outside Employment/Moonlighting",
    "Plans/Specifications",
    "Political Contributions, Gifts, Commissions",
    "Professional Reports, Statements, Testimony",
    "Professional Responsibility",
    "Proprietary Interests",
    "Public Awareness of Engineering",
    "Public Statements and Criticism",
    "Qualifications for Work",
    "Recruiting Engineer from Another Employer",
    "Remuneration",
    "Reviewing the Work of Other Engineers",
    "Self-Promotion",
    "Signing Plans/Documents",
    "Statements on Technical Matters for Interested Parties",
    "Sustainable Development",
    "Unethical Practice by Others",
    "Unfair Competition",
]
