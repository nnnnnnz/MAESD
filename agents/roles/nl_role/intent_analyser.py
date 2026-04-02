#!/usr/bin/env python
# -*- coding: utf-8 -*-

from agents.system.logs import logger
from agents.system.schema import Message
from agents.roles.role import Role
from agents.actions.nl_action.intent_analysis import IntentAnalyse
from agents.actions.nl_action.trans_terms import TransTerms


class IntentAnalyser(Role):
    """MetaGPT-style NLP role that first segments intent and then translates terms."""

    def __init__(
        self,
        name: str = "IntentAnalyser",
        profile: str = "Intent Analysis Expert",
        goal: str = "Analyze user intent and translate it into structured biological constraints",
        constraints: str = "Keep the output faithful to the original biological intent",
        **kwargs,
    ):
        super().__init__(name=name, profile=profile, goal=goal, constraints=constraints, **kwargs)
        self._init_actions([IntentAnalyse, TransTerms])

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: ready to execute intent analysis pipeline")
        intent_output = await self.actions[0].run(self.rc.important_memory or self.rc.history)
        translated_output = await self.actions[1].run(intent_output.instruct_content or intent_output.content)
        msg = Message(
            content=translated_output.content,
            instruct_content=translated_output.instruct_content,
            role=self.profile,
            cause_by=type(self.actions[1]),
            sent_from=self.name,
        )
        self.rc.memory.add(msg)
        return msg
