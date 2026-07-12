from app.services.study_strategy_catalog import CATALOG_VERSION, REFERENCES, STRATEGIES, build_study_actions, validate_study_actions
from app.schemas import StudyTopicInput

def test_catalog_is_versioned_and_references_are_owned():
    assert CATALOG_VERSION == "1.0.0"
    assert {"retrieval_practice", "spaced_practice", "interleaving", "concrete_examples", "self_explanation"} == set(STRATEGIES)
    assert {"dunlosky2013", "roediger_karpicke2006"} == set(REFERENCES)
    for strategy in STRATEGIES.values():
        assert strategy["name_pt"] and strategy["allowed_actions"] and strategy["situations"] and strategy["limitations"]
        assert set(strategy["reference_ids"]).issubset(REFERENCES)

def test_actions_have_no_pseudoscientific_duration_without_availability():
    actions = build_study_actions({"assessments": []}, [StudyTopicInput(title="Árvores AVL", difficulty="high", status="not_started")])
    assert actions and all(action["estimated_minutes"] is None for action in actions)
    assert validate_study_actions(actions) == actions
