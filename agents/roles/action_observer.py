#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Iterable, Optional

from agents.roles.role import Role
from agents.schema import Message


class ActionObserver(Role):
    """Collect downstream action outputs for later summarization or UI streaming."""

    def __init__(
        self,
        name: str = "Ava",
        profile: str = "ActionObserver",
        goal: str = "Observe action outputs and aggregate artifacts",
        steps: Optional[list[str]] = None,
        watch_actions: Optional[Iterable] = None,
        init_actions: Optional[Iterable] = None,
        **kwargs,
    ):
        super().__init__(name=name, profile=profile, goal=goal, constraints="Do not modify artifacts; only aggregate them", **kwargs)
        self.steps = list(steps or [])
        self.init_actions = list(init_actions or [])
        if watch_actions:
            self._watch(watch_actions)

    async def _act(self) -> Message:
        latest = self.rc.news[-1] if self.rc.news else Message(content="")
        payload = {
            "remaining_steps": self.steps,
            "observed_message": latest.content,
        }
        return Message(content=str(payload), role=self.profile, cause_by=self.rc.todo or "ActionObserver", sent_from=self.name)
