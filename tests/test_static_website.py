#!/usr/bin/env python3
"""
Unit tests for the static website HTML and CSS
"""

import unittest
import os
import re
import yaml
from pathlib import Path

class TestStaticWebsite(unittest.TestCase):
    """Test cases for static website HTML and CSS."""

    def setUp(self):
        """Set up test fixtures."""
        self.html_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'iac' / 'static_website' / 'index.html'
        self.css_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'iac' / 'static_website' / 'index.css'
        self.template_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'iac' / 'static_website' / 'template.yaml'
        
        # Read the HTML and CSS files
        with open(self.html_path, 'r') as f:
            self.html_content = f.read()
        
        with open(self.css_path, 'r') as f:
            self.css_content = f.read()
            
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

    def test_work_experience_minimized_by_default(self):
        """Test that work experience items are minimized by default."""
        # Check if the JavaScript initializes work experience items as collapsed
        self.assertIn("// Initialize all items as collapsed by default", self.html_content)
        self.assertIn("jobContent.classList.add('collapsed')", self.html_content)
        self.assertIn("item.style.paddingBottom = '0.2cm'", self.html_content)

    def test_no_trailing_line_for_last_experience_item(self):
        """Test that there is no trailing line below the bullet point for the final experience item."""
        # Check if the CSS has a rule for the last work experience item
        self.assertIn(".workExperience>ul>li:last-child:before", self.css_content)
        
        # Check if the rule sets the bottom property to stop at the bullet point
        last_item_rule = re.search(r'\.workExperience>ul>li:last-child:before\s*{[^}]*}', self.css_content)
        self.assertIsNotNone(last_item_rule, "Last item rule not found in CSS")
        
        # Check if the bottom property is set to stop at the bullet point
        bottom_property = re.search(r'bottom:\s*0\.1cm', last_item_rule.group(0))
        self.assertIsNotNone(bottom_property, "Bottom property not set correctly for last item")

    def test_solution_demos_section_exists(self):
        """Test that the solution demonstrations section exists."""
        self.assertIn('<div class="solutionDemos">', self.html_content)
        self.assertIn('Solution Demonstrations', self.html_content)

    def test_static_website_solution_included(self):
        """Test that the static website solution is included in the solutions list."""
        self.assertIn('Static Website', self.html_content)
        self.assertIn('AWS CloudFormation', self.html_content)
        self.assertIn('Professional Resume/Portfolio Website', self.html_content)

    def test_solution_demos_collapsible(self):
        """Test that solution demonstrations are collapsible like work experience."""
        # Check if the JavaScript initializes solution demo items as collapsed
        self.assertIn("// Collapsible solution demonstrations functionality", self.html_content)
        self.assertIn("const solutionDemoItems = document.querySelectorAll('.solutionDemos > ul > li')", self.html_content)
        
        # Check if the CSS has styling for solution demos similar to work experience
        self.assertIn(".solutionDemos>ul", self.css_content)
        self.assertIn(".solutionDemos>ul>li", self.css_content)
        
    def test_solution_demos_hover_effects(self):
        """Test that solution demonstrations have hover effects like work experience."""
        # Check if the CSS has cursor pointer for solution demos
        solution_demos_li_rule = re.search(r'\.solutionDemos>ul>li\s*{[^}]*}', self.css_content)
        self.assertIsNotNone(solution_demos_li_rule, "Solution demos li rule not found in CSS")
        self.assertIn("cursor: pointer", solution_demos_li_rule.group(0))
        
        # Check if the CSS has hover color change effect for solution demos
        self.assertIn(".solutionDemos .jobPosition .bolded", self.css_content)
        self.assertIn(".solutionDemos .jobPosition .bolded:hover", self.css_content)
        
        # Check if the hover color is the same as work experience
        work_exp_hover_rule = re.search(r'\.workExperience\s+\.jobPosition\s+\.bolded:hover\s*{[^}]*color:\s*([^;]*)}', self.css_content)
        solution_hover_rule = re.search(r'\.solutionDemos\s+\.jobPosition\s+\.bolded:hover\s*{[^}]*color:\s*([^;]*)}', self.css_content)
        
        self.assertIsNotNone(work_exp_hover_rule, "Work experience hover rule not found in CSS")
        self.assertIsNotNone(solution_hover_rule, "Solution demos hover rule not found in CSS")
        
        # Both sections should use the same hover color
        self.assertEqual(work_exp_hover_rule.group(1), solution_hover_rule.group(1))

    def test_required_parameters_exist(self):
        """Test that all required parameters exist in the template."""
        # Check that the required parameters exist
        required_params = [
            'BucketNamePrefix', 'OriginShieldRegion'
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

    def test_cloudfront_allowed_methods(self):
        """Test that CloudFront allows GET and HEAD requests to the S3 bucket."""
        # Get the CloudFront distribution resource
        cloudfront_resource = self.template_content['Resources']['CloudFrontDistribution']
        self.assertIn('DefaultCacheBehavior', cloudfront_resource['Properties']['DistributionConfig'])
        
        # Check that GET and HEAD are in AllowedMethods
        default_behavior = cloudfront_resource['Properties']['DistributionConfig']['DefaultCacheBehavior']
        self.assertIn('AllowedMethods', default_behavior)
        self.assertEqual(len(default_behavior['AllowedMethods']), 2)
        self.assertIn('GET', default_behavior['AllowedMethods'])
        self.assertIn('HEAD', default_behavior['AllowedMethods'])
        
        # Check that GET and HEAD are in CachedMethods
        self.assertIn('CachedMethods', default_behavior)
        self.assertEqual(len(default_behavior['CachedMethods']), 2)
        self.assertIn('GET', default_behavior['CachedMethods'])
        self.assertIn('HEAD', default_behavior['CachedMethods'])
        
    def test_cloudfront_origin_access_control(self):
        """Test that CloudFront is configured with Origin Access Control."""
        # Check that the CloudFrontOriginAccessControl resource exists
        self.assertIn('CloudFrontOriginAccessControl', self.template_content['Resources'])
        
        # Check that it has the correct properties
        oac = self.template_content['Resources']['CloudFrontOriginAccessControl']
        self.assertEqual(oac['Type'], 'AWS::CloudFront::OriginAccessControl')
        self.assertIn('OriginAccessControlConfig', oac['Properties'])
        self.assertEqual(oac['Properties']['OriginAccessControlConfig']['OriginAccessControlOriginType'], 's3')
        self.assertEqual(oac['Properties']['OriginAccessControlConfig']['SigningBehavior'], 'always')
        self.assertEqual(oac['Properties']['OriginAccessControlConfig']['SigningProtocol'], 'sigv4')
        
        # Check that the CloudFront distribution uses the Origin Access Control
        cloudfront_resource = self.template_content['Resources']['CloudFrontDistribution']
        origins = cloudfront_resource['Properties']['DistributionConfig']['Origins']
        self.assertEqual(len(origins), 1)
        self.assertIn('OriginAccessControlId', origins[0])
        # The OriginAccessControlId should reference the CloudFrontOriginAccessControl resource
        self.assertIn('GetAtt', origins[0]['OriginAccessControlId'])

    def test_s3_bucket_configuration(self):
        """Test that the S3 bucket is configured correctly."""
        # Check that the StaticWebsiteBucket resource exists
        self.assertIn('StaticWebsiteBucket', self.template_content['Resources'])
        
        # Get the bucket configuration
        bucket = self.template_content['Resources']['StaticWebsiteBucket']
        self.assertEqual(bucket['Type'], 'AWS::S3::Bucket')
        
        # Check that the bucket has OwnershipControls configured to enforce bucket owner ownership
        self.assertIn('OwnershipControls', bucket['Properties'])
        self.assertIn('Rules', bucket['Properties']['OwnershipControls'])
        self.assertEqual(bucket['Properties']['OwnershipControls']['Rules'][0]['ObjectOwnership'], 'BucketOwnerEnforced')
        
        # Check that the PublicAccessBlockConfiguration blocks all public access
        self.assertIn('PublicAccessBlockConfiguration', bucket['Properties'])
        self.assertEqual(bucket['Properties']['PublicAccessBlockConfiguration']['BlockPublicAcls'], True)
        self.assertEqual(bucket['Properties']['PublicAccessBlockConfiguration']['IgnorePublicAcls'], True)
        self.assertEqual(bucket['Properties']['PublicAccessBlockConfiguration']['BlockPublicPolicy'], True)
        self.assertEqual(bucket['Properties']['PublicAccessBlockConfiguration']['RestrictPublicBuckets'], True)
        
        # Check that versioning is enabled
        self.assertIn('VersioningConfiguration', bucket['Properties'])
        self.assertEqual(bucket['Properties']['VersioningConfiguration']['Status'], 'Enabled')
        
        # Check that AccessControl is not set (as it's redundant with the public access block configuration)
        self.assertNotIn('AccessControl', bucket['Properties'])
        
    def test_s3_bucket_policy_configuration(self):
        """Test that the S3 bucket policy is configured correctly."""
        # Check that the S3BucketPolicy resource exists
        self.assertIn('S3BucketPolicy', self.template_content['Resources'])
        
        # Check that the bucket policy has the correct properties
        bucket_policy = self.template_content['Resources']['S3BucketPolicy']
        self.assertEqual(bucket_policy['Type'], 'AWS::S3::BucketPolicy')
        
        # Check that the bucket policy references the S3 bucket
        self.assertIn('Bucket', bucket_policy['Properties'])
        self.assertIn('Ref', bucket_policy['Properties']['Bucket'])
        self.assertEqual(bucket_policy['Properties']['Bucket']['Ref'], 'StaticWebsiteBucket')
        
        # Check that the policy document has the correct structure
        policy_doc = bucket_policy['Properties']['PolicyDocument']
        self.assertEqual(policy_doc['Version'], '2008-10-17')
        self.assertEqual(policy_doc['Id'], 'PolicyForCloudFrontPrivateContent')
        
        # Check the statement
        statements = policy_doc['Statement']
        self.assertEqual(len(statements), 1, "Bucket policy should have one statement")
        
        # Check the statement for CloudFront access
        get_statement = statements[0]
        self.assertEqual(get_statement['Sid'], 'AllowCloudFrontServicePrincipal')
        self.assertEqual(get_statement['Effect'], 'Allow')
        self.assertEqual(get_statement['Principal']['Service'], 'cloudfront.amazonaws.com')
        self.assertEqual(get_statement['Action'], 's3:GetObject')
        
        # Check the resource pattern
        self.assertIn('Resource', get_statement)
        
        # Check the condition - should use StringEquals with specific distribution
        self.assertIn('Condition', get_statement)
        self.assertIn('StringEquals', get_statement['Condition'])
        self.assertIn('AWS:SourceArn', get_statement['Condition']['StringEquals'])
        
    def test_cloudfront_distribution_id_output(self):
        """Test that the CloudFront distribution ID is included in the outputs."""
        # Check that the CloudFrontDistributionId output exists
        self.assertIn('CloudFrontDistributionId', self.template_content['Outputs'])
        
        # Check that it references the CloudFront distribution
        output = self.template_content['Outputs']['CloudFrontDistributionId']
        self.assertIn('Value', output)
        self.assertIn('Ref', output['Value'])
        self.assertEqual(output['Value']['Ref'], 'CloudFrontDistribution')

    def test_no_waf_resources(self):
        """Test that the template doesn't include WAF resources."""
        # Check that WAF resources don't exist
        self.assertNotIn('WAFv2WebACLCLOUDFRONT', self.template_content['Resources'],
                        "WAFv2WebACLCLOUDFRONT should not exist in the template")
        self.assertNotIn('RegionalWebACL', self.template_content['Resources'],
                        "RegionalWebACL should not exist in the template")
        
    def test_no_cloudwatch_resources(self):
        """Test that the template doesn't include CloudWatch resources."""
        # Check that CloudWatch resources don't exist
        self.assertNotIn('ApplicationLogGroup', self.template_content['Resources'],
                        "ApplicationLogGroup should not exist in the template")
        self.assertNotIn('StaticWebsiteDashboard', self.template_content['Resources'],
                        "StaticWebsiteDashboard should not exist in the template")

    def test_cloudfront_viewer_certificate_configuration(self):
        """Test that the CloudFront ViewerCertificate is configured correctly."""
        # Get the CloudFront distribution resource
        cloudfront_resource = self.template_content['Resources']['CloudFrontDistribution']
        self.assertIn('ViewerCertificate', cloudfront_resource['Properties']['DistributionConfig'])
        
        viewer_certificate = cloudfront_resource['Properties']['DistributionConfig']['ViewerCertificate']
        
        # Check that we have the CloudFrontDefaultCertificate property
        self.assertIn('CloudFrontDefaultCertificate', viewer_certificate)
        self.assertTrue(viewer_certificate['CloudFrontDefaultCertificate'], 
                       "CloudFrontDefaultCertificate should be true")

    def test_cloudfront_default_root_object(self):
        """Test that CloudFront has index.html as the default root object."""
        # Check that the CloudFront distribution has DefaultRootObject set to index.html
        cloudfront_resource = self.template_content['Resources']['CloudFrontDistribution']
        self.assertIn('DefaultRootObject', cloudfront_resource['Properties']['DistributionConfig'])
        self.assertEqual(cloudfront_resource['Properties']['DistributionConfig']['DefaultRootObject'], 'index.html',
                        "DefaultRootObject should be set to index.html")

if __name__ == '__main__':
    unittest.main()