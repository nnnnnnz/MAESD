import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote_plus
from typing import Dict, Optional, Tuple, List
from agents.system.logs import logger

class SearchGOECTool:
    """
    A tool class integrating GO and EC number queries, providing the following functionalities:
    1. Get annotation from GO ID
    2. Get GO IDs from annotation
    3. Get annotation from EC number
    4. Get EC numbers from annotation
    """

    def __init__(self):
        # Initialize any required configurations here
        pass

    def normalize_ec_number(self, ec_number: str) -> str:
        """Standardize EC number format"""
        return re.sub(r'^\s*(EC|ec)\s*', '', ec_number, flags=re.IGNORECASE).strip()

    def validate_ec_number(self, ec_number: str) -> bool:
        """Validate EC number format"""
        clean_ec = self.normalize_ec_number(ec_number)
        if not re.match(r'^([\dx-]+\.){3}[\dx-]+$', clean_ec):
            return False
        parts = clean_ec.split('.')
        for i in range(len(parts)):
            part = parts[i]
            if not re.match(r'^[\dx-]+$', part):
                return False
            if part in ('x', '-'):
                for j in range(i + 1, len(parts)):
                    if parts[j] not in ('x', '-'):
                        return False
                break
        return True

    def get_go_definition(self, go_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Query GO term definition using QuickGO API"""
        url = f"https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/{go_id}"
        try:
            response = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
            response.raise_for_status()

            data = response.json()
            if not data.get("results"):
                return None, "GO term not found"

            term = data["results"][0]
            synonyms = [synonym["name"] for synonym in term.get("synonyms", []) if "name" in synonym]

            return {
                "id": term["id"],
                "name": term["name"],
                "definition": term["definition"]["text"],
                "ontology": term["aspect"],
                "synonyms": synonyms
            }, None

        except requests.exceptions.RequestException as e:
            logger.error(f"GO query network error: {str(e)}")
            return None, f"Network error: {str(e)}"
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"GO data parsing error: {str(e)}")
            return None, f"Data parsing error: {str(e)}"

    def search_go_by_definition(self, query: str, max_results: int = 5) -> Tuple[List[Dict], Optional[str]]:
        """Fuzzy search GO terms by definition text"""
        url = "https://www.ebi.ac.uk/QuickGO/services/ontology/go/search"
        params = {
            "query": f'definition:"{query}"',
            "limit": max_results,
            "page": 1
        }

        try:
            response = requests.get(url, params=params, headers={"Accept": "application/json"}, timeout=10)
            response.raise_for_status()

            data = response.json()
            results = []
            for term in data.get("results", []):
                results.append({
                    "id": term["id"],
                    "name": term["name"],
                    "definition": term.get("definition", {}).get("text", "")
                })
            return results, None

        except requests.exceptions.RequestException as e:
            logger.error(f"GO search network error: {str(e)}")
            return [], f"Network error: {str(e)}"
        except (KeyError, ValueError) as e:
            logger.error(f"GO search data parsing error: {str(e)}")
            return [], f"Data parsing error: {str(e)}"

    def get_ec_info(self, ec_number: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Query EC number information"""
        ec_number = self.normalize_ec_number(ec_number)
        url = f"https://enzyme.expasy.org/EC/{ec_number}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            if "No such enzyme" in response.text:
                return None, "EC number does not exist"

            soup = BeautifulSoup(response.text, 'html.parser')

            # Handle wildcard queries
            if '-' in ec_number:
                target_link = soup.find('a', href=ec_number)
                if not target_link:
                    return None, f"Classification definition not found for {ec_number}"
                definition = target_link.next_sibling.strip().lstrip(':').strip()
                return {"ec_number": ec_number, "definition": definition}, None

            # Process detailed parsing for specific numbers
            info = {
                "ec_number": ec_number,
                "accepted_name": "N/A",
                "alternative_names": [],
                "reaction": [],
                "comments": []
            }

            main_table = soup.find('table', class_='type-1')
            if main_table:
                # === Accepted Name ===
                if accepted_th := main_table.find('th', string='Accepted Name'):
                    accepted_td = accepted_th.find_next('td')
                    if accepted_td:
                        info['accepted_name'] = accepted_td.get_text(' ', strip=True).replace('\n', ' ')

                # === Alternative Names ===
                if alt_th := main_table.find('th', string='Alternative Name(s)'):
                    alt_td = alt_th.find_next('td')
                    if alt_td:
                        info['alternative_names'] = [
                            strong.get_text(strip=True) for strong in alt_td.find_all('strong')
                        ]

                # === Reaction Catalysed ===
                if react_th := main_table.find('th', string='Reaction catalysed'):
                    react_td = react_th.find_next('td')
                    if react_td:
                        if ul := react_td.find('ul', class_='ca'):
                            info['reaction'] = [
                                li.get_text(' ', strip=True).replace('\n', ' ') for li in ul.find_all('li')
                            ]
                        else:
                            reaction_text = react_td.get_text(' ', strip=True)
                            reaction_text = re.sub(r'<span.*?span>', '', reaction_text)
                            info['reaction'] = [reaction_text]

                # === Comments ===
                if comment_th := main_table.find('th', string='Comment(s)'):
                    comment_td = comment_th.find_next('td')
                    if comment_td:
                        if ul := comment_td.find('ul', class_='cc'):
                            info['comments'] = [
                                li.get_text(' ', strip=True).replace('\n', ' ') for li in ul.find_all('li')
                            ]
                        else:
                            comment_text = comment_td.get_text(' ', strip=True)
                            info['comments'] = [comment_text]

            return info, None

        except requests.exceptions.RequestException as e:
            logger.error(f"EC query network error: {str(e)}")
            return None, f"Network error: {str(e)}"
        except Exception as e:
            logger.error(f"EC data parsing error: {str(e)}")
            return None, f"Parsing error: {str(e)}"

    def search_ec_by_annotation(self, keyword: str) -> List[Dict]:
        """Fuzzy search EC numbers by annotation"""
        base_url = "http://rest.kegg.jp/find/enzyme/"
        try:
            response = requests.get(f"{base_url}{quote_plus(keyword)}", timeout=10)
            response.raise_for_status()

            results = []
            for line in response.text.split('\n'):
                if line.strip():
                    try:
                        ec_id, description = line.split('\t', 1)
                        results.append({
                            "EC_Number": ec_id.replace("ec:", "").strip(),
                            "Description": description.strip()
                        })
                    except ValueError:
                        continue

            return results or [{"error": "No corresponding EC number found"}]

        except requests.exceptions.RequestException as e:
            logger.error(f"EC search network error: {str(e)}")
            return [{"error": f"API request failed: {str(e)}"}]
        except Exception as e:
            logger.error(f"EC search error: {str(e)}")
            return [{"error": f"Error occurred: {str(e)}"}]
