#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional

from agents.actions.action import ActionOutput
from agents.actions.nl_action.trans_terms import TransTerms
from agents.roles.role import Role
from agents.schema import Message
from agents.system.logs import logger


class TermTranslatorRole(Role):
    """Translate biological terminology into GO/EC-friendly structured annotations."""

    def __init__(
        self,
        name: str = "TermTranslator",
        profile: str = "Term Translation Expert",
        goal: str = "Translate biological terms into GO and EC identifiers",
        constraints: str = "Prefer precise biological identifiers over vague paraphrases",
        **kwargs,
    ):
        super().__init__(name=name, profile=profile, goal=goal, constraints=constraints, **kwargs)
        self._init_actions([TransTerms])

    async def _act(self, content: str = "") -> ActionOutput:
        logger.info(f"{self._setting}: translating biological terms")
        return await self.rc.todo.run(content=content)

    async def run(self, content: str = "") -> Optional[Message]:
        action_output = await self._act(content)
        if not action_output:
            logger.warning("Term translation returned no result.")
            return None
        result = Message(
            content=action_output.content,
            instruct_content=action_output.instruct_content,
            role=self.profile,
            cause_by=self.rc.todo,
            sent_from=self.name,
        )
        self.publish_message(result)
        return result
