from typing import List, Tuple, Optional
from agents.actions import ActionOutput
from agents.system.logs import logger
from agents.actions.action import Action
import json

PROMPT_TEMPLATE = '''
-----
# System
You are an expert in the field of protein design and you have a thorough understanding of the biochemical terms associated with proteins and enzymes.

# Input
{content}

# Requirements
1. Verify the accuracy of the GO number and EC number based on the original intent, initial annotation, and validation definition (val_def).
2. Generate a report with the polished design intent, keywords, GO and EC numbers.

# Steps
1. Read the input information in the format of:
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
1.1 The intent of different groups is distinguished by "intent." The "intent" corresponds to the "name" in the message that the intentanalyser sends to the environment, ensuring a strict correspondence.
2. Read the "description" in the message sent by the intentanalyser in the environment, which is the user's design intent.
2.1 Take advantage of your expertise in protein design and biochemistry to determine if "val_def" accurately matches the meaning in "description".
2.2 Record whether val_def and description correspond to each number.
3. Generate validation reports as output.
3.1 The verification report needs to contain each initial design intention, that is, whether "description" and "val_def" of" number "corresponding to each design intention match the initial design intention. If no match is found, the verification report needs to indicate which" number "does not match. If a match is made, a more detailed design description is generated by combining the initial design intent and all "val_def" as well as knowledge of the protein design knowledge base and biochemistry. And list "number" separately.

# Format example
Your final output should ALWAYS in the following format:
{format_example}

# Attention:
1. "val_def" and the initial design intention do not require a strict match, do not be too rigid, make full use of protein design knowledge, understand the design intention," val_def" in the above and the design intention can be consistent.
2. Output format carefully referenced "Format example".

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
            "match": "Y"
        },
        {
            "number": "EC 3.1.1.74",
            "match": "Y"
        }
    ],
    "report": "There are terms that do not match the intent:EC 3.1.1.74,...",
    "design suggestion": "Re-query related terms.",
    "mismatched terms": [
        {
            "number": "EC 3.1.1.74",
            "content": "{the annotation in input}"
        }
    ]
},
{
    "intent": "intent_2",
    "annotations": [
        {
            "number": "GO:0016787",
            "match": "Y"
        },
        {
            "number": "EC 3.1.1.74",
            "match": "N"
        }
    ],
    "report": "There are terms that do not match the intent:EC 3.1.1.74,...",
    "design suggestion": "{Please generate a professional and complete protein design goal according to intention and "val_def" and protein design.}",
    "mismatched terms": [
        {
        }
    ]
}
-----
'''

OUTPUT_MAPPING = {
    "Intent List": (str, "JSON blob containing intent and annotations"),
}


class ProAnalysis(Action):
    name: str = "ProAnalysis"

    async def run(self, content: str, suggestions: Optional[str] = None) -> ActionOutput:
        try:
            logger.info("Starting ProAnalysis analysis...")
            logger.debug(f"Input content: {content}")

            # Format the prompt with the input content and format example
            if not content:
                raise ValueError("Input content is empty.")
            prompt = PROMPT_TEMPLATE.format(content=content, format_example=FORMAT_EXAMPLE, suggestions=suggestions or "")
            logger.debug(f"Generated prompt: {prompt}")

            # Call the LLM to analyze the content and generate the output
            logger.info("Calling LLM for analysis...")
            try:
                llm_response, instruct_content = await self._aask_v1(
                    prompt=prompt,
                    output_data_mapping=OUTPUT_MAPPING
                )
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                raise

            logger.debug(f"LLM response: {llm_response}")

            # Validate the LLM output
            try:
                parsed_output = json.loads(llm_response)
                if not isinstance(parsed_output, dict):
                    raise ValueError("LLM output is not a valid JSON object.")
                if "intent" not in parsed_output or "annotations" not in parsed_output:
                    raise ValueError("LLM output is missing required fields.")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON output from LLM: {e}")
                raise
            except ValueError as e:
                logger.error(f"Invalid output format from LLM: {e}")
                raise

            logger.info("ProAnalysis analysis completed successfully.")
            return ActionOutput(llm_response, instruct_content)
        except Exception as e:
            logger.error(f"Error in ProAnalysis: {e}")
            raise

