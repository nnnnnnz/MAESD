from typing import List, Tuple
from agents.actions import ActionOutput
from agents.system.logs import logger
from agents.actions.action import Action

PROMPT_TEMPLATE = '''
-----
# System
You are a professional protein design intent analysis expert and your goal is to analyze the intent of input text according to the following steps.

# User input
{content}

# Requirements: 
1. Analyze the given text about protein design to understand its core intent.
2. Use divergent thinking to extract multiple potential focus areas based on the core intent.

# Step
By following these steps, you will be able to parse the intent of any protein design text:
1. The first thing you should understand is that you're getting content from humans.
1.1 Read, analyze, and understand this text carefully. Summarize his core ideas or intentions, call it core intent.
2. You need to understand, analyze, and break down the possible design goals of this protein design text from a professional perspective. For example, optimization of thermal stability, optimization of activity in acidic/alkaline/high salt environments, realization of one or more specific functions, optimization of reaction efficiency, etc.
2.1 Take full advantage of all aspects of natural language processing capabilities. Understand the content of the text from different angles.
2.2 Convert different angles into possible design intentions for users. And keep three or fewer intentions that are closest to the original text.
2.3 Design intentions from different angles are each composed into a smooth and smooth text.
2.4 Making full use of the knowledge base, the colloquial and general content in the text content is transformed into specialized biological terms.
3. The complete design intention text containing professional terms is denoted as intent_1, intent_2 and intent_3 respectively. The biological terms contained in these three intentions are denoted as term _1_1, term _1_2... ; Term _2_1. Term _2_2... ; Term _3_1, term _3_2,,,
3.1 You have to output each intent and its corresponding terms in json format.Specifically, an intent JSON file should have a "name" key (e.g., intent_1), a "description" key (the content of the intent), and a "terms" key (biological terms). Each JSON blob should contain only one design intent, and do not return a list of multiple design intents. Here's an example of a valid JSON blob:
{{
    "name": "Intent Number",
    "description": "Intent Content",
    "terms": "term_1,term_2,term_3"
}}
3.2 Intents and terms must correspond strictly, and terms that do not exist in the content of the intent must not be allowed.

# Format example
Your final output should ALWAYS in the following format:
{format_example}

# Suggestions
{suggestions}

# Attention: 
1. Ensure the analysis captures the core intent accurately.
2. Maintain divergent thinking to explore various possible focus areas.
3. The output should be structured and easy to understand.
4. Use '##' to SPLIT SECTIONS, not '#'. Output format carefully referenced "Format example".
-----
'''

FORMAT_EXAMPLE = '''
---
## Intent List

JSON BLOB 1,
JSON BLOB 2,
JSON BLOB 3

---
'''

OUTPUT_MAPPING = {
    "Intent List": (str, "JSON blob containing intent and terms"),
}


class IntentAnalyse(Action):
    name: str = "IntentAnalyse"

    async def run(self, content):
        prompt = PROMPT_TEMPLATE.format(content=content, format_example=FORMAT_EXAMPLE)
        try:
            content, instruct_content = await self._aask_v1(prompt=prompt, output_data_mapping=OUTPUT_MAPPING)
            return ActionOutput(content, instruct_content)
        except Exception as e:
            logger.error(f"Error in IntentAnalyse: {e}")
            raise
