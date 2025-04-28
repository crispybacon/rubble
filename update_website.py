#!/usr/bin/env python3
"""
Update Website Script

This script updates the static website's index.html file with the API endpoint
from a deployed messaging solution. It should be run after deploying the messaging solution.
"""

import argparse
import boto3
import os
import re
import sys
import yaml
from pathlib import Path


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Update Website Script')
    parser.add_argument('--config', type=str, default='config.yaml',
                        help='Path to configuration file')
    parser.add_argument('--stack_name', type=str, required=True,
                        help='CloudFormation stack name for the messaging solution')
    parser.add_argument('--static_website_stack', type=str, required=True,
                        help='Name of the static website stack to update')
    parser.add_argument('--region', type=str,
                        help='AWS region (overrides config file)')
    return parser.parse_args()


def load_config(config_path):
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_path}' not found.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing configuration file: {e}")
        sys.exit(1)


def get_api_endpoint(stack_name, region):
    """Get the API endpoint from the CloudFormation stack outputs."""
    try:
        # Initialize CloudFormation client
        cfn = boto3.client('cloudformation', region_name=region)
        
        # Get stack outputs
        response = cfn.describe_stacks(StackName=stack_name)
        
        # Find the ApiEndpoint output
        for output in response['Stacks'][0]['Outputs']:
            if output['OutputKey'] == 'ApiEndpoint':
                return output['OutputValue']
        
        print(f"Error: ApiEndpoint not found in stack outputs for {stack_name}")
        return None
    except Exception as e:
        print(f"Error getting API endpoint from stack: {e}")
        return None


def update_index_html(api_endpoint, config):
    """Update the index.html file with the API endpoint."""
    try:
        # Get the static website content directory
        if 'solutions' not in config or 'static_website' not in config['solutions']:
            print("Error: Static website solution not found in configuration.")
            return False
        
        solution_config = config['solutions']['static_website']
        
        # Check if the content directory exists
        content_dir = solution_config.get('content_dir', 'iac/static_website/content')
        content_path = Path(content_dir)
        
        if not content_path.exists() or not content_path.is_dir():
            # Try the main directory
            content_path = Path('iac/static_website')
            if not content_path.exists() or not content_path.is_dir():
                print(f"Error: Static website directory not found.")
                return False
        
        # Find the index.html file
        index_path = content_path / 'index.html'
        if not index_path.exists():
            # Try the parent directory
            index_path = Path('iac/static_website/index.html')
            if not index_path.exists():
                print(f"Error: index.html file not found.")
                return False
        
        # Read the index.html file
        with open(index_path, 'r') as file:
            content = file.read()
        
        # Update the API endpoint in the file
        # Look for the fetch URL pattern in the JavaScript code
        pattern = r"fetch\('([^']*)',"
        if re.search(pattern, content):
            updated_content = re.sub(pattern, f"fetch('{api_endpoint}',", content)
            
            # Write the updated content back to the file
            with open(index_path, 'w') as file:
                file.write(updated_content)
            
            print(f"Successfully updated index.html with API endpoint: {api_endpoint}")
            
            # Also update the content directory if it's different
            if index_path != content_path / 'index.html':
                # Ensure the content directory exists
                os.makedirs(content_path, exist_ok=True)
                
                # Copy the updated file to the content directory
                with open(content_path / 'index.html', 'w') as file:
                    file.write(updated_content)
                
                print(f"Also copied updated index.html to content directory: {content_path}")
            
            return True
        else:
            print("Error: Could not find API endpoint placeholder in index.html")
            return False
    
    except Exception as e:
        print(f"Error updating index.html: {e}")
        return False


def add_messaging_to_solution_demos(config):
    """Add the messaging solution to the Solution Demonstrations section in index.html."""
    try:
        # Get the static website content directory
        if 'solutions' not in config or 'static_website' not in config['solutions']:
            print("Error: Static website solution not found in configuration.")
            return False
        
        solution_config = config['solutions']['static_website']
        
        # Check if the content directory exists
        content_dir = solution_config.get('content_dir', 'iac/static_website/content')
        content_path = Path(content_dir)
        
        if not content_path.exists() or not content_path.is_dir():
            # Try the main directory
            content_path = Path('iac/static_website')
            if not content_path.exists() or not content_path.is_dir():
                print(f"Error: Static website directory not found.")
                return False
        
        # Find the index.html file
        index_path = content_path / 'index.html'
        if not index_path.exists():
            # Try the parent directory
            index_path = Path('iac/static_website/index.html')
            if not index_path.exists():
                print(f"Error: index.html file not found.")
                return False
        
        # Read the index.html file
        with open(index_path, 'r') as file:
            content = file.read()
        
        # Check if the messaging solution is already in the Solution Demonstrations section
        if 'AWS End User Messaging' in content:
            print("Messaging solution already in Solution Demonstrations section.")
            return True
        
        # Find the Solution Demonstrations section
        solution_demos_pattern = r'<div class="solutionDemos">\s*<h2>\s*Solution Demonstrations\s*</h2>\s*<ul>(.*?)</ul>'
        solution_demos_match = re.search(solution_demos_pattern, content, re.DOTALL)
        
        if solution_demos_match:
            # Create the new solution demo entry
            messaging_solution_entry = """
            <li>
              <div class="jobPosition">
                <span class="bolded">
                  AWS End User Messaging
                </span>
                <span>
                  AWS CloudFormation
                </span>
              </div>
              <div class="job-content">
                <div class="projectName bolded">
                  <span>
                    SMS and Email Contact Forms
                  </span>
                </div>
                <div class="smallText">
                  <p>
                    A secure messaging infrastructure for handling contact form submissions via SMS and email.
                  </p>
                  <ul>
                    <li>
                      <p>
                        Deployed using CloudFormation for infrastructure as code
                      </p>
                    </li>
                    <li>
                      <p>
                        Uses AWS End User Messaging services for reliable delivery
                      </p>
                    </li>
                    <li>
                      <p>
                        Secured with KMS encryption and IAM permissions
                      </p>
                    </li>
                  </ul>
                  <p>
                    <span class="bolded">Technologies: </span>AWS Lambda, API Gateway, SNS, SES, PinpointSMSVoice, KMS
                  </p>
                </div>
              </div>
            </li>"""
            
            # Insert the new solution demo entry after the existing entries
            updated_content = re.sub(
                solution_demos_pattern,
                f'<div class="solutionDemos">\n          <h2>\n            Solution Demonstrations\n          </h2>\n          <ul>{solution_demos_match.group(1)}{messaging_solution_entry}\n          </ul>',
                content,
                flags=re.DOTALL
            )
            
            # Write the updated content back to the file
            with open(index_path, 'w') as file:
                file.write(updated_content)
            
            print("Successfully added messaging solution to Solution Demonstrations section.")
            
            # Also update the content directory if it's different
            if index_path != content_path / 'index.html':
                # Ensure the content directory exists
                os.makedirs(content_path, exist_ok=True)
                
                # Copy the updated file to the content directory
                with open(content_path / 'index.html', 'w') as file:
                    file.write(updated_content)
                
                print(f"Also copied updated index.html to content directory: {content_path}")
            
            return True
        else:
            print("Error: Could not find Solution Demonstrations section in index.html")
            return False
    
    except Exception as e:
        print(f"Error adding messaging solution to Solution Demonstrations: {e}")
        return False


def main():
    """Main function to update the website."""
    # Parse arguments and load configuration
    args = parse_arguments()
    config = load_config(args.config)
    
    # Determine which region to use (CLI overrides config)
    region = args.region if args.region else config.get('region', 'us-east-1')
    
    # Get the API endpoint from the CloudFormation stack
    api_endpoint = get_api_endpoint(args.stack_name, region)
    if not api_endpoint:
        print("Failed to get API endpoint. Exiting.")
        sys.exit(1)
    
    # Store the static website stack name in the config
    if 'solutions' not in config:
        config['solutions'] = {}
    if 'messaging' not in config['solutions']:
        config['solutions']['messaging'] = {}
    if 'parameters' not in config['solutions']['messaging']:
        config['solutions']['messaging']['parameters'] = {}
    config['solutions']['messaging']['parameters']['StaticWebsiteStackName'] = args.static_website_stack
    
    # Update the index.html file with the API endpoint
    if not update_index_html(api_endpoint, config):
        print("Failed to update index.html. Exiting.")
        sys.exit(1)
    
    # Add the messaging solution to the Solution Demonstrations section
    if not add_messaging_to_solution_demos(config):
        print("Failed to add messaging solution to Solution Demonstrations. Exiting.")
        sys.exit(1)
    
    print("Website update completed successfully!")


if __name__ == "__main__":
    main()