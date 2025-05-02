#!/usr/bin/env python3
"""
Unit tests for the CloudFront Origin Access Control functionality
"""

import unittest
import sys
import os
import yaml
from pathlib import Path

# Add parent directory to path to import the script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestOriginAccessControl(unittest.TestCase):
    """Test cases for CloudFront Origin Access Control functionality."""

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

    def test_origin_access_control_exists(self):
        """Test that the CloudFront Origin Access Control resource exists."""
        self.assertIn('CloudFrontOriginAccessControl', self.template_content['Resources'])
        
        # Check that it has the correct type
        oac = self.template_content['Resources']['CloudFrontOriginAccessControl']
        self.assertEqual(oac['Type'], 'AWS::CloudFront::OriginAccessControl')

    def test_origin_access_control_config(self):
        """Test that the Origin Access Control is configured correctly."""
        oac = self.template_content['Resources']['CloudFrontOriginAccessControl']
        
        # Check that it has the required properties
        self.assertIn('OriginAccessControlConfig', oac['Properties'])
        config = oac['Properties']['OriginAccessControlConfig']
        
        # Check that it has a name
        self.assertIn('Name', config)
        
        # Check that it's configured for S3
        self.assertEqual(config['OriginAccessControlOriginType'], 's3')
        
        # Check that signing is enabled
        self.assertEqual(config['SigningBehavior'], 'always')
        self.assertEqual(config['SigningProtocol'], 'sigv4')

    def test_cloudfront_uses_origin_access_control(self):
        """Test that the CloudFront distribution uses the Origin Access Control."""
        # Get the CloudFront distribution resource
        self.assertIn('CloudFrontDistribution', self.template_content['Resources'])
        cloudfront = self.template_content['Resources']['CloudFrontDistribution']
        
        # Check that it has origins
        self.assertIn('Origins', cloudfront['Properties']['DistributionConfig'])
        origins = cloudfront['Properties']['DistributionConfig']['Origins']
        
        # Check that there's at least one origin
        self.assertGreaterEqual(len(origins), 1)
        
        # Check that the first origin has an OriginAccessControlId
        self.assertIn('OriginAccessControlId', origins[0])
        
        # Check that it references the CloudFrontOriginAccessControl resource
        self.assertIn('GetAtt', origins[0]['OriginAccessControlId'])
        self.assertEqual(origins[0]['OriginAccessControlId']['GetAtt'][0], 'CloudFrontOriginAccessControl')
        self.assertEqual(origins[0]['OriginAccessControlId']['GetAtt'][1], 'Id')

    def test_s3_bucket_policy_allows_cloudfront(self):
        """Test that the S3 bucket policy allows CloudFront access."""
        # Check that the S3BucketPolicy resource exists
        self.assertIn('S3BucketPolicy', self.template_content['Resources'])
        
        # Get the bucket policy
        bucket_policy = self.template_content['Resources']['S3BucketPolicy']
        
        # Check that it has a policy document
        self.assertIn('PolicyDocument', bucket_policy['Properties'])
        policy_doc = bucket_policy['Properties']['PolicyDocument']
        
        # Check that it has statements
        self.assertIn('Statement', policy_doc)
        statements = policy_doc['Statement']
        
        # Check that there's at least one statement
        self.assertGreaterEqual(len(statements), 1)
        
        # Find the statement that allows CloudFront access
        cloudfront_statement = None
        for statement in statements:
            if (statement.get('Principal', {}).get('Service') == 'cloudfront.amazonaws.com' and
                statement.get('Action') == 's3:GetObject'):
                cloudfront_statement = statement
                break
        
        # Check that we found a CloudFront statement
        self.assertIsNotNone(cloudfront_statement, "No statement allowing CloudFront access found")
        
        # Check that it has a condition
        self.assertIn('Condition', cloudfront_statement)
        condition = cloudfront_statement['Condition']
        
        # Check that it uses StringEquals with AWS:SourceArn
        self.assertIn('StringEquals', condition)
        self.assertIn('AWS:SourceArn', condition['StringEquals'])


if __name__ == '__main__':
    unittest.main()