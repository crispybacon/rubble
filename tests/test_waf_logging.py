#!/usr/bin/env python3
"""
Unit tests for the WAF logging configuration in the static website template
"""

import unittest
import os
import yaml
from pathlib import Path

class TestWAFLogging(unittest.TestCase):
    """Test cases for WAF logging configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.template_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'iac' / 'static_website' / 'template.yaml'
            
        # Read the CloudFormation template
        # We'll use a custom loader to handle CloudFormation's custom YAML tags
        class CloudFormationLoader(yaml.SafeLoader):
            pass
        
        def construct_cfn_tag(loader, node):
            if isinstance(node, yaml.ScalarNode):
                return node.value
            elif isinstance(node, yaml.SequenceNode):
                return [loader.construct_scalar(i) for i in node.value]
            else:
                return loader.construct_mapping(node)
        
        # Add constructors for CloudFormation's custom YAML tags
        for tag in ['!Ref', '!GetAtt', '!Sub', '!Join', '!If', '!Equals', '!Not', '!FindInMap']:
            CloudFormationLoader.add_constructor(tag, construct_cfn_tag)
        
        with open(self.template_path, 'r') as f:
            self.template_content = yaml.load(f, CloudFormationLoader)

    def test_waf_resources_exist(self):
        """Test that WAF resources exist but logging configurations are removed."""
        # Check that the WAF resources exist
        self.assertIn('WAFv2WebACLCLOUDFRONT', self.template_content['Resources'])
        self.assertIn('RegionalWebACL', self.template_content['Resources'])
        
        # Check that the CloudFront WAF is conditional on us-east-1 region
        self.assertIn('Condition', self.template_content['Resources']['WAFv2WebACLCLOUDFRONT'])
        self.assertEqual(self.template_content['Resources']['WAFv2WebACLCLOUDFRONT']['Condition'], 'IsUsEast1Region')
        
        # Check that the WAF logging configurations and role are removed
        self.assertNotIn('CloudFrontWebACLLoggingConfiguration', self.template_content['Resources'])
        self.assertNotIn('RegionalWebACLLoggingConfiguration', self.template_content['Resources'])
        self.assertNotIn('WAFLoggingRole', self.template_content['Resources'])

if __name__ == '__main__':
    unittest.main()