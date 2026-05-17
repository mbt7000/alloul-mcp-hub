import pytest
from handex_workflow.engine import StateMachineEngine


def test_engine_transitions() -> None:
    defn = {
        "states": ["draft", "submitted", "approved"],
        "initial": "draft",
        "transitions": [
            {"from": "draft", "to": "submitted", "trigger": "submit"},
            {"from": "submitted", "to": "approved", "trigger": "approve"},
        ],
        "terminal_states": ["approved"],
    }
    engine = StateMachineEngine(defn)
    assert engine.initial_state() == "draft"
    assert engine.next_state("draft", "submit") == "submitted"
    assert engine.next_state("submitted", "approve") == "approved"
    assert engine.next_state("draft", "approve") is None
    assert engine.is_terminal("approved") is True
    assert engine.is_terminal("draft") is False


def test_engine_available_triggers() -> None:
    defn = {
        "states": ["a", "b", "c"],
        "initial": "a",
        "transitions": [
            {"from": "a", "to": "b", "trigger": "go"},
            {"from": "a", "to": "c", "trigger": "skip"},
        ],
        "terminal_states": ["b", "c"],
    }
    engine = StateMachineEngine(defn)
    triggers = engine.available_triggers("a")
    assert "go" in triggers
    assert "skip" in triggers
    assert engine.available_triggers("b") == []
