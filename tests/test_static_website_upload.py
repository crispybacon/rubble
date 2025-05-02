#!/usr/bin/env python3
"""
Unit tests for the static website upload functionality
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add parent directory to path to import the script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from deploy_function import deploy_cloudformation_template, upload_static_website


class TestStaticWebsiteUpload(unittest.TestCase):
    """Test cases for static website upload functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_config = {
            'solutions': {
                'static_website': {
                    'template_path': 'iac/static_website/template.yaml',
                    'content_dir': 'iac/static_website',
                    'parameters': {
                        'BucketNamePrefix': 'test-bucket'
                    }
                }
            }
        }
        
        # Mock CloudFormation stack outputs
        self.mock_outputs = {
            'S3BucketName': 'test-bucket-us-east-1',
            'CloudFrontDistributionId': 'ABCDEF12345',
            'CloudFrontDistributionDomainName': 'abcdef12345.cloudfront.net'
        }

    @patch('deploy_function.boto3.client')
    @patch('deploy_function.load_cloudformation_yaml')
    @patch('deploy_function.upload_static_website')
    def test_upload_after_stack_creation(self, mock_upload, mock_load_yaml, mock_boto_client):
        """Test that static website files are uploaded after stack creation."""
        # Mock CloudFormation client
        mock_cfn = MagicMock()
        mock_cf = MagicMock()
        mock_boto_client.side_effect = lambda service, region_name: mock_cfn if service == 'cloudformation' else mock_cf
        
        # Mock CloudFormation describe_stacks response
        mock_cfn.describe_stacks.side_effect = Exception("Stack does not exist")
        
        # Mock CloudFormation create_stack response
        mock_cfn.create_stack.return_value = {'StackId': 'test-stack-id'}
        
        # Mock CloudFormation get_waiter response
        mock_waiter = MagicMock()
        mock_cfn.get_waiter.return_value = mock_waiter
        
        # Mock CloudFormation describe_stacks response after stack creation
        mock_cfn.describe_stacks.side_effect = [
            Exception("Stack does not exist"),  # First call fails
            {  # Second call succeeds
                'Stacks': [{
                    'Outputs': [
                        {'OutputKey': 'S3BucketName', 'OutputValue': self.mock_outputs['S3BucketName']},
                        {'OutputKey': 'CloudFrontDistributionId', 'OutputValue': self.mock_outputs['CloudFrontDistributionId']},
                        {'OutputKey': 'CloudFrontDistributionDomainName', 'OutputValue': self.mock_outputs['CloudFrontDistributionDomainName']}
                    ]
                }]
            }
        ]
        
        # Mock CloudFront get_distribution response
        mock_cf.get_distribution.return_value = {
            'Distribution': {
                'ARN': 'arn:aws:cloudfront::123456789012:distribution/ABCDEF12345'
            }
        }
        
        # Mock template loading
        mock_load_yaml.return_value = {
            'Resources': {
                'StaticWebsiteBucket': {},
                'S3BucketPolicy': {},  # Include bucket policy in template
                'CloudFrontOriginAccessControl': {}  # Include Origin Access Control in template
            }
        }
        
        # Mock upload_static_website function
        mock_upload.return_value = True
        
        # Call the function with dry_run=False to simulate actual deployment
        with patch('builtins.open', MagicMock()):
            result = deploy_cloudformation_template(
                'static_website', 'test-stack', 'us-east-1', 
                self.test_config, export_template=False, force_update=False, dry_run=False
            )
        
        # Check that the function returned success
        self.assertEqual(result['status'], 'success')
        
        # Check that upload_static_website was called with the correct arguments
        mock_upload.assert_called_once_with(self.mock_outputs['S3BucketName'], 'us-east-1', self.test_config)

    @patch('deploy_function.boto3.client')
    @patch('deploy_function.load_cloudformation_yaml')
    @patch('deploy_function.upload_static_website')
    def test_upload_after_no_updates(self, mock_upload, mock_load_yaml, mock_boto_client):
        """Test that static website files are uploaded even when no stack updates are performed."""
        # Mock CloudFormation client
        mock_cfn = MagicMock()
        mock_cf = MagicMock()
        mock_boto_client.side_effect = lambda service, region_name: mock_cfn if service == 'cloudformation' else mock_cf
        
        # Mock CloudFormation describe_stacks response
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'Outputs': [
                    {'OutputKey': 'S3BucketName', 'OutputValue': self.mock_outputs['S3BucketName']},
                    {'OutputKey': 'CloudFrontDistributionId', 'OutputValue': self.mock_outputs['CloudFrontDistributionId']},
                    {'OutputKey': 'CloudFrontDistributionDomainName', 'OutputValue': self.mock_outputs['CloudFrontDistributionDomainName']}
                ]
            }]
        }
        
        # Mock CloudFormation update_stack to raise "No updates are to be performed" error
        mock_cfn.update_stack.side_effect = Exception("No updates are to be performed")
        
        # Mock CloudFront get_distribution response
        mock_cf.get_distribution.return_value = {
            'Distribution': {
                'ARN': 'arn:aws:cloudfront::123456789012:distribution/ABCDEF12345'
            }
        }
        
        # Mock template loading
        mock_load_yaml.return_value = {
            'Resources': {
                'StaticWebsiteBucket': {},
                'S3BucketPolicy': {},  # Include bucket policy in template
                'CloudFrontOriginAccessControl': {}  # Include Origin Access Control in template
            }
        }
        
        # Mock upload_static_website function
        mock_upload.return_value = True
        
        # Call the function with dry_run=False to simulate actual deployment
        with patch('builtins.open', MagicMock()):
            result = deploy_cloudformation_template(
                'static_website', 'test-stack', 'us-east-1', 
                self.test_config, export_template=False, force_update=False, dry_run=False
            )
        
        # Check that the function returned success
        self.assertEqual(result['status'], 'success')
        
        # Check that upload_static_website was called with the correct arguments
        mock_upload.assert_called_once_with(self.mock_outputs['S3BucketName'], 'us-east-1', self.test_config)


if __name__ == '__main__':
    unittest.main()