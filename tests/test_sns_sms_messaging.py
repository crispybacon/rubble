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

    def test_messaging_template_empty(self):
        """Test that the messaging template is empty (no resources)"""
        # Load the template
        template_path = 'iac/messaging/template.yaml'
        with open(template_path, 'r') as f:
            template_content = f.read()
            template = load_cloudformation_yaml(template_content)
        
        # Check that there are no resources defined
        resources = template.get('Resources', {})
        self.assertEqual(len(resources), 0, "Messaging template should not contain any resources")
        
        # Check that the template has the correct description
        description = template.get('Description', '')
        self.assertIn('Empty', description, "Template description should indicate it's empty")
        self.assertIn('Placeholder', description, "Template description should indicate it's a placeholder")

if __name__ == "__main__":
    unittest.main()