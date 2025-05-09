#!/usr/bin/env python3
"""
Unit tests for the combined website and streaming media CloudFormation template
"""

import unittest
import os
import yaml
from pathlib import Path

class TestCombinedWebsite(unittest.TestCase):
    """Test cases for combined website and streaming media CloudFormation template."""

    def setUp(self):
        """Set up test fixtures."""
        self.template_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'iac' / 'combined_website' / 'template.yaml'
        
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
        for tag in ['!Ref', '!GetAtt', '!Sub', '!Join', '!If', '!Equals', '!Not', '!FindInMap', '!Select']:
            CloudFormationLoader.add_constructor(tag, construct_cfn_tag)
        
        with open(self.template_path, 'r') as f:
            self.template_content = yaml.load(f, CloudFormationLoader)

    def test_required_parameters_exist(self):
        """Test that all required parameters exist in the template."""
        # Check that the required parameters exist
        required_params = [
            'BucketNamePrefix', 'OriginShieldRegion', 'LiveInputType', 'LiveInputWhitelistCidr'
        ]
        
        for param in required_params:
            self.assertIn(param, self.template_content['Parameters'], 
                         f"Required parameter '{param}' not found in template")
            
        # Check that BucketNamePrefix has the correct default
        self.assertEqual(self.template_content['Parameters']['BucketNamePrefix']['Default'], 
                         "flatstone-solutions", 
                         "BucketNamePrefix should have default value 'flatstone-solutions'")
                         
        # Check that OriginShieldRegion has the correct default
        self.assertEqual(self.template_content['Parameters']['OriginShieldRegion']['Default'], 
                         "us-east-2", 
                         "OriginShieldRegion should have default value 'us-east-2'")

    def test_s3_buckets_exist(self):
        """Test that the required S3 buckets exist in the template."""
        # Check that the S3 buckets exist
        required_buckets = [
            'StaticWebsiteBucket', 'VodContentBucket'
        ]
        
        for bucket in required_buckets:
            self.assertIn(bucket, self.template_content['Resources'], 
                         f"Required bucket '{bucket}' not found in template")
            
        # Check that the buckets have the correct properties
        for bucket in required_buckets:
            self.assertEqual(self.template_content['Resources'][bucket]['Type'], 'AWS::S3::Bucket',
                            f"Resource '{bucket}' should be of type AWS::S3::Bucket")
            self.assertIn('VersioningConfiguration', self.template_content['Resources'][bucket]['Properties'],
                         f"Bucket '{bucket}' should have VersioningConfiguration")
            self.assertEqual(self.template_content['Resources'][bucket]['Properties']['VersioningConfiguration']['Status'], 'Enabled',
                            f"Bucket '{bucket}' should have versioning enabled")
            self.assertIn('PublicAccessBlockConfiguration', self.template_content['Resources'][bucket]['Properties'],
                         f"Bucket '{bucket}' should have PublicAccessBlockConfiguration")
            self.assertEqual(self.template_content['Resources'][bucket]['Properties']['PublicAccessBlockConfiguration']['BlockPublicAcls'], True,
                            f"Bucket '{bucket}' should block public ACLs")

    def test_cloudfront_distribution_exists(self):
        """Test that the CloudFront distribution exists in the template."""
        # Check that the CloudFront distribution exists
        self.assertIn('CloudFrontDistribution', self.template_content['Resources'],
                     "CloudFrontDistribution not found in template")
        
        # Check that the CloudFront distribution has the correct properties
        self.assertEqual(self.template_content['Resources']['CloudFrontDistribution']['Type'], 'AWS::CloudFront::Distribution',
                        "CloudFrontDistribution should be of type AWS::CloudFront::Distribution")
        self.assertIn('DistributionConfig', self.template_content['Resources']['CloudFrontDistribution']['Properties'],
                     "CloudFrontDistribution should have DistributionConfig")
        self.assertIn('Origins', self.template_content['Resources']['CloudFrontDistribution']['Properties']['DistributionConfig'],
                     "CloudFrontDistribution should have Origins")
        self.assertIn('DefaultCacheBehavior', self.template_content['Resources']['CloudFrontDistribution']['Properties']['DistributionConfig'],
                     "CloudFrontDistribution should have DefaultCacheBehavior")
        self.assertIn('CacheBehaviors', self.template_content['Resources']['CloudFrontDistribution']['Properties']['DistributionConfig'],
                     "CloudFrontDistribution should have CacheBehaviors")

    def test_cloudfront_origins(self):
        """Test that the CloudFront distribution has the correct origins."""
        # Get the origins from the CloudFront distribution
        origins = self.template_content['Resources']['CloudFrontDistribution']['Properties']['DistributionConfig']['Origins']
        
        # Check that there are at least 3 origins (StaticWebsiteOrigin, VODOrigin, HLSOrigin)
        self.assertGreaterEqual(len(origins), 3, "CloudFrontDistribution should have at least 3 origins")
        
        # Check that the required origins exist
        origin_ids = [origin.get('Id') for origin in origins]
        required_origins = ['StaticWebsiteOrigin', 'VODOrigin', 'HLSOrigin']
        
        for origin_id in required_origins:
            self.assertIn(origin_id, origin_ids, f"CloudFrontDistribution should have origin with Id '{origin_id}'")

    def test_cloudfront_cache_behaviors(self):
        """Test that the CloudFront distribution has the correct cache behaviors."""
        # Get the cache behaviors from the CloudFront distribution
        cache_behaviors = self.template_content['Resources']['CloudFrontDistribution']['Properties']['DistributionConfig']['CacheBehaviors']
        
        # Check that there are at least 2 cache behaviors (live and vod)
        self.assertGreaterEqual(len(cache_behaviors), 2, "CloudFrontDistribution should have at least 2 cache behaviors")
        
        # Check that the required path patterns exist
        path_patterns = [behavior.get('PathPattern') for behavior in cache_behaviors]
        required_patterns = ['/live/*', '/vod/*']
        
        for pattern in required_patterns:
            self.assertIn(pattern, path_patterns, f"CloudFrontDistribution should have cache behavior with PathPattern '{pattern}'")
        
        # Check that the cache behaviors target the correct origins
        for behavior in cache_behaviors:
            if behavior.get('PathPattern') == '/live/*':
                self.assertEqual(behavior.get('TargetOriginId'), 'HLSOrigin',
                                "Cache behavior for '/live/*' should target HLSOrigin")
            elif behavior.get('PathPattern') == '/vod/*':
                self.assertEqual(behavior.get('TargetOriginId'), 'VODOrigin',
                                "Cache behavior for '/vod/*' should target VODOrigin")

    def test_media_resources_exist(self):
        """Test that the required media resources exist in the template."""
        # Check that the required media resources exist
        required_resources = [
            'MediaLiveChannel', 'MediaLiveInput', 'MediaLiveInputSecurityGroup',
            'MediaPackageChannel', 'MediaPackageHlsEndpoint', 'MediaPackageDashEndpoint'
        ]
        
        for resource in required_resources:
            self.assertIn(resource, self.template_content['Resources'], 
                         f"Required resource '{resource}' not found in template")

    def test_outputs_exist(self):
        """Test that the required outputs exist in the template."""
        # Check that the required outputs exist
        required_outputs = [
            'CloudFrontDistributionDomainName', 'CloudFrontDistributionId',
            'StaticWebsiteBucketName', 'VodBucketName',
            'MediaLiveInputUrl', 'HlsEndpointUrl', 'DashEndpointUrl'
        ]
        
        for output in required_outputs:
            self.assertIn(output, self.template_content['Outputs'], 
                         f"Required output '{output}' not found in template")

    def test_no_lambda_function(self):
        """Test that there is no Lambda function in the template."""
        # Check that there is no Lambda function in the template
        for resource_name, resource in self.template_content['Resources'].items():
            self.assertNotEqual(resource.get('Type'), 'AWS::Lambda::Function',
                              f"Resource '{resource_name}' should not be of type AWS::Lambda::Function")

if __name__ == '__main__':
    unittest.main()