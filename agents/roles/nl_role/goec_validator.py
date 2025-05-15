from typing import Optional
from agents.actions import ActionOutput
from agents.system.logs import logger
from agents.schema import Message
from agents.roles.role import Role
from agents.actions.nl_action.goec_search import GOECSearch

class GOECValidatorRole(Role):
    """
    GO/EC 验证角色，继承自 Role 类。
    该角色负责调用 GOECSearch 动作，根据 TermTranslatorRole 的结果中的 number 和 annotation，
    使用工具查询 GO 和 EC 对应的含义，并将结果发送到环境中。
    """

    name: str = "GOECValidator"
    profile: str = "GO/EC Validation Expert"
    goal: str = "Validate GO and EC terms based on TermTranslatorRole's results"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([GOECSearch])  # 使用 set_actions 设置动作

    async def _act(self, content: str = "") -> ActionOutput:
        """
        执行 GOECSearch 动作。
        """
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        rsp = await self.rc.todo.run(content=content)
        return rsp

    async def run(self, content: str = "") -> Optional[Message]:
        """
        运行 GO/EC 验证任务。

        Args:
            content (str): TermTranslatorRole 的结果（包含 GO/EC 编号和注释）。

        Returns:
            Optional[Message]: 发送到环境中的消息。
        """
        # 调用 _act 方法执行动作
        action_output = await self._act(content)
        if not action_output:
            logger.warning("GO/EC validation returned no result.")
            return None

        # 将 ActionOutput 转换为 Message
        result = Message(
            content=action_output.content,
            role=self.profile,
            cause_by=self.rc.todo,
            sent_from=self.name
        )

        # 将验证结果发送到环境中
        self.publish_message(result)
        logger.info(f"{self.name} sent validation result to the environment.")

        return result
