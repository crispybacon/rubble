#!/usr/bin/env python3
"""
Unit tests for the update_stack_parameters function in deploy_function.py
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

# Add parent directory to path to import the main script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from deploy_function import update_stack_parameters

class TestUpdateStackParameters(unittest.TestCase):
    """Test cases for update_stack_parameters function."""

    @patch('boto3.client')
    def test_update_stack_parameters(self, mock_boto_client):
        """Test that update_stack_parameters correctly updates stack parameters."""
        # Mock the CloudFormation client
        mock_cfn = MagicMock()
        mock_boto_client.return_value = mock_cfn
        
        # Mock the describe_stacks response
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'Parameters': [
                    {'ParameterKey': 'BucketNamePrefix', 'ParameterValue': 'test-bucket'},
                    {'ParameterKey': 'MessagingStackName', 'ParameterValue': ''}
                ]
            }]
        }
        
        # Mock the get_template response
        mock_cfn.get_template.return_value = {
            'TemplateBody': {
                'Parameters': {
                    'BucketNamePrefix': {'Type': 'String', 'Default': 'test-bucket'},
                    'MessagingStackName': {'Type': 'String', 'Default': ''}
                },
                'Conditions': {
                    'HasMessagingStack': {'Fn::Not': [{'Fn::Equals': [{'Ref': 'MessagingStackName'}, '']}]}
                },
                'Resources': {
                    'TestBucket': {
                        'Type': 'AWS::S3::Bucket',
                        'Properties': {
                            'BucketName': {'Ref': 'BucketNamePrefix'}
                        }
                    }
                },
                'Outputs': {
                    'ApiEndpoint': {
                        'Condition': 'HasMessagingStack',
                        'Value': {'Fn::ImportValue': {'Fn::Sub': '${MessagingStackName}-ApiEndpoint'}}
                    }
                }
            }
        }
        
        # Call the function with new parameters
        result = update_stack_parameters('test-stack', 'us-west-2', {'MessagingStackName': 'messaging-stack'})
        
        # Check that the function returned success
        self.assertEqual(result['status'], 'success')
        
        # Check that update_stack was called with the correct parameters
        mock_cfn.update_stack.assert_called_once()
        args, kwargs = mock_cfn.update_stack.call_args
        
        # Check that the stack name is correct
        self.assertEqual(kwargs['StackName'], 'test-stack')
        
        # Check that the parameters include the updated MessagingStackName
        parameters = kwargs['Parameters']
        messaging_stack_param = next((p for p in parameters if p['ParameterKey'] == 'MessagingStackName'), None)
        self.assertIsNotNone(messaging_stack_param)
        self.assertEqual(messaging_stack_param['ParameterValue'], 'messaging-stack')
        
        # Check that the BucketNamePrefix parameter is preserved
        bucket_name_param = next((p for p in parameters if p['ParameterKey'] == 'BucketNamePrefix'), None)
        self.assertIsNotNone(bucket_name_param)
        self.assertEqual(bucket_name_param['ParameterValue'], 'test-bucket')
        
    @patch('boto3.client')
    def test_update_stack_parameters_no_updates(self, mock_boto_client):
        """Test that update_stack_parameters handles 'No updates are to be performed' error."""
        # Mock the CloudFormation client
        mock_cfn = MagicMock()
        mock_boto_client.return_value = mock_cfn
        
        # Mock the describe_stacks response
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'Parameters': [
                    {'ParameterKey': 'BucketNamePrefix', 'ParameterValue': 'test-bucket'},
                    {'ParameterKey': 'MessagingStackName', 'ParameterValue': 'messaging-stack'}
                ]
            }]
        }
        
        # Mock the get_template response
        mock_cfn.get_template.return_value = {
            'TemplateBody': {
                'Parameters': {
                    'BucketNamePrefix': {'Type': 'String', 'Default': 'test-bucket'},
                    'MessagingStackName': {'Type': 'String', 'Default': ''}
                }
            }
        }
        
        # Mock the update_stack method to raise a ClientError with 'No updates are to be performed'
        mock_cfn.exceptions.ClientError = ClientError
        mock_cfn.update_stack.side_effect = ClientError(
            {'Error': {'Code': 'ValidationError', 'Message': 'No updates are to be performed'}},
            'UpdateStack'
        )
        
        # Call the function with the same parameters as already in the stack
        result = update_stack_parameters('test-stack', 'us-west-2', {'MessagingStackName': 'messaging-stack'})
        
        # Check that the function returned success
        self.assertEqual(result['status'], 'success')
        self.assertIn('No updates needed', result['message'])
        
    @patch('boto3.client')
    def test_update_stack_parameters_error(self, mock_boto_client):
        """Test that update_stack_parameters handles errors correctly."""
        # Mock the CloudFormation client
        mock_cfn = MagicMock()
        mock_boto_client.return_value = mock_cfn
        
        # Mock the describe_stacks method to raise an exception
        mock_cfn.describe_stacks.side_effect = Exception('Test error')
        
        # Call the function
        result = update_stack_parameters('test-stack', 'us-west-2', {'MessagingStackName': 'messaging-stack'})
        
        # Check that the function returned error
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['message'], 'Test error')

if __name__ == "__main__":
    unittest.main()