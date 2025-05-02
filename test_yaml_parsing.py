#!/usr/bin/env python3
"""
Test script to verify YAML parsing of the static website template
"""

import yaml
import sys

def main():
    """Main function to test YAML parsing"""
    try:
        with open('iac/static_website/template.yaml', 'r') as f:
            template = yaml.safe_load(f)
        print("YAML parsing successful!")
        
        # Check if the ApiEndpoint output exists and has the correct structure
        if 'Outputs' in template and 'ApiEndpoint' in template['Outputs']:
            api_endpoint = template['Outputs']['ApiEndpoint']
            print("ApiEndpoint output found:")
            print(f"  Description: {api_endpoint.get('Description')}")
            print(f"  Condition: {api_endpoint.get('Condition')}")
            print(f"  Value: {api_endpoint.get('Value')}")
            
            # Check if the Value is using ImportValue and Sub correctly
            if isinstance(api_endpoint.get('Value'), dict) and 'Fn::ImportValue' in api_endpoint.get('Value'):
                print("  ImportValue structure is correct")
            else:
                print("  ImportValue structure is NOT correct")
        else:
            print("ApiEndpoint output not found in template")
            
        return 0
    except Exception as e:
        print(f"Error parsing YAML: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())