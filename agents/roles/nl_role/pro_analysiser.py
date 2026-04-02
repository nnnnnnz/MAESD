#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional

from agents.actions.nl_action.pro_analysis import ProAnalysis
from agents.roles.role import Role
from agents.system.logs import logger
from agents.system.schema import Message


class ProAnalyser(Role):
    """Analyse validated design intents and return a protein-design-focused report."""

    def __init__(
        self,
        name: str = "ProAnalyser",
        profile: str = "Protein Design Analyst",
        goal: str = "Analyze protein design intents and generate validation reports",
        constraints: str = "Keep the analysis biologically grounded and implementation-oriented",
        **kwargs,
    ):
        super().__init__(name=name, profile=profile, goal=goal, constraints=constraints, **kwargs)
        self._init_actions([ProAnalysis])

    async def _act(self, message: Optional[Message] = None) -> Optional[Message]:
        if message is None:
            message = self.rc.news[-1] if self.rc.news else None
        if not message or not message.content:
            raise ValueError("No content provided in the message.")

        logger.info(f"{self.name} is analyzing the protein design intent")
        action_output = await self.actions[0].run(message.content)
        response_message = Message(
            content=action_output.content,
            instruct_content=action_output.instruct_content,
            role=self.profile,
            cause_by=ProAnalysis,
            sent_from=self.name,
            send_to=message.sent_from if message else None,
        )
        return response_message
