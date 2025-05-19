# ec_query_tool.py
from agents.system.tools.enzy_api import get_ec_info, validate_ec_number

def main():
    """EC Number Query Tool for ExPASy Enzyme Database"""
    print("ExPASy EC Number Query Tool")
    print("Enter EC numbers to get detailed information (q to quit)\n")

    while True:
        user_input = input("Enter EC number (e.g., 1.1.1.1, 1.-.-.-, EC 1.1.1.1): ").strip()
        
        # Exit condition
        if user_input.lower() == "q":
            break

        # Validate input format
        if not validate_ec_number(user_input):
            print("Invalid EC number format! Examples: 1.1.1.1 or 1.-.-.-")
            continue

        # Get EC information
        ec_data, error = get_ec_info(user_input)

        if error:
            print(f"Error: {error}")
            continue

        # Display results
        print("\n=== Query Results ===")
        
        if 'definition' in ec_data:
            # Wildcard EC number case
            print(f"EC Class: {ec_data['ec_number']}")
            print(f"Classification Definition: {ec_data['definition']}")
        else:
            # Specific EC number case
            print(f"EC Number: {ec_data['ec_number']}")
            print(f"Accepted Name: {ec_data['accepted_name']}")
            
            if ec_data['alternative_names']:
                print(f"Synonyms: {', '.join(ec_data['alternative_names'])}")
            
            if ec_data['reaction']:
                print("\nCatalyzed Reaction:")
                for reaction in ec_data['reaction']:
                    print(f"  • {reaction}")
            
            if ec_data['comments']:
                print("\nComments:")
                for comment in ec_data['comments']:
                    print(f"  › {comment}")
        
        print("-" * 40 + "\n")

if __name__ == "__main__":
    main()
