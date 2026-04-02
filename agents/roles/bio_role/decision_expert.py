#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from agents.actions.action_bank.requirement import Requirement
from agents.maesd import DecisionExpert
from agents.roles.role import Role
from agents.schema import Message


class DecisionExpertRole(Role):
    """Decision role that mimics MAESD's Pareto-style loop controller."""

    def __init__(
        self,
        name: str = "Derek",
        profile: str = "DecisionExpert",
        goal: str = "Select elite candidates and decide whether optimization should continue",
        constraints: str = "Prefer non-dominated candidates and explain the decision clearly",
        **kwargs,
    ):
        super().__init__(name=name, profile=profile, goal=goal, constraints=constraints, **kwargs)
        self.decider = DecisionExpert()
        self._watch([Requirement])

    async def _act(self) -> Message:
        latest = self.rc.news[-1] if self.rc.news else Message(content="")
        decision = {
            "message": latest.content,
            "policy": "pareto-front-first",
            "improvement_rule": "delta > 0.01 on any objective",
        }
        return Message(content=str(decision), role=self.profile, cause_by=Requirement, sent_from=self.name)
