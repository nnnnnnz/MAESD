from typing import List, Dict, Optional
from agents.actions import ActionOutput
from agents.system.logs import logger
from agents.actions.action import Action
from agents.system.tools.interpro_api import search_domains_by_protein

# Prompt Template
PROMPT_TEMPLATE = '''
-----
# System
You are an expert at identifying protein domains from natural language descriptions and calling the InterPro API to verify domain information.

# Input
{content}

# Requirements
1. Analyze the natural language description to identify potential protein domains.
2. For each identified domain, use the search_domains_by_protein tool to verify its existence and get details.
3. Add validation results to the output with specific fields: 
   - Store domain name, accession, and description from API response
   - Include source database (InterPro, Pfam, etc.)
   - Add confidence score if available

# Steps
1. Read protein description in the following format:
{
    "protein_id": "P12345",
    "description": "Serine protease with trypsin-like domain and EGF-like repeats"
}

2. For each protein description:
   2.1 Extract domain candidates from the description
   2.2 Call search_domains_by_protein for each candidate
   2.3 Validate domain existence and properties
   2.4 Store results in structured format

3. Handle different cases:
   - Exact matches: Use directly from API
   - Partial matches: Include with confidence score
   - No matches: Flag for manual review

# Format example
Your final output should ALWAYS be in the following format:
{format_example}

# Attention:
1. Ensure domain names match standard nomenclature
2. Verify domain boundaries with protein sequence
3. Include all supporting evidence
4. Document any discrepancies
-----
'''

FORMAT_EXAMPLE = '''
-----
## Domain Analysis Report
{
    "protein_id": "P12345",
    "validated_domains": [
        {
            "name": "Trypsin",
            "accession": "IPR001254",
            "source": "InterPro",
            "description": "Serine protease, trypsin domain",
            "start": 56,
            "end": 251,
            "confidence": 0.98
        },
        {
            "name": "EGF-like",
            "accession": "IPR000742",
            "source": "InterPro",
            "description": "EGF-like domain",
            "start": 300,
            "end": 340,
            "confidence": 0.85
        }
    ],
    "unverified_terms": [
        {
            "term": "Catalytic triad",
            "reason": "Not found as standalone domain"
        }
    ]
}
-----
'''

OUTPUT_MAPPING = {
    "Domain Report": (Dict, "Contains validated domains and analysis results"),
    "Unverified Terms": (List[Dict], "Terms that couldn't be verified automatically")
}


class ProteinDomainSearch(Action):
    name: str = "ProteinDomainSearch"

    async def search_protein_domains(self, protein_id: str, domain_name: str) -> Dict:
        """
        Search for protein domains using InterPro API
        
        Args:
            protein_id: UniProt protein accession
            domain_name: Domain name or keyword to search
            
        Returns:
            Dictionary containing domain information or error
        """
        try:
            results = await search_domains_by_protein(protein_id, domain_name)
            if not results:
                return {"error": f"No domains found matching {domain_name}"}
            return results[0]  # Return best match
        except Exception as e:
            logger.error(f"Error searching domains for {protein_id}: {e}")
            return {"error": str(e)}

    async def run(self, content: Dict) -> ActionOutput:
        """
        Analyze protein description and validate domains using InterPro
        
        Args:
            content: Dictionary containing protein_id and description
            
        Returns:
            ActionOutput with validated domain information
        """
        try:
            prompt = PROMPT_TEMPLATE.format(
                content=content,
                format_example=FORMAT_EXAMPLE
            )

            # First pass - extract domain candidates from description
            analysis, instruct_content = await self._aask_v1(
                prompt=prompt,
                output_data_mapping=OUTPUT_MAPPING
            )

            # Second pass - validate each candidate domain
            protein_id = content.get("protein_id")
            description = content.get("description", "")
            
            validated_domains = []
            unverified_terms = []

            # This would be more sophisticated in practice
            domain_candidates = self._extract_domain_candidates(description)
            
            for domain in domain_candidates:
                result = await self.search_protein_domains(protein_id, domain)
                if "error" not in result:
                    validated_domains.append(result)
                else:
                    unverified_terms.append({
                        "term": domain,
                        "reason": result["error"]
                    })

            output = {
                "protein_id": protein_id,
                "validated_domains": validated_domains,
                "unverified_terms": unverified_terms
            }

            return ActionOutput(output, instruct_content)
            
        except Exception as e:
            logger.error(f"Error in ProteinDomainSearch: {e}")
            raise

    def _extract_domain_candidates(self, description: str) -> List[str]:
        """
        Extract potential domain names from protein description
        
        Args:
            description: Natural language protein description
            
        Returns:
            List of candidate domain names
        """
        # This is a simplified version - would use more sophisticated NLP in practice
        keywords = ["domain", "repeat", "motif", "region"]
        candidates = []
        
        # Split description and look for domain indicators
        for word in description.split():
