# go_api.py
import requests


def get_go_definition(go_id):
    """通过QuickGO API查询GO术语定义"""
    url = f"https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/{go_id}"
    try:
        response = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
        response.raise_for_status()  # 自动处理4xx/5xx错误

        data = response.json()
        if not data.get("results"):
            return None, "GO term not found"

        term = data["results"][0]

        # 提取同义词（Synonyms）
        synonyms = []
        for synonym in term.get("synonyms", []):
            if "name" in synonym:
                synonyms.append(synonym["name"])

        return {
            "id": term["id"],
            "name": term["name"],
            "definition": term["definition"]["text"],
            "ontology": term["aspect"],
            "synonyms": synonyms  # 新增同义词字段
        }, None

    except requests.exceptions.RequestException as e:
        return None, f"Network error: {str(e)}"
    except (KeyError, IndexError, ValueError) as e:
        return None, f"Data parsing error: {str(e)}"


def search_go_by_definition(query, max_results=5):
    """通过定义文本模糊搜索GO术语"""
    url = "https://www.ebi.ac.uk/QuickGO/services/ontology/go/search"
    params = {
        "query": f'definition:"{query}"',  # 在定义字段中搜索
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
        return [], f"Network error: {str(e)}"
    except (KeyError, ValueError) as e:
        return [], f"Data parsing error: {str(e)}"
