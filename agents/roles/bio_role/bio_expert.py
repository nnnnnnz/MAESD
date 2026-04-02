#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from agents.actions.action_bank.requirement import Requirement
from agents.maesd import IntentRecognitionAgent
from agents.roles.role import Role
from agents.schema import Message


class BioExpert(Role):
    """MetaGPT-style domain expert that turns validated text into an executable MAESD brief."""

    def __init__(
        self,
        name: str = "Bianca",
        profile: str = "BioExpert",
        goal: str = "Integrate biological constraints into a coherent protein design brief",
        constraints: str = "Preserve user intent while making the brief executable for sequence design",
        **kwargs,
    ):
        super().__init__(name=name, profile=profile, goal=goal, constraints=constraints, **kwargs)
        self.ira = IntentRecognitionAgent()
        self._watch([Requirement])

    async def _act(self) -> Message:
        latest = self.rc.news[-1] if self.rc.news else Message(content="")
        constraints = self.ira.parse(latest.content)
        msg = Message(content=constraints.original_prompt, instruct_content=constraints, role=self.profile, cause_by=Requirement, sent_from=self.name)
        self.rc.memory.add(msg)
        return msg
