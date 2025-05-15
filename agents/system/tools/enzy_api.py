# enzy_api.py
import requests
from bs4 import BeautifulSoup
import re  # 添加缺失的re模块导入
from urllib.parse import quote_plus
import re


def normalize_ec_number(ec_number):
    return re.sub(r'^\s*(EC|ec)\s*','',ec_number, flags=re.IGNORECASE).strip()

def get_ec_info(ec_number):
    """精确处理EC编号查询的最终方案"""
    ec_number = normalize_ec_number(ec_number)
    # 保持原始EC编号格式（关键修正）
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

        # 处理具体编号的详细解析（根据实际HTML结构调整）
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
                # 处理多行名称的情况
                accepted_td = accepted_th.find_next('td')
                if accepted_td:
                    info['accepted_name'] = accepted_td.get_text(' ', strip=True)
                    # 清除换行符
                    info['accepted_name'] = info['accepted_name'].replace('\n', ' ')

            # === Alternative Names ===
            if alt_th := main_table.find('th', string='Alternative Name(s)'):
                # 可能包含多个<strong>标签
                alt_td = alt_th.find_next('td')
                if alt_td:
                    info['alternative_names'] = [
                        strong.get_text(strip=True)
                        for strong in alt_td.find_all('strong')
                    ]

            # === Reaction Catalysed ===
            if react_th := main_table.find('th', string='Reaction catalysed'):
                react_td = react_th.find_next('td')
                if react_td:
                    # 处理两种情况：带有<ul>列表和直接文本
                    if ul := react_td.find('ul', class_='ca'):
                        # 带列表的情况（如1.1.1.1）
                        info['reaction'] = [
                            li.get_text(' ', strip=True)
                            .replace('\n', ' ')
                            for li in ul.find_all('li')
                        ]
                    else:
                        # 直接文本的情况（如1.2.3.4）
                        reaction_text = react_td.get_text(' ', strip=True)
                        # 清理颜色标记
                        reaction_text = re.sub(r'<span.*?span>', '', reaction_text)
                        info['reaction'] = [reaction_text]

            # === Comments ===
            if comment_th := main_table.find('th', string='Comment(s)'):
                comment_td = comment_th.find_next('td')
                if comment_td:
                    # 处理带列表和直接文本的情况
                    if ul := comment_td.find('ul', class_='cc'):
                        info['comments'] = [
                            li.get_text(' ', strip=True)
                            .replace('\n', ' ')
                            for li in ul.find_all('li')
                        ]
                    else:
                        comment_text = comment_td.get_text(' ', strip=True)
                        info['comments'] = [comment_text]

        return info, None

    except requests.exceptions.RequestException as e:
        return None, f"网络错误: {str(e)}"
    except Exception as e:
        return None, f"解析错误: {str(e)}"


import re


def validate_ec_number(ec_number):
    """支持 EC/ec 前缀，并严格验证层级关系的验证函数"""
    # 预处理：去除前缀和空格
    clean_ec = re.sub(r'^\s*(EC|ec)\s*', '', ec_number, flags=re.IGNORECASE)

    # 验证基本格式
    if not re.match(r'^([\dx-]+\.){3}[\dx-]+$', clean_ec):
        return False

    parts = clean_ec.split('.')

    # 严格验证层级关系
    for i in range(len(parts)):
        part = parts[i]

        # 检查当前部分的合法性
        if not re.match(r'^[\dx-]+$', part):  # 允许多位数字
            return False

        # 如果当前部分为通配符（x 或 -），后续部分必须也为通配符
        if part in ('x', '-'):
            for j in range(i + 1, len(parts)):
                if parts[j] not in ('x', '-'):
                    return False
            break  # 后续部分已确保为通配符

    return True


def search_ec_by_annotation(keyword):
    """Search EC numbers by annotation with fuzzy matching"""
    base_url = "http://rest.kegg.jp/find/enzyme/"

    try:
        # 对关键词进行URL编码并发送请求
        response = requests.get(f"{base_url}{quote_plus(keyword)}", timeout=10)
        response.raise_for_status()  # 自动检测HTTP错误状态码

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
                    continue  # 跳过格式不符的行

        return results or ["No corresponding EC number found"]

    except requests.exceptions.RequestException as e:
        return [f"API request failed: {str(e)}"]
    except Exception as e:
        return [f"Error occurred: {str(e)}"]