import requests
import json
from typing import List, Dict, Optional


class InterProSearcher:
    """A tool class that encapsulates InterPro API text search functionality"""

    def __init__(self, api_endpoint: str = "https://www.ebi.ac.uk/interpro/api/search/text"):
        """
        Initialize the InterPro search tool
        
        :param api_endpoint: InterPro API endpoint URL
        """
        self.api_endpoint = api_endpoint
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def search(self, query: str, timeout: int = 10) -> Optional[List[Dict]]:
        """
        Execute InterPro text search
        
        :param query: Search text
        :param timeout: Request timeout in seconds
        :return: List of search results (each result is a dict), returns None if error occurs
        """
        try:
            payload = json.dumps({"query": query})
            response = requests.post(
                self.api_endpoint,
                headers=self.headers,
                data=payload,
                timeout=timeout
            )

            if response.status_code != 200:
                print(f"API request failed with status code: {response.status_code}")
                print(f"Response: {response.text}")
                return None

            data = response.json()
            return self._normalize_results(data.get('results', []))

        except requests.exceptions.RequestException as e:
            print(f"Error making request to InterPro API: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error parsing API response: {str(e)}")
            return None

    def _normalize_results(self, raw_results: List[Dict]) -> List[Dict]:
        """
        Normalize raw results returned from API
        
        :param raw_results: Raw results from API
        :return: List of normalized results
        """
        normalized = []

        for item in raw_results:
            metadata = item.get('metadata', {})
            extra_fields = item.get('extra_fields', {})

            result = {
                'accession': metadata.get('accession'),
                'name': metadata.get('name'),
                'type': metadata.get('type'),
                'description': metadata.get('description'),
                'go_terms': metadata.get('go_terms', []),
                'score': extra_fields.get('score')
            }

            normalized.append(result)

        return normalized


# Example usage
if __name__ == "__main__":
    searcher = InterProSearcher()

    # Example search
    print("Searching InterPro for 'kinase'...")
    results = searcher.search("kinase")

    if results:
        print(f"Found {len(results)} results:")
        for i, result in enumerate(results[:3], 1):  # Only show first 3 results
            print(f"\nResult {i}:")
            print(f"Accession: {result['accession']}")
            print(f"Name: {result['name']}")
            print(f"Type: {result['type']}")
            print(f"Description: {result['description'][:100]}...")  # Truncate long description
            print(f"Score: {result['score']}")
    else:
        print("No results found or error occurred.")
