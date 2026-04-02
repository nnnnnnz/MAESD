#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from agents.actions.action_bank.requirement import Requirement
from agents.maesd import DesignCandidate, DesignConstraints, ProteinScreeningExpert
from agents.roles.role import Role
from agents.schema import Message


class ProtScreenExpert(Role):
    """Protein screening expert that mirrors SGHFS-style validation in the paper."""

    def __init__(
        self,
        name: str = "Sophia",
        profile: str = "ProtScreenExpert",
        goal: str = "Evaluate candidate sequences with structural, energetic and functional criteria",
        constraints: str = "Report FSM, SMR and GCI style signals in a structured way",
        **kwargs,
    ):
        super().__init__(name=name, profile=profile, goal=goal, constraints=constraints, **kwargs)
        self.screener = ProteinScreeningExpert()
        self._watch([Requirement])

    async def _act(self) -> Message:
        latest = self.rc.news[-1] if self.rc.news else Message(content="")
        sequence = self._extract_sequence(latest.content)
        constraints = DesignConstraints(
            original_prompt=latest.content,
            intents=[latest.content],
            go_terms=[],
            ec_numbers=[],
            domains=[],
            motifs=[],
            target_length=max(60, len(sequence) or 180),
            optimization_goals=["general_function_preservation"],
        )
        candidate = DesignCandidate(sequence=sequence or "A" * constraints.target_length, origin="manual", iteration=0)
        candidate.scores = self.screener.score(candidate, constraints)
        return Message(content=str(candidate.scores), role=self.profile, cause_by=Requirement, sent_from=self.name)

    def _extract_sequence(self, text: str) -> str:
        cleaned = "".join(ch for ch in text.upper() if ch in "ACDEFGHIKLMNPQRSTVWY")
        return cleaned
