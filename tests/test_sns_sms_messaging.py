#!/usr/bin/env python3
"""
Test script for SNS SMS messaging in static website template
"""

import unittest
import yaml
import os
import sys

# Add parent directory to path to import deploy_function
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from deploy_function import deploy_cloudformation_template, load_cloudformation_yaml

class TestSnsSmsMessaging(unittest.TestCase):
    """Test class for SNS SMS messaging in static website template"""

    def setUp(self):
        """Set up test environment"""
        # Path to the static website template
        self.template_path = 'iac/static_website/template.yaml'
        
        # Create a test config
        self.test_config = {
            'region': 'us-east-2',
            'solutions': {
                'static_website': {
                    'template_path': self.template_path,
                    'parameters': {
                        'BucketNamePrefix': 'test-bucket',
                        'OriginShieldRegion': 'us-east-2'
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

    def test_no_pinpoint_resources(self):
        """Test that the template does not contain any PinPoint resources"""
        # Load the template
        with open(self.template_path, 'r') as f:
            template_content = f.read()
            template = load_cloudformation_yaml(template_content)
        
        # Check that there are no PinPoint resources
        resources = template.get('Resources', {})
        for resource_id, resource in resources.items():
            resource_type = resource.get('Type', '')
            self.assertFalse(
                resource_type.startswith('AWS::PinpointSMSVoice::'),
                f"Found PinPoint resource: {resource_id} of type {resource_type}"
            )
    
    def test_sns_topic_exists(self):
        """Test that the template contains an SNS topic for SMS messaging"""
        # Load the template
        with open(self.template_path, 'r') as f:
            template_content = f.read()
            template = load_cloudformation_yaml(template_content)
        
        # Check that there is an SNS topic for SMS messaging
        resources = template.get('Resources', {})
        
        # Find the SMS topic
        sms_topic_found = False
        for resource_id, resource in resources.items():
            if (resource.get('Type') == 'AWS::SNS::Topic' and 
                resource_id == 'SmsTopic'):
                sms_topic_found = True
                break
        
        self.assertTrue(sms_topic_found, "SNS topic for SMS messaging not found")
    
    def test_sns_subscription_exists(self):
        """Test that the template contains an SNS subscription for SMS messaging"""
        # Load the template
        with open(self.template_path, 'r') as f:
            template_content = f.read()
            template = load_cloudformation_yaml(template_content)
        
        # Check that there is an SNS subscription for SMS messaging
        resources = template.get('Resources', {})
        
        # Find the SMS subscription
        sms_subscription_found = False
        for resource_id, resource in resources.items():
            if (resource.get('Type') == 'AWS::SNS::Subscription' and 
                resource_id == 'SmsSubscription'):
                properties = resource.get('Properties', {})
                if properties.get('Protocol') == 'sms':
                    sms_subscription_found = True
                    break
        
        self.assertTrue(sms_subscription_found, "SNS subscription for SMS messaging not found")
    
    def test_lambda_uses_sns_topic(self):
        """Test that the Lambda function uses the SNS topic for SMS messaging"""
        # Load the template
        with open(self.template_path, 'r') as f:
            template_content = f.read()
            template = load_cloudformation_yaml(template_content)
        
        # Check that the Lambda function has the SNS topic ARN as an environment variable
        resources = template.get('Resources', {})
        lambda_function = resources.get('ContactFormFunction', {})
        environment = lambda_function.get('Properties', {}).get('Environment', {})
        variables = environment.get('Variables', {})
        
        self.assertIn('SMS_TOPIC_ARN', variables, "SMS_TOPIC_ARN environment variable not found in Lambda function")
        self.assertEqual(variables.get('SMS_TOPIC_ARN'), {'Ref': 'SmsTopic'}, "SMS_TOPIC_ARN does not reference the SmsTopic")
        
        # Check that the Lambda function has permission to publish to the SNS topic
        lambda_role = resources.get('ContactFormLambdaRole', {})
        policies = lambda_role.get('Properties', {}).get('Policies', [])
        
        sns_publish_permission_found = False
        for policy in policies:
            statements = policy.get('PolicyDocument', {}).get('Statement', [])
            for statement in statements:
                if statement.get('Action') == 'sns:Publish' or 'sns:Publish' in statement.get('Action', []):
                    resources = statement.get('Resource', [])
                    if isinstance(resources, list) and {'Ref': 'SmsTopic'} in resources:
                        sns_publish_permission_found = True
                        break
        
        self.assertTrue(sns_publish_permission_found, "Lambda function does not have permission to publish to the SNS topic")

if __name__ == "__main__":
    unittest.main()