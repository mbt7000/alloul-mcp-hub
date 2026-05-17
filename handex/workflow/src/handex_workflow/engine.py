from __future__ import annotations
from typing import Any


class StateMachineEngine:
    """
    Pure Python state machine. Definition format:
    {
        "states": ["draft", "submitted", "reviewing", "approved", "rejected"],
        "initial": "draft",
        "transitions": [
            {"from": "draft",      "to": "submitted",  "trigger": "submit",   "requires_role": "employee"},
            {"from": "submitted",  "to": "reviewing",  "trigger": "start_review", "requires_role": "reviewer"},
            {"from": "reviewing",  "to": "approved",   "trigger": "approve",  "requires_role": "reviewer"},
            {"from": "reviewing",  "to": "rejected",   "trigger": "reject",   "requires_role": "reviewer"},
        ],
        "terminal_states": ["approved", "rejected"],
        "sla_hours": {"submitted": 48, "reviewing": 24}
    }
    """

    def __init__(self, definition: dict[str, Any]) -> None:
        self._def = definition
        self._states: set[str] = set(definition["states"])
        self._transitions: list[dict[str, Any]] = definition.get("transitions", [])
        self._terminal: set[str] = set(definition.get("terminal_states", []))

    def initial_state(self) -> str:
        return self._def["initial"]

    def can_transition(self, from_state: str, trigger: str) -> dict[str, Any] | None:
        for t in self._transitions:
            if t["from"] == from_state and t["trigger"] == trigger:
                return t
        return None

    def next_state(self, from_state: str, trigger: str) -> str | None:
        t = self.can_transition(from_state, trigger)
        return t["to"] if t else None

    def is_terminal(self, state: str) -> bool:
        return state in self._terminal

    def available_triggers(self, from_state: str) -> list[str]:
        return [t["trigger"] for t in self._transitions if t["from"] == from_state]

    def required_role(self, from_state: str, trigger: str) -> str | None:
        t = self.can_transition(from_state, trigger)
        return t.get("requires_role") if t else None
