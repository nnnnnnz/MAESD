#!/usr/bin/env python
# -*- coding: utf-8 -*-
from typing import Optional
from agents.actions import ActionOutput
from agents.system.logs import logger
from agents.system.memory import Memory
from agents.system.schema import Message
from agents.roles.role import Role
from agents.actions.nl_action.intent_analysis import IntentAnalyse
from agents.actions.nl_action.trans_terms import TransTerms

class IntentAnalyser(Role):
    """
    意图分析角色，继承自 Role 类。
    该角色负责依次执行 IntentAnalyse 和 TransTerms 动作，分析用户输入的意图并转换为术语。
    """

    def __init__(self, name: str = "IntentAnalyser", profile: str = "Intent Analysis Expert",
                 goal: str = "Analyze user intent and translate to biological terms",
                 constraints: str = "", **kwargs):
        """
        初始化 IntentAnalyser。

        Args:
            name (str): 角色名称。
            profile (str): 角色描述。
            goal (str): 角色目标。
            constraints (str): 角色约束条件。
            **kwargs: 其他参数，传递给父类。
        """
        super().__init__(name=name, profile=profile, goal=goal, constraints=constraints, **kwargs)
        # 初始化动作
        self._init_actions([IntentAnalyse, TransTerms])

    async def _act(self) -> Message:
        """
        依次执行 IntentAnalyse 和 TransTerms 动作，并返回最终结果。
        """
        logger.info(f"{self._setting}: ready to {self._rc.todo}")

        # 执行第一个动作：IntentAnalyse
        intent_analyse_action = self._rc.todo
        intent_analyse_output = await intent_analyse_action.run(self._rc.important_memory)

        # 提取 IntentAnalyse 的输出
        intent_content = intent_analyse_output.instruct_content

        # 执行第二个动作：TransTerms
        trans_terms_action = self._rc.todo
        trans_terms_output = await trans_terms_action.run(intent_content)

        # 将 ActionOutput 转换为 Message
        msg = Message(
            content=trans_terms_output.content,
            instruct_content=trans_terms_output.instruct_content,
            role=self.profile,
            cause_by=type(self._rc.todo)
        )
        self._rc.memory.add(msg)

        return msg
