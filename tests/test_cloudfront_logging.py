#!/usr/bin/env python3
"""
Unit tests for CloudFront logging configuration in the static website and combined website templates
"""

import unittest
import os
import yaml
from pathlib import Path

class TestCloudFrontLogging(unittest.TestCase):
    """Test cases for CloudFront logging configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.static_website_template_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'iac' / 'static_website' / 'template.yaml'
        self.combined_website_template_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'iac' / 'combined_website' / 'template.yaml'
            
        # Read the CloudFormation templates
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
        
        with open(self.static_website_template_path, 'r') as f:
            self.static_website_template = yaml.load(f, CloudFormationLoader)
            
        with open(self.combined_website_template_path, 'r') as f:
            self.combined_website_template = yaml.load(f, CloudFormationLoader)

    def test_static_website_cloudfront_logging_parameters(self):
        """Test that the static website template has CloudFront logging parameters."""
        parameters = self.static_website_template['Parameters']
        
        # Check that the logging parameters exist
        self.assertIn('LogRetentionInDays', parameters)
        self.assertIn('EnableCloudFrontLogging', parameters)
        
        # Check parameter properties
        self.assertEqual(parameters['LogRetentionInDays']['Type'], 'Number')
        self.assertEqual(parameters['EnableCloudFrontLogging']['Type'], 'String')
        self.assertEqual(parameters['EnableCloudFrontLogging']['Default'], 'true')
        self.assertEqual(parameters['EnableCloudFrontLogging']['AllowedValues'], ['true', 'false'])

    def test_static_website_cloudfront_logging_condition(self):
        """Test that the static website template has CloudFront logging condition."""
        conditions = self.static_website_template['Conditions']
        
        # Check that the condition exists
        self.assertIn('EnableCloudFrontLoggingCondition', conditions)

    def test_static_website_cloudfront_log_group(self):
        """Test that the static website template has CloudFront log group."""
        resources = self.static_website_template['Resources']
        
        # Check that the CloudWatch Log Group resource exists
        self.assertIn('CloudFrontLogGroup', resources)
        
        # Check that it has the correct condition
        self.assertEqual(resources['CloudFrontLogGroup']['Condition'], 'EnableCloudFrontLoggingCondition')
        
        # Check properties
        properties = resources['CloudFrontLogGroup']['Properties']
        self.assertIn('LogGroupName', properties)
        self.assertIn('RetentionInDays', properties)
        self.assertEqual(properties['RetentionInDays'], '!Ref LogRetentionInDays')

    def test_static_website_cloudfront_real_time_log_config(self):
        """Test that the static website template has CloudFront real-time log config."""
        resources = self.static_website_template['Resources']
        
        # Check that the real-time log config resource exists
        self.assertIn('CloudFrontRealTimeLogConfig', resources)
        
        # Check that it has the correct condition
        self.assertEqual(resources['CloudFrontRealTimeLogConfig']['Condition'], 'EnableCloudFrontLoggingCondition')
        
        # Check properties
        properties = resources['CloudFrontRealTimeLogConfig']['Properties']
        self.assertIn('EndPoints', properties)
        self.assertIn('Fields', properties)
        self.assertIn('SamplingRate', properties)
        self.assertEqual(properties['SamplingRate'], 100)

    def test_static_website_cloudfront_distribution_logging(self):
        """Test that the static website CloudFront distribution has logging configured."""
        resources = self.static_website_template['Resources']
        
        # Check that the CloudFront distribution resource exists
        self.assertIn('CloudFrontDistribution', resources)
        
        # Check that the distribution config has real-time logging configured
        distribution_config = resources['CloudFrontDistribution']['Properties']['DistributionConfig']
        self.assertIn('DefaultCacheBehavior', distribution_config)
        self.assertIn('RealtimeLogConfigArn', distribution_config['DefaultCacheBehavior'])
        
        # Check that standard logging to S3 is configured
        self.assertIn('Logging', distribution_config)

    def test_combined_website_cloudfront_logging_parameters(self):
        """Test that the combined website template has CloudFront logging parameters."""
        parameters = self.combined_website_template['Parameters']
        
        # Check that the logging parameters exist
        self.assertIn('LogRetentionInDays', parameters)
        self.assertIn('EnableCloudFrontLogging', parameters)
        self.assertIn('EnableMediaLiveLogging', parameters)
        self.assertIn('EnableMediaPackageLogging', parameters)
        
        # Check parameter properties
        self.assertEqual(parameters['LogRetentionInDays']['Type'], 'Number')
        self.assertEqual(parameters['EnableCloudFrontLogging']['Type'], 'String')
        self.assertEqual(parameters['EnableCloudFrontLogging']['Default'], 'true')
        self.assertEqual(parameters['EnableCloudFrontLogging']['AllowedValues'], ['true', 'false'])

    def test_combined_website_cloudfront_logging_conditions(self):
        """Test that the combined website template has CloudFront logging conditions."""
        conditions = self.combined_website_template['Conditions']
        
        # Check that the conditions exist
        self.assertIn('EnableCloudFrontLoggingCondition', conditions)
        self.assertIn('EnableMediaLiveLoggingCondition', conditions)
        self.assertIn('EnableMediaPackageLoggingCondition', conditions)

    def test_combined_website_cloudfront_log_group(self):
        """Test that the combined website template has CloudFront log group."""
        resources = self.combined_website_template['Resources']
        
        # Check that the CloudWatch Log Group resources exist
        self.assertIn('CloudFrontLogGroup', resources)
        self.assertIn('MediaLiveLogGroup', resources)
        self.assertIn('MediaPackageLogGroup', resources)
        
        # Check that they have the correct conditions
        self.assertEqual(resources['CloudFrontLogGroup']['Condition'], 'EnableCloudFrontLoggingCondition')
        self.assertEqual(resources['MediaLiveLogGroup']['Condition'], 'EnableMediaLiveLoggingCondition')
        self.assertEqual(resources['MediaPackageLogGroup']['Condition'], 'EnableMediaPackageLoggingCondition')
        
        # Check properties
        properties = resources['CloudFrontLogGroup']['Properties']
        self.assertIn('LogGroupName', properties)
        self.assertIn('RetentionInDays', properties)
        self.assertEqual(properties['RetentionInDays'], '!Ref LogRetentionInDays')

    def test_combined_website_cloudfront_real_time_log_config(self):
        """Test that the combined website template has CloudFront real-time log config."""
        resources = self.combined_website_template['Resources']
        
        # Check that the real-time log config resource exists
        self.assertIn('CloudFrontRealTimeLogConfig', resources)
        
        # Check that it has the correct condition
        self.assertEqual(resources['CloudFrontRealTimeLogConfig']['Condition'], 'EnableCloudFrontLoggingCondition')
        
        # Check properties
        properties = resources['CloudFrontRealTimeLogConfig']['Properties']
        self.assertIn('EndPoints', properties)
        self.assertIn('Fields', properties)
        self.assertIn('SamplingRate', properties)
        self.assertEqual(properties['SamplingRate'], 100)

    def test_combined_website_cloudfront_distribution_logging(self):
        """Test that the combined website CloudFront distribution has logging configured."""
        resources = self.combined_website_template['Resources']
        
        # Check that the CloudFront distribution resource exists
        self.assertIn('CloudFrontDistribution', resources)
        
        # Check that the distribution config has real-time logging configured
        distribution_config = resources['CloudFrontDistribution']['Properties']['DistributionConfig']
        self.assertIn('DefaultCacheBehavior', distribution_config)
        self.assertIn('RealtimeLogConfigArn', distribution_config['DefaultCacheBehavior'])
        
        # Check that cache behaviors also have real-time logging configured
        self.assertIn('CacheBehaviors', distribution_config)
        for cache_behavior in distribution_config['CacheBehaviors']:
            self.assertIn('RealtimeLogConfigArn', cache_behavior)
        
        # Check that standard logging to S3 is configured
        self.assertIn('Logging', distribution_config)

    def test_combined_website_medialive_logging(self):
        """Test that the combined website MediaLive channel has logging configured."""
        resources = self.combined_website_template['Resources']
        
        # Check that the MediaLive channel resource exists
        self.assertIn('MediaLiveChannel', resources)
        
        # Check that the channel has logging configured
        properties = resources['MediaLiveChannel']['Properties']
        self.assertIn('LogLevel', properties)
        self.assertIn('CloudWatchLoggingOptions', properties)

    def test_combined_website_mediapackage_logging(self):
        """Test that the combined website MediaPackage channel has logging configured."""
        resources = self.combined_website_template['Resources']
        
        # Check that the MediaPackage channel resource exists
        self.assertIn('MediaPackageChannel', resources)
        
        # Check that the channel has logging configured
        properties = resources['MediaPackageChannel']['Properties']
        self.assertIn('LogConfiguration', properties)

    def test_static_website_outputs(self):
        """Test that the static website template has logging outputs."""
        outputs = self.static_website_template['Outputs']
        
        # Check that the logging outputs exist
        self.assertIn('CloudFrontLogGroupName', outputs)
        self.assertIn('CloudFrontLogBucketName', outputs)
        
        # Check that they have the correct conditions
        self.assertEqual(outputs['CloudFrontLogGroupName']['Condition'], 'EnableCloudFrontLoggingCondition')
        self.assertEqual(outputs['CloudFrontLogBucketName']['Condition'], 'EnableCloudFrontLoggingCondition')

    def test_combined_website_outputs(self):
        """Test that the combined website template has logging outputs."""
        outputs = self.combined_website_template['Outputs']
        
        # Check that the logging outputs exist
        self.assertIn('CloudFrontLogGroupName', outputs)
        self.assertIn('MediaLiveLogGroupName', outputs)
        self.assertIn('MediaPackageLogGroupName', outputs)
        self.assertIn('CloudFrontLogBucketName', outputs)
        
        # Check that they have the correct conditions
        self.assertEqual(outputs['CloudFrontLogGroupName']['Condition'], 'EnableCloudFrontLoggingCondition')
        self.assertEqual(outputs['MediaLiveLogGroupName']['Condition'], 'EnableMediaLiveLoggingCondition')
        self.assertEqual(outputs['MediaPackageLogGroupName']['Condition'], 'EnableMediaPackageLoggingCondition')
        self.assertEqual(outputs['CloudFrontLogBucketName']['Condition'], 'EnableCloudFrontLoggingCondition')

if __name__ == '__main__':
    unittest.main()