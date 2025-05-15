from typing import Optional
from agents.system.logs import logger
from agents.roles.role import Role
from agents.actions.nl_action.pro_analysis import ProAnalysis
from agents.system.schema import Message

class ProAnalyser(Role):
    """
    A role that specializes in analyzing protein design intents and generating validation reports.
    """

    def __init__(self, name: str = "ProAnalyser", profile: str = "Protein Design Analyst", goal: str = "Analyze protein design intents and generate validation reports"):
        super().__init__(name, profile, goal)
        self._init_actions([ProAnalysis])  # Initialize with the ProAnalysis action

    async def _act(self, message: Optional[Message] = None) -> Optional[Message]:
        """
        Perform the analysis based on the received message.
        """
        try:
            logger.info(f"{self.name} is analyzing the protein design intent...")

            # Extract content from the message
            if not message or not message.content:
                raise ValueError("No content provided in the message.")
            content = message.content

            # Run the ProAnalysis action
            pro_analysis_action = self.get_action_by_name("ProAnalysis")
            if not pro_analysis_action:
                raise ValueError("ProAnalysis action not found.")
            action_output = await pro_analysis_action.run(content)

            # Generate a response message
            response_message = Message(
                content=action_output.content,
                role=self.profile,
                cause_by=ProAnalysis,
                sent_from=self.name,
                send_to=message.sent_from if message else None
            )

            logger.info(f"{self.name} analysis completed successfully.")
            return response_message

        except Exception as e:
            logger.error(f"Error in {self.name}: {e}")
            raise
