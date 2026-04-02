#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Iterable, Optional

from agents.actions.action import Action
from agents.roles.role import Role
from agents.schema import Message


class CustomRole(Role):
    """Generic configurable role similar to MetaGPT's dynamic role composition."""

    def __init__(
        self,
        name: str,
        profile: str,
        goal: str,
        role_prompt: str = "",
        steps: Optional[list[str]] = None,
        tool: Optional[list[str]] = None,
        watch_actions: Optional[Iterable[type[Action]]] = None,
        **kwargs,
    ):
        super().__init__(name=name, profile=profile, goal=goal, constraints=role_prompt or "", **kwargs)
        self.role_prompt = role_prompt
        self.steps = steps or []
        self.tools = tool or []
        if watch_actions:
            self._watch(watch_actions)

    async def _act(self) -> Message:
        latest = self.rc.news[-1] if self.rc.news else Message(content="")
        summary = {
            "role": self.name,
            "goal": self.goal,
            "steps": self.steps,
            "tools": self.tools,
            "latest_input": latest.content,
        }
        return Message(content=str(summary), role=self.profile, cause_by=self.rc.todo or "CustomRole", sent_from=self.name)
