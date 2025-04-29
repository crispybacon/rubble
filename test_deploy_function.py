#!/usr/bin/env python3
"""
Test script for deploy_function.py
"""

import yaml
import json
from deploy_function import deploy_cloudformation_template

def test_deploy_cloudformation_template():
    """Test that deploy_cloudformation_template doesn't add AwsRegion parameter if it doesn't exist in the template."""
    # Create a simple test template without AwsRegion parameter
    test_template = {
        "Parameters": {
            "BucketNamePrefix": {
                "Type": "String",
                "Default": "test-bucket"
            }
        },
        "Resources": {
            "TestBucket": {
                "Type": "AWS::S3::Bucket",
                "Properties": {
                    "BucketName": {"Ref": "BucketNamePrefix"}
                }
            }
        }
    }
    
    # Write the test template to a file
    with open('test_template.yaml', 'w') as f:
        yaml.dump(test_template, f)
    
    # Create a test config
    test_config = {
        'solutions': {
            'test_solution': {
                'template_path': 'test_template.yaml',
                'parameters': {
                    'BucketNamePrefix': 'test-bucket'
                }
            }
        }
    }
    
    # Call the function with a dry run flag to avoid actually deploying
    try:
        # This should not raise an error about AwsRegion parameter not existing
        result = deploy_cloudformation_template('test_solution', 'test-stack', 'us-west-2', test_config, dry_run=True)
        print("Test passed: No error about AwsRegion parameter not existing")
    except Exception as e:
        if "AwsRegion" in str(e):
            print(f"Test failed: Error about AwsRegion parameter: {e}")
        else:
            print(f"Test failed with unexpected error: {e}")
    
    # Clean up
    import os
    if os.path.exists('test_template.yaml'):
        os.remove('test_template.yaml')

if __name__ == "__main__":
    test_deploy_cloudformation_template()