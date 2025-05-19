from agents.system.tools.go_api import get_go_definition


def main():
    while True:
        go_id = input("Enter GO ID (e.g. GO:0003677, q to quit): ").strip()
        if go_id.lower() == 'q':
            break

        if not validate_go_id(go_id):
            print("Invalid GO ID format. Should be GO: followed by 7 digits")
            continue

        result, error = get_go_definition(go_id)
        if error:
            print(f"Error: {error}")
            continue
        print(result)

        print(f"\nGO Term: {result['id']}")
        print(f"Name: {result['name']}")
        print(f"Ontology: {result['ontology']}")
        print(f"Definition:\n{result['definition']}\n")

        
        if result["synonyms"]:
            print("\nSynonyms:")
            for synonym in result["synonyms"]:
                print(f"- {synonym}")
        else:
            print("\nNo synonyms found.")
        print("")


def validate_go_id(go_id):
    return go_id.startswith("GO:") and len(go_id) == 10 and go_id[3:].isdigit()


if __name__ == "__main__":
    main()
