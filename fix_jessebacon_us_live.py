#!/usr/bin/env python3
"""
Fix for jessebacon-us-live stack issue with CloudFront distribution update Lambda function.
This script updates the CloudFormation stack with the fixed Lambda function.
"""

import boto3
import yaml
import json
import sys
import time

def load_fixed_template():
    """Load the fixed template with the corrected Lambda function."""
    try:
        with open('iac/streaming_media/template_fixed.yaml', 'r') as file:
            return file.read()
    except FileNotFoundError:
        print("Error: Fixed template file 'iac/streaming_media/template_fixed.yaml' not found.")
        sys.exit(1)

def update_stack(stack_name, template_body, region):
    """Update the CloudFormation stack with the fixed template."""
    try:
        # Initialize CloudFormation client
        cfn = boto3.client('cloudformation', region_name=region)
        
        # Get current stack parameters
        try:
            stack_info = cfn.describe_stacks(StackName=stack_name)
            current_parameters = stack_info['Stacks'][0].get('Parameters', [])
            
            # Update the stack with the fixed template
            print(f"Updating stack '{stack_name}' with fixed template...")
            cfn.update_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=current_parameters,
                Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM', 'CAPABILITY_AUTO_EXPAND']
            )
            
            # Wait for the update to complete
            print(f"Waiting for stack update to complete...")
            waiter = cfn.get_waiter('stack_update_complete')
            
            # Configure the waiter with increased timeout for CloudFront distributions
            waiter_config = {
                'Delay': 30,  # Check every 30 seconds
                'MaxAttempts': 120  # Wait up to 60 minutes (120 * 30 seconds)
            }
            
            print(f"Using extended waiter configuration: {waiter_config}")
            waiter.wait(StackName=stack_name, WaiterConfig=waiter_config)
            
            print(f"Stack '{stack_name}' updated successfully with fixed template.")
            return True
            
        except cfn.exceptions.ClientError as e:
            if 'No updates are to be performed' in str(e):
                print(f"No updates needed for stack '{stack_name}'. The template may already be fixed.")
                return True
            else:
                raise
    
    except Exception as e:
        print(f"Error updating stack: {e}")
        return False

def main():
    """Main function to fix the jessebacon-us-live stack."""
    # Set the stack name and region
    stack_name = "jessebacon-us-live"
    region = "us-east-1"  # Default region, change if needed
    
    # Load the fixed template
    template_body = load_fixed_template()
    
    # Update the stack with the fixed template
    success = update_stack(stack_name, template_body, region)
    
    if success:
        print("Stack update completed successfully.")
    else:
        print("Stack update failed. Please check CloudFormation events for more details.")
        sys.exit(1)

if __name__ == "__main__":
    main()