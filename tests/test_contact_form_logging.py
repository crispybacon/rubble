#!/usr/bin/env python3
"""
Test script for contact form logging and DynamoDB storage
"""

import unittest
from unittest.mock import patch, MagicMock, ANY
import yaml
import os
import sys
import json
import boto3
from datetime import datetime

# Add parent directory to path to import deploy_function
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from deploy_function import deploy_cloudformation_template

class TestContactFormLogging(unittest.TestCase):
    """Test class for contact form logging and DynamoDB storage"""

    def setUp(self):
        """Set up test environment"""
        # Create a test config
        self.test_config = {
            'region': 'us-west-2',
            'solutions': {
                'messaging': {
                    'template_path': 'iac/messaging/template.yaml',
                    'parameters': {
                        'StaticWebsiteStackName': 'test-static-website-stack',
                        'ContactLogRetentionDays': 30
                    }
                }
            },
            'messaging': {
                'email': {
                    'destination': 'test@example.com'
                },
                'sms': {
                    'destination': '+12345678901',
                    'country': 'US',
                    'originator_id': 'TestSender'
                }
            }
        }
        
        # Mock Lambda event with client information
        self.mock_event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'messageType': 'email',
                'message': 'Test message from contact form'
            }),
            'requestContext': {
                'identity': {
                    'sourceIp': '192.168.1.1',
                    'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                'requestTime': '2025-04-27T13:37:42Z'
            }
        }

    @patch('deploy_function.boto3.client')
    def test_dynamodb_table_creation(self, mock_boto3_client):
        """Test that DynamoDB table is created in CloudFormation template"""
        # Mock the CloudFormation client
        mock_cfn = MagicMock()
        mock_boto3_client.return_value = mock_cfn
        
        # Call the function with a dry run flag to avoid actually deploying
        result = deploy_cloudformation_template(
            'messaging', 
            'test-messaging-stack', 
            'us-west-2', 
            self.test_config, 
            dry_run=True
        )
        
        # Check that the result is successful
        self.assertEqual(result['status'], 'dry_run')
        
        # Load the template to check for DynamoDB table
        with open('iac/messaging/template.yaml', 'r') as f:
            template = yaml.safe_load(f)
        
        # Check that the DynamoDB table resource exists
        self.assertIn('ContactFormTable', template['Resources'])
        
        # Check table properties
        table_props = template['Resources']['ContactFormTable']['Properties']
        self.assertEqual(table_props['BillingMode'], 'PAY_PER_REQUEST')
        self.assertTrue(table_props['PointInTimeRecoverySpecification']['PointInTimeRecoveryEnabled'])
        self.assertTrue(table_props['SSESpecification']['SSEEnabled'])
        
        # Check that the Lambda function has DynamoDB permissions
        lambda_role = template['Resources']['ContactFormLambdaRole']
        permissions_found = False
        for policy in lambda_role['Properties']['Policies']:
            for statement in policy['PolicyDocument']['Statement']:
                if 'dynamodb:PutItem' in statement.get('Action', []):
                    permissions_found = True
                    break
        
        self.assertTrue(permissions_found, "Lambda function should have DynamoDB permissions")
        
        # Check that the Lambda function has the DynamoDB table name as an environment variable
        lambda_env = template['Resources']['ContactFormFunction']['Properties']['Environment']['Variables']
        self.assertIn('CONTACT_FORM_TABLE', lambda_env)

    @patch('boto3.client')
    def test_lambda_function_logging(self, mock_boto3_client):
        """Test that the Lambda function logs client information and message details"""
        # Load the Lambda function code from the template
        with open('iac/messaging/template.yaml', 'r') as f:
            template = yaml.safe_load(f)
        
        lambda_code = template['Resources']['ContactFormFunction']['Properties']['Code']['ZipFile']
        
        # Check that the Lambda function extracts client information
        self.assertIn('const clientIp = event.requestContext?.identity?.sourceIp', lambda_code)
        self.assertIn('const userAgent = event.requestContext?.identity?.userAgent', lambda_code)
        
        # Check that the Lambda function logs client information
        self.assertIn('console.log(\'Contact form submission received:', lambda_code)
        self.assertIn('clientIp', lambda_code)
        self.assertIn('userAgent', lambda_code)
        
        # Check that the Lambda function stores data in DynamoDB
        self.assertIn('await dynamodb.put', lambda_code)
        self.assertIn('TableName: process.env.CONTACT_FORM_TABLE', lambda_code)
        
        # Check that the client IP is included in the message
        self.assertIn('Submitted from: ${clientIp}', lambda_code)
        self.assertIn('Browser: ${userAgent}', lambda_code)

    @patch('boto3.client')
    def test_cloudwatch_log_group_creation(self, mock_boto3_client):
        """Test that CloudWatch Log Group is created with the specified retention period"""
        # Load the template to check for CloudWatch Log Group
        with open('iac/messaging/template.yaml', 'r') as f:
            template = yaml.safe_load(f)
        
        # Check that the CloudWatch Log Group resource exists
        self.assertIn('ContactFormLambdaLogGroup', template['Resources'])
        
        # Check log group properties
        log_group_props = template['Resources']['ContactFormLambdaLogGroup']['Properties']
        self.assertEqual(log_group_props['RetentionInDays'], {'Ref': 'ContactLogRetentionDays'})
        self.assertIn('KmsKeyId', log_group_props)

    @patch('deploy_function.boto3.client')
    def test_contact_log_retention_parameter(self, mock_boto3_client):
        """Test that ContactLogRetentionDays parameter is passed to CloudFormation"""
        # Mock the CloudFormation client
        mock_cfn = MagicMock()
        mock_boto3_client.return_value = mock_cfn
        
        # Call the function with a dry run flag to avoid actually deploying
        result = deploy_cloudformation_template(
            'messaging', 
            'test-messaging-stack', 
            'us-west-2', 
            self.test_config, 
            dry_run=True
        )
        
        # Check that the result is successful
        self.assertEqual(result['status'], 'dry_run')
        
        # Check that the ContactLogRetentionDays parameter is included in the parameters
        parameters = result['parameters']
        retention_param = None
        for param in parameters:
            if param['ParameterKey'] == 'ContactLogRetentionDays':
                retention_param = param
                break
        
        # Assert that the parameter exists and has the correct value
        self.assertIsNotNone(retention_param, "ContactLogRetentionDays parameter not found")
        self.assertEqual(retention_param['ParameterValue'], 30)

    @patch('deploy_function.boto3.client')
    def test_vpc_configuration(self, mock_boto3_client):
        """Test that the Lambda function has VPC configuration when VPC parameters are provided"""
        # Update the test config to include VPC parameters
        self.test_config['solutions']['messaging']['parameters'].update({
            'VpcId': 'vpc-12345',
            'PrivateSubnet1Id': 'subnet-12345',
            'PrivateSubnet2Id': 'subnet-67890'
        })
        
        # Mock the CloudFormation client
        mock_cfn = MagicMock()
        mock_boto3_client.return_value = mock_cfn
        
        # Call the function with a dry run flag to avoid actually deploying
        result = deploy_cloudformation_template(
            'messaging', 
            'test-messaging-stack', 
            'us-west-2', 
            self.test_config, 
            dry_run=True
        )
        
        # Check that the result is successful
        self.assertEqual(result['status'], 'dry_run')
        
        # Check that the VPC parameters are included in the parameters
        parameters = result['parameters']
        vpc_params = {}
        for param in parameters:
            if param['ParameterKey'] in ['VpcId', 'PrivateSubnet1Id', 'PrivateSubnet2Id']:
                vpc_params[param['ParameterKey']] = param['ParameterValue']
        
        # Assert that the parameters exist and have the correct values
        self.assertEqual(vpc_params['VpcId'], 'vpc-12345')
        self.assertEqual(vpc_params['PrivateSubnet1Id'], 'subnet-12345')
        self.assertEqual(vpc_params['PrivateSubnet2Id'], 'subnet-67890')
        
        # Load the template to check for VPC configuration
        with open('iac/messaging/template.yaml', 'r') as f:
            template = yaml.safe_load(f)
        
        # Check that the HasVpcConfig condition exists
        self.assertIn('HasVpcConfig', template['Conditions'])
        
        # Check that the Lambda security group exists
        self.assertIn('LambdaSecurityGroup', template['Resources'])
        self.assertEqual(template['Resources']['LambdaSecurityGroup']['Condition'], 'HasVpcConfig')
        
        # Check that the Lambda function has VPC configuration
        lambda_function = template['Resources']['ContactFormFunction']['Properties']
        self.assertIn('VpcConfig', lambda_function)
        
        # Check that the Lambda role has VPC access permissions
        lambda_role = template['Resources']['ContactFormLambdaRole']['Properties']
        managed_policies = lambda_role['ManagedPolicyArns']
        vpc_policy_found = False
        for policy in managed_policies:
            if isinstance(policy, dict) and 'Fn::If' in policy:
                if policy['Fn::If'][0] == 'HasVpcConfig' and 'AWSLambdaVPCAccessExecutionRole' in policy['Fn::If'][1]:
                    vpc_policy_found = True
                    break
        
        self.assertTrue(vpc_policy_found, "Lambda role should have VPC access policy when VPC is configured")

if __name__ == "__main__":
    unittest.main()