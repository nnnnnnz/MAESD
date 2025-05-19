# enzy_api.py
import requests
from bs4 import BeautifulSoup
import re  
from urllib.parse import quote_plus
import re


def normalize_ec_number(ec_number):
    return re.sub(r'^\s*(EC|ec)\s*','',ec_number, flags=re.IGNORECASE).strip()

def get_ec_info(ec_number):
    ec_number = normalize_ec_number(ec_number)

    url = f"https://enzyme.expasy.org/EC/{ec_number}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        if "No such enzyme" in response.text:
            return None, "EC number does not exist"

        soup = BeautifulSoup(response.text, 'html.parser')

        if '-' in ec_number:
            target_link = soup.find('a', href=ec_number)
            if not target_link:
                return None, f"Classification definition not found for {ec_number}"
            definition = target_link.next_sibling.strip().lstrip(':').strip()
            return {"ec_number": ec_number, "definition": definition}, None

        # Process detailed parsing for specific EC numbers (adjust according to actual HTML structure)
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
                # Handle multi-line names
                accepted_td = accepted_th.find_next('td')
                if accepted_td:
                    info['accepted_name'] = accepted_td.get_text(' ', strip=True)
                    # Remove newlines
                    info['accepted_name'] = info['accepted_name'].replace('\n', ' ')

            # === Alternative Names ===
            if alt_th := main_table.find('th', string='Alternative Name(s)'):
                # May contain multiple <strong> tags
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
                    # Handle both cases: with <ul> list and direct text
                    if ul := react_td.find('ul', class_='ca'):
                        # Case with list (e.g. 1.1.1.1)
                        info['reaction'] = [
                            li.get_text(' ', strip=True)
                            .replace('\n', ' ')
                            for li in ul.find_all('li')
                        ]
                    else:
                        # Direct text case (e.g. 1.2.3.4)
                        reaction_text = react_td.get_text(' ', strip=True)
                        # Clean color markers
                        reaction_text = re.sub(r'<span.*?span>', '', reaction_text)
                        info['reaction'] = [reaction_text]

            # === Comments ===
            if comment_th := main_table.find('th', string='Comment(s)'):
                comment_td = comment_th.find_next('td')
                if comment_td:
                    # Handle both list and direct text cases
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
        return None, f"Network error: {str(e)}"
    except Exception as e:
        return None, f"Parsing error: {str(e)}"


import re


def validate_ec_number(ec_number):
    """Validation function that supports EC/ec prefix and strictly verifies hierarchy relationships"""
    # Preprocessing: remove prefix and whitespace
    clean_ec = re.sub(r'^\s*(EC|ec)\s*', '', ec_number, flags=re.IGNORECASE)

    # Validate basic format
    if not re.match(r'^([\dx-]+\.){3}[\dx-]+$', clean_ec):
        return False

    parts = clean_ec.split('.')

    # Strictly validate hierarchy relationships
    for i in range(len(parts)):
        part = parts[i]

        # Check validity of current part
        if not re.match(r'^[\dx-]+$', part):  # Allow multi-digit numbers
            return False

        # If current part is wildcard (x or -), subsequent parts must also be wildcards
        if part in ('x', '-'):
            for j in range(i + 1, len(parts)):
                if parts[j] not in ('x', '-'):
                    return False
            break  # Subsequent parts are confirmed as wildcards

    return True


def search_ec_by_annotation(keyword):
    """Search EC numbers by annotation with fuzzy matching"""
    base_url = "http://rest.kegg.jp/find/enzyme/"

    try:
        # URL encode the keyword and send request
        response = requests.get(f"{base_url}{quote_plus(keyword)}", timeout=10)
        response.raise_for_status()  # Automatically detect HTTP error status codes

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
                    continue  # Skip lines with invalid format

        return results or ["No corresponding EC number found"]

    except requests.exceptions.RequestException as e:
        return [f"API request failed: {str(e)}"]
    except Exception as e:
        return [f"Error occurred: {str(e)}"]
