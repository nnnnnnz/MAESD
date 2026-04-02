#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional

from agents.actions.action import ActionOutput
from agents.actions.nl_action.goec_search import GOECSearch
from agents.roles.role import Role
from agents.schema import Message
from agents.system.logs import logger


class GOECValidatorRole(Role):
    """Validate GO/EC annotations produced by the translation stage."""

    def __init__(
        self,
        name: str = "GOECValidator",
        profile: str = "GO/EC Validation Expert",
        goal: str = "Validate GO and EC terms against tool-backed knowledge",
        constraints: str = "Preserve traceability between the source intent and the validated identifiers",
        **kwargs,
    ):
        super().__init__(name=name, profile=profile, goal=goal, constraints=constraints, **kwargs)
        self._init_actions([GOECSearch])

    async def _act(self, content: str = "") -> ActionOutput:
        logger.info(f"{self._setting}: validating GO/EC annotations")
        return await self.rc.todo.run(content=content)

    async def run(self, content: str = "") -> Optional[Message]:
        action_output = await self._act(content)
        if not action_output:
            logger.warning("GO/EC validation returned no result.")
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
