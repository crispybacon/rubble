#!/usr/bin/env python3
"""
Test script for deploy_function.py
"""

import yaml
import json
import unittest
from unittest.mock import patch, MagicMock
from deploy_function import deploy_cloudformation_template, update_stack_parameters

class TestDeployFunction(unittest.TestCase):
    """Test cases for deploy_function.py"""
    
    def test_deploy_cloudformation_template_no_aws_region(self):
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
        result = deploy_cloudformation_template('test_solution', 'test-stack', 'us-west-2', test_config, dry_run=True)
        
        # Check that the result is as expected
        self.assertEqual(result['status'], 'dry_run')
        self.assertEqual(result['message'], 'Dry run completed successfully')
        
        # Check that the parameters don't include AwsRegion
        aws_region_param = False
        for param in result['parameters']:
            if param.get('ParameterKey') == 'AwsRegion':
                aws_region_param = True
                break
        
        self.assertFalse(aws_region_param, "AwsRegion parameter should not be included")
        
        # Clean up
        import os
        if os.path.exists('test_template.yaml'):
            os.remove('test_template.yaml')
    
    @patch('boto3.client')
    def test_waiter_configuration(self, mock_boto3_client):
        """Test that the waiter is configured with increased timeout values."""
        # Mock the CloudFormation client and its methods
        mock_cfn = MagicMock()
        mock_boto3_client.return_value = mock_cfn
        
        # Mock the waiter
        mock_waiter = MagicMock()
        mock_cfn.get_waiter.return_value = mock_waiter
        
        # Mock describe_stacks to simulate stack exists
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'Outputs': [
                    {'OutputKey': 'TestOutput', 'OutputValue': 'TestValue'}
                ]
            }]
        }
        
        # Create a test config
        test_config = {
            'solutions': {
                'test_solution': {
                    'template_path': 'test_template.yaml',
                    'parameters': {}
                }
            }
        }
        
        # Call the function with update=True to trigger the waiter code
        deploy_cloudformation_template('test_solution', 'test-stack', 'us-west-2', test_config, force_update=True)
        
        # Check that the waiter was called with the expected configuration
        mock_waiter.wait.assert_called()
        call_args = mock_waiter.wait.call_args[1]
        
        # Check that WaiterConfig was included
        self.assertIn('WaiterConfig', call_args)
        
        # Check that the WaiterConfig has the expected values
        waiter_config = call_args['WaiterConfig']
        self.assertEqual(waiter_config['Delay'], 30)
        self.assertEqual(waiter_config['MaxAttempts'], 120)
    
    @patch('boto3.client')
    def test_update_stack_parameters_waiter_config(self, mock_boto3_client):
        """Test that update_stack_parameters uses the extended waiter configuration."""
        # Mock the CloudFormation client and its methods
        mock_cfn = MagicMock()
        mock_boto3_client.return_value = mock_cfn
        
        # Mock the waiter
        mock_waiter = MagicMock()
        mock_cfn.get_waiter.return_value = mock_waiter
        
        # Mock describe_stacks to simulate stack exists
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'Parameters': [
                    {'ParameterKey': 'TestParam', 'ParameterValue': 'OldValue'}
                ]
            }]
        }
        
        # Mock get_template
        mock_cfn.get_template.return_value = {
            'TemplateBody': '{"Parameters": {"TestParam": {"Type": "String"}}}'
        }
        
        # Call update_stack_parameters
        update_stack_parameters('test-stack', 'us-west-2', {'TestParam': 'NewValue'})
        
        # Check that the waiter was called with the expected configuration
        mock_waiter.wait.assert_called()
        call_args = mock_waiter.wait.call_args[1]
        
        # Check that WaiterConfig was included
        self.assertIn('WaiterConfig', call_args)
        
        # Check that the WaiterConfig has the expected values
        waiter_config = call_args['WaiterConfig']
        self.assertEqual(waiter_config['Delay'], 30)
        self.assertEqual(waiter_config['MaxAttempts'], 120)

def test_deploy_cloudformation_template():
    """Legacy test function for backward compatibility."""
    test_case = TestDeployFunction()
    test_case.test_deploy_cloudformation_template_no_aws_region()

if __name__ == "__main__":
    unittest.main()