from agents.system.tools.enzy_api import search_ec_by_annotation

def search_by_definition():
    test_cases = [
        "thermal stability",  # 精确查询
    ]

    for case in test_cases:
        #print(f"Searching: {case}")
        results = search_ec_by_annotation(case)
        print(results[:5])

        if isinstance(results[0], str):  # 错误信息
            print(f"  → {results[0]}")
        else:
            #print(f"  Found {len(results)} results:")
            for item in results[:3]:  # 显示前3个结果
                print(f"  EC {item['EC_Number']}: {item['Description']}")
        print("-" * 60)


if __name__ == "__main__":
    search_by_definition()