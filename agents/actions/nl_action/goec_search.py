from typing import List, Dict, Optional
from agents.actions import ActionOutput
from agents.system.logs import logger
from agents.actions.action import Action
from agents.system.tools.go_api import search_go_by_definition
from agents.system.tools.enzy_api import get_ec_info


# Prompt Template
PROMPT_TEMPLATE = '''
-----
# System
You are an expert at calling tools to verify that EC numbers and GO numbers correspond correctly with their annotations.

# Input
{content}

# Requirements
1. Read the JSON list and follow the steps.
2. Description needs to be documented.
3. Use get_go_definition for GO numbers and get_ec_info for EC numbers.
4. Add validation results to original JSON with specific fields: GO: store definition from tool response; EC: store accept_name from tool response.

# Steps
1. Read a JSON list in the following format and follow the following instructions:
{
    "intent": "intent_1",
    "annotations": [
        {
            "number": "GO:0016787",
            "annotation": "Hydrolase activity; involved in the hydrolysis of plastic polymers."
        },
        {
            "number": "EC 3.1.1.74",
            "annotation": "Poly(ethylene terephthalate) hydrolase (PETase); catalyzes the degradation of PET plastic."
        }
    ]
}
Instructions:
   - "intent": Distinguish the json list you get by intent, it will be used when you output the result.
   - "annotations": Contains fields with numbers and comments to validate.
   - "number": It may be a GO number or an EC number. If it is a GO number, it starts with "GO:". In the case of EC, the number starts with "EC ".
   - "annotation": The content of the comment that needs to be verified does not need to be changed and remains as output.
   - Save these results in groups, leaving the name and description unprocessed. Proceed to the terms section as the next step.
2. For every "intent_":
2.1 Record the number of the intent, filled in the "intent" field at output time.
2.2 Create a new field named val_def in annotations to store the search results.
2.3 If the number field in the input starts with "GO", use the get_go_definition tool; If it starts with "EC", use the get_ec_info tool.
2.4 If it is GO, save the definition field in the search result to the val_def field; If EC, save the accept_name field in the search result to the val_def field.

# Format example
Your final output should ALWAYS in the following format:
{format_example}

# Attention:
1. Make sure you don't confuse the two different situations.
2. Make sure you use the right tools.
3. Output format carefully referenced "Format example".
-----
'''

FORMAT_EXAMPLE = '''
-----
## Intent List
{
    "intent": "intent_1",
    "annotations": [
        {
            "number": "GO:0016787",
            "annotation": "Hydrolase activity...",
            "val_def": "Catalysis of the hydrolysis..."
        },
        {
            "number": "EC 3.1.1.74",
            "annotation": "PETase description...",
            "val_def": "poly(ethylene terephthalate) hydrolase"
        }
    ]
}
-----
'''

OUTPUT_MAPPING = {
    "Intent List": (str, "JSON blob containing intent and annotations"),
}


class GOECSearch(Action):
    name: str = "GOECSearch"

    async def get_go_definition(self, go_number: str) -> str:
        """
        Fetch the definition of a GO number using the search_go_by_definition tool.

        Args:
            go_number (str): The GO number to fetch the definition for.

        Returns:
            str: The definition of the GO number.
        """
        try:
            results, error = search_go_by_definition(go_number)
            if error:
                logger.warning(f"Error fetching GO definition for {go_number}: {error}")
                return ""
            if results:
                return results[0].get("definition", "")
            return ""
        except Exception as e:
            logger.error(f"Error fetching GO definition for {go_number}: {e}")
            raise

    async def get_ec_info(self, ec_number: str) -> str:
        """
        Fetch the accept_name of an EC number using the get_ec_info tool.

        Args:
            ec_number (str): The EC number to fetch the accept_name for.

        Returns:
            str: The accept_name of the EC number.
        """
        try:
            info, error = get_ec_info(ec_number)
            if error:
                logger.warning(f"Error fetching EC info for {ec_number}: {error}")
                return ""
            return info.get("accepted_name", "")
        except Exception as e:
            logger.error(f"Error fetching EC info for {ec_number}: {e}")
            raise

    async def run(self, content: str) -> ActionOutput:
        """
        Analyze the input content, validate GO and EC numbers, and return structured results.

        Args:
            content (str): Input text containing intents and annotations.

        Returns:
            ActionOutput: Structured output containing the validated GO/EC numbers and annotations.
        """
        try:
            # Format the prompt with the input content and format example
            prompt = PROMPT_TEMPLATE.format(content=content, format_example=FORMAT_EXAMPLE)

            # Call the LLM to analyze the content and generate the output
            content, instruct_content = await self._aask_v1(
                prompt=prompt,
                output_data_mapping=OUTPUT_MAPPING
            )

            # Parse the content to extract intents and annotations
            intents = self._parse_intents(content)

            # Validate each annotation using the appropriate tool
            for intent in intents:
                for annotation in intent.get("annotations", []):
                    number = annotation.get("number", "")
                    if number.startswith("GO:"):
                        annotation["val_def"] = await self.get_go_definition(number)
                    elif number.startswith("EC "):
                        annotation["val_def"] = await self.get_ec_info(number)

            # Return the result as an ActionOutput
            return ActionOutput(content, instruct_content)
        except Exception as e:
            logger.error(f"Error in GOECSearch: {e}")
            raise

    def _parse_intents(self, content: str) -> List[Dict]:
        """
        Parse the content to extract intents and annotations.

        Args:
            content (str): The content to parse.

        Returns:
            List[Dict]: A list of intents, each containing annotations.
        """
        # Implement logic to parse the content and extract intents and annotations
        # For simplicity, assume content is already in the correct JSON format
        import json
        try:
            intents = json.loads(content)
            return intents
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing content: {e}")
            raise
