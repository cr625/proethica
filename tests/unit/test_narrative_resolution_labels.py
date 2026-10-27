"""
Board Resolution card of the Step 5 narrative view.

Conclusions of type board_explicit are shown as Board findings. When a case
has none, the card states that no explicit Board finding was extracted and
labels the remaining conclusions as analytical, so that the extended analysis
is not presented under the Board heading as if it were the finding of the Board.
"""

from pathlib import Path

from jinja2 import Environment

TEMPLATE = (Path(__file__).resolve().parents[2] / 'app' / 'templates'
            / 'scenario_pipeline' / 'step5_narrative.html')


def _render_card(conclusions):
    text = TEMPLATE.read_text(encoding='utf-8')
    start = text.index('<!-- Resolution / Conclusions Card -->')
    end = text.index('<!-- Key Takeaways Card -->')
    env = Environment(autoescape=True)
    env.globals['url_for'] = lambda endpoint, **kw: '/' + endpoint
    narrative = {'resolution': {'conclusions': conclusions}}
    return env.from_string(text[start:end]).render(narrative=narrative, case={'id': 8})


def test_board_conclusions_are_board_findings():
    html = _render_card([
        {'text': 'It was ethical.', 'conclusion_type': 'board_explicit'},
        {'text': 'An extension.', 'conclusion_type': 'analytical_extension'},
    ])
    assert 'Board Finding</span>' in html
    assert 'It was ethical.' in html
    assert 'An extension.' not in html
    assert 'Plus 1 extended analysis conclusion.' in html


def test_without_board_conclusions_the_rest_is_labelled_analytical():
    html = _render_card([
        {'text': 'An extension.', 'conclusion_type': 'analytical_extension'},
        {'text': 'A response.', 'conclusion_type': 'question_response'},
    ])
    assert 'No explicit Board finding was extracted for this case.' in html
    assert 'Board Finding</span>' not in html
    assert html.count('Analytical</span>') == 2
