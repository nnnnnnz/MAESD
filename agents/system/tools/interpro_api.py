import requests
import json
from typing import List, Dict, Optional


class InterProSearcher:
    """封装 InterPro API 文本查询功能的工具类"""

    def __init__(self, api_endpoint: str = "https://www.ebi.ac.uk/interpro/api/search/text"):
        """
        初始化 InterPro 搜索工具

        :param api_endpoint: InterPro API 端点 URL
        """
        self.api_endpoint = api_endpoint
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def search(self, query: str, timeout: int = 10) -> Optional[List[Dict]]:
        """
        执行 InterPro 文本搜索

        :param query: 搜索文本
        :param timeout: 请求超时时间(秒)
        :return: 搜索结果列表，每个结果是一个字典；如果出错返回None
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
        规范化 API 返回的原始结果

        :param raw_results: API 返回的原始结果
        :return: 规范化后的结果列表
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


# 使用示例
if __name__ == "__main__":
    searcher = InterProSearcher()

    # 示例搜索
    print("Searching InterPro for 'kinase'...")
    results = searcher.search("kinase")

    if results:
        print(f"Found {len(results)} results:")
        for i, result in enumerate(results[:3], 1):  # 只显示前3个结果
            print(f"\nResult {i}:")
            print(f"Accession: {result['accession']}")
            print(f"Name: {result['name']}")
            print(f"Type: {result['type']}")
            print(f"Description: {result['description'][:100]}...")  # 截断长描述
            print(f"Score: {result['score']}")
    else:
        print("No results found or error occurred.")
