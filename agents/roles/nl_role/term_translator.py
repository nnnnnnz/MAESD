from typing import Optional
from agents.actions import ActionOutput
from agents.system.logs import logger
from agents.schema import Message
from agents.roles.role import Role
from agents.actions.nl_action.trans_terms import TransTerms

class TermTranslatorRole(Role):
    """
    术语翻译角色，继承自 Role 类。
    该角色负责调用 TransTerms 动作，将 IntentAnalyserRole 的结果中的生物学术语转换为 GO 和 EC 编号，并将结果发送到环境中。
    """

    name: str = "TermTranslator"
    profile: str = "Term Translation Expert"
    goal: str = "Translate biological terms to GO and EC numbers"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([TransTerms])  # 使用 set_actions 设置动作

    async def _act(self, content: str = "") -> ActionOutput:
        """
        执行 TransTerms 动作。
        """
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        rsp = await self.rc.todo.run(content=content)
        return rsp

    async def run(self, content: str = "") -> Optional[Message]:
        """
        运行术语翻译任务。

        Args:
            content (str): IntentAnalyserRole 的结果（包含生物学术语和意图）。

        Returns:
            Optional[Message]: 发送到环境中的消息。
        """
        # 调用 _act 方法执行动作
        action_output = await self._act(content)
        if not action_output:
            logger.warning("Term translation returned no result.")
            return None

        # 将 ActionOutput 转换为 Message
        result = Message(
            content=action_output.content,
            role=self.profile,
            cause_by=self.rc.todo,
            sent_from=self.name
        )

        # 将翻译结果发送到环境中
        self.publish_message(result)
        logger.info(f"{self.name} sent translation result to the environment.")

        return result
