from typing import List, Dict, Optional
from agents.actions import ActionOutput
from agents.system.logs import logger
from agents.actions.action import Action

PROMPT_TEMPLATE = '''
-----
-----
# System
You are a professional expert in protein design and biological term validation. Your goal is to analyze the input intent list, identify mismatched terms, and provide appropriate actions based on the analysis.

# Input
{content}

# Requirements
1. Analyze each intent in the input to identify mismatched terms.
2. If there are mismatched terms, perform the following steps:
   2.1 Re-query related terms for each mismatched term.
   2.2 Call the appropriate tool to validate the new terms.
   2.3 Update the intent list with the validated terms.
3. If there are no mismatched terms, generate a detailed design suggestion based on the intent and annotations.

# Steps
By following these steps, you will be able to process the input and generate the correct output:
1. Read the input intent list carefully.
2. For each intent, check the "match" field in each annotation.
   2.1 If any annotation has "match": "N", it indicates a mismatched term.
3. If mismatched terms are found:
   3.1 For each mismatched term, re-query related terms using your knowledge and available tools.
   3.2 Validate the new terms by calling the appropriate tool (e.g., GO or EC validation tools).
   3.3 Update the intent list with the validated terms and their annotations.
4. If no mismatched terms are found:
   4.1 Generate a detailed design suggestion based on the intent and annotations.
   4.2 Ensure the design suggestion is professional, complete, and aligned with the initial design intent.
5. Output the final result in the following format:
   - If mismatched terms are found, output the updated intent list with validated terms.
   - If no mismatched terms are found, output the design suggestion.

# Format example
Your final output should ALWAYS in the following format:
{format_example}

# Attention:
1. Ensure the analysis is accurate and thorough.
2. Use professional terminology and knowledge in protein design.
3. Output format carefully referenced "Format example".
-----
'''

FORMAT_EXAMPLE = '''
## Inten List
If exit mismatched terms in a intent:
{
    "intent": "intent_1",
    "annotations": [
        {
            "number": "GO:0016787",
            "match": "Y"
        },
        {
            "number": "GO:0005198",
            "match": "Y"
        },
        {
            "number": "EC 3.1.1.75",
            "match": "Y",
            "annotation": "Poly(ethylene terephthalate) hydrolase (PETase); optimized for high catalytic activity."
        }
    ],
    "report": "The mismatched term (EC 3.1.1.74) has been replaced with EC 3.1.1.75.",
    "design suggestion": "The initial design intent is to create a plastic-degrading enzyme with high catalytic activity and structural stability to function effectively in extreme conditions such as high temperature. The GO terms (GO:0016787 and GO:0005198) align well with the intent, focusing on hydrolase activity and structural stability. The updated EC term (EC 3.1.1.75) now better matches the intended enzyme's function and specificity."
}

If not exit mismatched terms in a intent:
{
    "design suggestion": "The initial design intent is to optimize the enzyme to maintain functionality in high-salt environments, ensuring its activity is not inhibited by elevated salt concentrations. The GO terms (GO:0003824 and GO:0006950) and the EC term (EC 3.2.1.1) align well with the intent, focusing on catalytic activity and stress response in high-salt environments. The enzyme design should prioritize enhancing salt tolerance while maintaining catalytic efficiency. Consider incorporating structural features that stabilize the enzyme in high-salt conditions, such as optimizing surface charge distribution and enhancing hydrophobic interactions."
}
'''

OUTPUT_MAPPING = {
    "Intent List": (str, "Updated intent list or design suggestion"),
}