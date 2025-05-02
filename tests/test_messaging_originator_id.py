#!/usr/bin/env python3
"""
Test script for SMS originator ID in messaging template
"""

import unittest
from unittest.mock import patch, MagicMock
import yaml
import os
import sys
import json

# Add parent directory to path to import deploy_function
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from deploy_function import deploy_cloudformation_template

class TestMessagingOriginatorId(unittest.TestCase):
    """Test class for SMS originator ID in messaging template"""

    def setUp(self):
        """Set up test environment"""
        # Create a test config with SMS originator ID
        self.test_config = {
            'region': 'us-west-2',
            'solutions': {
                'messaging': {
                    'template_path': 'iac/messaging/template.yaml',
                    'parameters': {
                        'StaticWebsiteStackName': 'test-static-website-stack'
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

    @patch('deploy_function.boto3.client')
    def test_sms_originator_id_parameter(self, mock_boto3_client):
        """Test that SmsOriginatorId parameter is passed to CloudFormation"""
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
        
        # Check that the SmsOriginatorId parameter is included in the parameters
        parameters = result['parameters']
        sms_originator_id_param = None
        for param in parameters:
            if param['ParameterKey'] == 'SmsOriginatorId':
                sms_originator_id_param = param
                break
        
        # Assert that the parameter exists and has the correct value
        self.assertIsNotNone(sms_originator_id_param, "SmsOriginatorId parameter not found")
        self.assertEqual(sms_originator_id_param['ParameterValue'], 'TestSender')

if __name__ == "__main__":
    unittest.main()