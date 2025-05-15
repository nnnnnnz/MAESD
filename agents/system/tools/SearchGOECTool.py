import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote_plus
from typing import Dict, Optional, Tuple, List
from agents.system.logs import logger

class SearchGOECTool:
    """
    整合 GO 和 EC 编号查询的工具类，提供以下功能：
    1. 从 GO 编号获取注释
    2. 从注释获取 GO 编号
    3. 从 EC 编号获取注释
    4. 从注释获取 EC 编号
    """

    def __init__(self):
        # 可以在这里初始化任何需要的配置
        pass

    def normalize_ec_number(self, ec_number: str) -> str:
        """标准化 EC 编号格式"""
        return re.sub(r'^\s*(EC|ec)\s*', '', ec_number, flags=re.IGNORECASE).strip()

    def validate_ec_number(self, ec_number: str) -> bool:
        """验证 EC 编号格式"""
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
        """通过 QuickGO API 查询 GO 术语定义"""
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
            logger.error(f"GO查询网络错误: {str(e)}")
            return None, f"Network error: {str(e)}"
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"GO数据解析错误: {str(e)}")
            return None, f"Data parsing error: {str(e)}"

    def search_go_by_definition(self, query: str, max_results: int = 5) -> Tuple[List[Dict], Optional[str]]:
        """通过定义文本模糊搜索 GO 术语"""
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
            logger.error(f"GO搜索网络错误: {str(e)}")
            return [], f"Network error: {str(e)}"
        except (KeyError, ValueError) as e:
            logger.error(f"GO搜索数据解析错误: {str(e)}")
            return [], f"Data parsing error: {str(e)}"

    def get_ec_info(self, ec_number: str) -> Tuple[Optional[Dict], Optional[str]]:
        """查询 EC 编号信息"""
        ec_number = self.normalize_ec_number(ec_number)
        url = f"https://enzyme.expasy.org/EC/{ec_number}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            if "No such enzyme" in response.text:
                return None, "EC编号不存在"

            soup = BeautifulSoup(response.text, 'html.parser')

            # 处理通配符查询
            if '-' in ec_number:
                target_link = soup.find('a', href=ec_number)
                if not target_link:
                    return None, f"未找到{ec_number}的分类定义"
                definition = target_link.next_sibling.strip().lstrip(':').strip()
                return {"ec_number": ec_number, "definition": definition}, None

            # 处理具体编号的详细解析
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
            logger.error(f"EC查询网络错误: {str(e)}")
            return None, f"Network error: {str(e)}"
        except Exception as e:
            logger.error(f"EC数据解析错误: {str(e)}")
            return None, f"Parsing error: {str(e)}"

    def search_ec_by_annotation(self, keyword: str) -> List[Dict]:
        """通过注解模糊搜索 EC 编号"""
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
            logger.error(f"EC搜索网络错误: {str(e)}")
            return [{"error": f"API request failed: {str(e)}"}]
        except Exception as e:
            logger.error(f"EC搜索错误: {str(e)}")
            return [{"error": f"Error occurred: {str(e)}"}]
