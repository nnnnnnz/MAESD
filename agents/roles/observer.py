#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from agents.actions.action_bank.requirement import Requirement
from agents.roles.role import Role
from agents.schema import Message


class ObserverAgents(Role):
    """Observe manager outputs and summarize the selected role roster."""

    def __init__(self, name: str = "Olivia", profile: str = "Agents Observer", goal: str = "Summarize the active role roster", **kwargs):
        super().__init__(name=name, profile=profile, goal=goal, constraints="Keep the summary concise", **kwargs)
        self._watch([Requirement])

    async def _act(self) -> Message:
        latest = self.rc.news[-1] if self.rc.news else Message(content="")
        return Message(content=latest.content, role=self.profile, cause_by=Requirement, sent_from=self.name)


class ObserverPlans(Role):
    """Observe manager outputs and summarize execution plan progress."""

    def __init__(self, name: str = "Peter", profile: str = "Plans Observer", goal: str = "Monitor plan progress", **kwargs):
        super().__init__(name=name, profile=profile, goal=goal, constraints="Echo the latest plan state only", **kwargs)
        self._watch([Requirement])

    async def _act(self) -> Message:
        latest = self.rc.news[-1] if self.rc.news else Message(content="")
        return Message(content=latest.content, role=self.profile, cause_by=Requirement, sent_from=self.name)
