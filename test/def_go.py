from agents.system.tools.go_api import search_go_by_definition


def search_by_definition():
    query = "thermal"
    results, error = search_go_by_definition(query)

    if error:
        print(f"Error: {error}")
        return

    #print(f"Found {len(results)} results for '{query}':")
    print(results)
    for idx, term in enumerate(results, 1):
        print(f"\n{idx}. {term['id']} - {term['name']}")
        print(f"Definition: {term['definition']}")


if __name__ == "__main__":
    #test_search_by_definition()
    search_by_definition()