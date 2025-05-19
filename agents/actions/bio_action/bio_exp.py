from typing import List, Dict, Optional
from agents.actions import ActionOutput
from agents.system.logs import logger
from agents.actions.action import Action

INTEGRATION_PROMPT_TEMPLATE = '''
-----
# System
You are an expert biological systems analyst. Your task is to integrate and analyze inputs from multiple specialized agents to produce comprehensive protein design recommendations.

# Input Sources
1. GO/EC Validator: {goec_validator_output}
2. Intent Analyzer: {intent_analyser_output}
3. Protein Property Analyzer: {pro_analysiser_output} 
4. Terminology Translator: {term_translator_output}

# Requirements
1. Cross-validate all inputs for consistency and accuracy
2. Identify any discrepancies between different agent outputs
3. Resolve conflicts by:
   3.1 Determining the most reliable source
   3.2 Consulting domain knowledge
   3.3 Flagging unresolved issues for human review
4. Generate unified recommendations that incorporate:
   4.1 Validated biological terms (GO/EC)
   4.2 Design intent specifications
   4.3 Protein property analyses
   4.4 Standardized terminology

# Steps
1. Compare GO/EC validation results with intent analysis
2. Verify property analysis aligns with validated terms
3. Check terminology consistency across all inputs
4. Resolve conflicts through priority rules:
   4.1 Experimental data > Computational predictions
   4.2 Validated terms > Unverified terms
   4.3 Domain consensus > Individual annotations
5. Generate final output containing:
   5.1 Unified validated terms
   5.2 Conflict resolution report
   5.3 Design implementation plan
   5.4 Open questions requiring further research

# Output Format
{format_example}

# Attention:
1. Maintain traceability to all source inputs
2. Document all conflict resolution decisions
3. Provide scientific justification for recommendations
4. Flag any remaining uncertainties
-----
'''

FORMAT_EXAMPLE = '''
## Integrated Analysis Report
{
    "validated_components": {
        "go_terms": ["GO:0016787", "GO:0005198"],
        "ec_numbers": ["EC 3.1.1.75"],
        "design_intent": "Optimize PETase for high-temperature stability",
        "key_properties": {
            "thermostability": "Target ≥70°C",
            "activity": "Maintain ≥80% of wild-type"
        }
    },
    "conflict_resolution": [
        {
            "issue": "Discrepancy in optimal pH range",
            "resolution": "Adjusted to pH 6.0-8.0 based on experimental data",
            "sources": ["PropertyAnalyzer", "TermTranslator"]
        }
    ],
    "design_recommendations": [
        "Introduce disulfide bonds at positions A101-B202",
        "Optimize surface charge distribution for pH stability",
        "Include N-terminal His-tag for purification"
    ],
    "research_questions": [
        "Effect of glycosylation on thermostability",
        "Optimal expression system for this variant"
    ]
}
'''

OUTPUT_MAPPING = {
    "Integrated Report": (Dict, "Contains all validated components and recommendations"),
    "Conflict Log": (List[Dict], "Documents all resolved discrepancies"),
    "Design Suggestions": (List[str], "Actionable implementation steps"),
    "Open Questions": (List[str], "Areas requiring further investigation")
}

class IntegratedAnalysisAction(Action):
    def __init__(self):
        super().__init__()
        self.desc = "Integrates outputs from multiple validation agents to produce unified protein design recommendations"

    async def run(self, 
                 goec_validator_output: Dict,
                 intent_analyser_output: Dict,
                 pro_analysiser_output: Dict,
                 term_translator_output: Dict) -> ActionOutput:
        """Execute the integrated analysis workflow"""
        
        prompt = INTEGRATION_PROMPT_TEMPLATE.format(
            goec_validator_output=goec_validator_output,
            intent_analyser_output=intent_analyser_output,
            pro_analysiser_output=pro_analysiser_output,
            term_translator_output=term_translator_output,
            format_example=FORMAT_EXAMPLE
        )

        try:
            # Call LLM with the integration prompt
            resp = await self._aask(prompt)
            
            # Parse and validate response
            validated_data = self._validate_output(resp)
            
            return ActionOutput(
                content=validated_data,
                instruct_content=self._create_instruct_content(validated_data)
            )
            
        except Exception as e:
            logger.error(f"Integration failed: {str(e)}")
            raise

    def _validate_output(self, raw_output: str) -> Dict:
        """Validate and parse the LLM output"""
        # Implementation would include:
        # 1. Schema validation
        # 2. Cross-check with source inputs
        # 3. Logical consistency checks
        return parsed_data

    def _create_instruct_content(self, data: Dict) -> Dict:
        """Create structured output for downstream use"""
        return {
            "analysis_summary": data.get("validated_components"),
            "design_actions": data.get("design_recommendations"),
            "validation_report": {
                "resolved_issues": data.get("conflict_resolution"),
                "remaining_questions": data.get("research_questions")
            }
        }
