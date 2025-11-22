"""Integration checks for blueprint registration."""

from app import create_app
from app.blueprints import (
    ADMIN_BLUEPRINTS,
    ANNOTATION_BLUEPRINTS,
    CORE_BLUEPRINTS,
    SCENARIO_BLUEPRINTS,
)


def _expected_blueprint_names():
    expected = set()
    for blueprint, _ in (
        CORE_BLUEPRINTS
        + SCENARIO_BLUEPRINTS
        + ANNOTATION_BLUEPRINTS
        + ADMIN_BLUEPRINTS
    ):
        expected.add(blueprint.name)
    return expected


def test_all_expected_blueprints_registered():
    app = create_app('testing')
    registered = set(app.blueprints.keys())

    expected = _expected_blueprint_names()

    assert expected.issubset(registered)
