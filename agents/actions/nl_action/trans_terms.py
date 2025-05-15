from typing import List, Tuple, Dict, Optional
from agents.actions import ActionOutput
from agents.system.logs import logger
from agents.actions.action import Action
from agents.system.tools.go_api import search_go_by_definition


# Prompt Template
PROMPT_TEMPLATE = '''
-----
# System
You are a professional expert in Gene Ontology (GO) and Enzyme Commission (EC) Number knowledge. Your goal is to analyze the input text and map the provided biological terms to relevant GO or EC numbers, ensuring the output is organized by intent and includes accurate annotations.

# Input
{content}

# Requirements
1. Analyze the given text to understand its core intent and the associated biological terms.
2. Map each biological term to relevant GO or EC numbers based on their biological or enzymatic functions.
3. Provide concise and accurate annotations for each GO or EC number.
4. Ensure the results are grouped by intent and maintain clear distinctions between different intents.

# Steps
By following these steps, you will be able to map biological terms to GO or EC numbers accurately:
1. The first thing you should understand is that you're getting content from humans.
1.1 Read, analyze, and understand this text carefully. Identify the core intent and the associated biological terms.
2. For each intent, analyze the biological terms provided and map them to relevant GO or EC numbers.
2.1 Use your knowledge of GO and EC classifications to ensure the mappings are accurate and relevant.
2.2 Provide concise and professional annotations for each GO or EC number, explaining its relevance to the intent.
3. Group the results by intent, ensuring terms from different intents are not mixed.
3.1 Output the results in JSON format, with each intent as a separate JSON blob. Each JSON blob should contain a "number" key (GO or EC number) and an "annotation" key (the corresponding explanation).
3.2 Ensure the output is structured and easy to understand, with clear distinctions between intents.
4. Output Format Example:
Here’s an example of the expected output format for each intent:

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
4.1 Each JSON blob should correspond to one intent only.The "intent" field is just a intent_number.
4.2 Ensure the annotations are accurate and directly related to the terms in the intent.

# Format example
Your final output should ALWAYS in the following format:
{format_example}

# Suggestions
{suggestions}

# Attention:
1. Ensure the analysis captures the core intent accurately and maps terms to relevant GO or EC numbers.
2. Maintain clear distinctions between different intents in the output.
3. The output should be structured, professional, and easy to understand.
4. Use '##' to SPLIT SECTIONS, not '#'. Output format carefully referenced "Format example".
-----
'''

FORMAT_EXAMPLE = '''
## Intent List
JSON BLOB 1,
JSON BLOB 2,
JSON BLOB 3
'''

OUTPUT_MAPPING = {
    "Intent List": (str, "List of JSON blobs grouped by intent"),
}


class TransTerms(Action):
    name: str = "TransTerms"

    async def run(self, content: str, suggestions: Optional[str] = None) -> ActionOutput:
        """
        Analyze the input content, map biological terms to GO or EC numbers, and return structured results.

        Args:
            content (str): Input text containing biological terms and intents.
            suggestions (Optional[str]): Additional suggestions for the analysis.

        Returns:
            ActionOutput: Structured output containing the mapped GO/EC numbers and annotations.
        """
        try:
            # Format the prompt with the input content and format example
            prompt = PROMPT_TEMPLATE.format(content=content, format_example=FORMAT_EXAMPLE, suggestions=suggestions or "")

            # Call the LLM to analyze the content and generate the output
            content, instruct_content = await self._aask_v1(
                prompt=prompt,
                output_data_mapping=OUTPUT_MAPPING
            )

            # Return the result as an ActionOutput
            return ActionOutput(content, instruct_content)
        except Exception as e:
            logger.error(f"Error in TransTerms: {e}")
            raise
