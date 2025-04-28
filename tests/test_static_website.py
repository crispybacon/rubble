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
        
    def test_cloudfront_cache_policy_name(self):
        """Test that the CloudFront CachePolicy name doesn't use the reserved 'Managed-' prefix."""
        # Find the CloudFrontCachePolicy resource
        self.assertIn('CloudFrontCachePolicy', self.template_content['Resources'])
        
        # Get the CachePolicyConfig
        cache_policy_config = self.template_content['Resources']['CloudFrontCachePolicy']['Properties']['CachePolicyConfig']
        
        # Check that the name doesn't start with 'Managed-'
        self.assertIn('Name', cache_policy_config)
        self.assertFalse(cache_policy_config['Name'].startswith('Managed-'), 
                         f"CachePolicy name '{cache_policy_config['Name']}' should not start with 'Managed-' prefix")
        
        # Verify it uses the correct prefix
        self.assertTrue(cache_policy_config['Name'].startswith('Custom-'), 
                        f"CachePolicy name should start with 'Custom-' prefix")
                        
    def test_wafv2_webacl_configuration(self):
        """Test that the WAFv2 WebACL is configured correctly for different regions."""
        # Check that the condition for us-east-1 region exists
        self.assertIn('Conditions', self.template_content)
        self.assertIn('IsUsEast1Region', self.template_content['Conditions'])
        
        # Check that the CloudFront WAF is only created in us-east-1
        self.assertIn('WAFv2WebACLCLOUDFRONT', self.template_content['Resources'])
        self.assertIn('Condition', self.template_content['Resources']['WAFv2WebACLCLOUDFRONT'])
        self.assertEqual(self.template_content['Resources']['WAFv2WebACLCLOUDFRONT']['Condition'], 'IsUsEast1Region')
        
        # Check that the CloudFront WAF has the correct scope
        self.assertEqual(
            self.template_content['Resources']['WAFv2WebACLCLOUDFRONT']['Properties']['Scope'], 
            'CLOUDFRONT'
        )
        
        # Check that the Regional WAF exists and is not conditional
        self.assertIn('RegionalWebACL', self.template_content['Resources'])
        self.assertNotIn('Condition', self.template_content['Resources']['RegionalWebACL'])
        
        # Check that the Regional WAF has the correct scope
        self.assertEqual(
            self.template_content['Resources']['RegionalWebACL']['Properties']['Scope'], 
            'REGIONAL'
        )
        
        # Check that the CloudFront distribution conditionally uses the WAF
        cloudfront_resource = self.template_content['Resources']['CloudFrontDistribution']
        self.assertIn('WebACLId', cloudfront_resource['Properties']['DistributionConfig'])
        
        # The WebACLId should be a conditional expression
        webacl_id = cloudfront_resource['Properties']['DistributionConfig']['WebACLId']
        self.assertIsInstance(webacl_id, dict)
        self.assertIn('Fn::If', webacl_id) or self.assertIn('!If', webacl_id)
        
    def test_cloudfront_viewer_certificate_configuration(self):
        """Test that the CloudFront ViewerCertificate is configured correctly."""
        # Get the CloudFront distribution resource
        cloudfront_resource = self.template_content['Resources']['CloudFrontDistribution']
        self.assertIn('ViewerCertificate', cloudfront_resource['Properties']['DistributionConfig'])
        
        viewer_certificate = cloudfront_resource['Properties']['DistributionConfig']['ViewerCertificate']
        
        # Check that we have the CloudFrontDefaultCertificate property
        self.assertIn('CloudFrontDefaultCertificate', viewer_certificate)
        
        # If CloudFrontDefaultCertificate is true, SslSupportMethod should not be present
        if viewer_certificate['CloudFrontDefaultCertificate'] is True:
            self.assertNotIn('SslSupportMethod', viewer_certificate, 
                            "SslSupportMethod should not be present when CloudFrontDefaultCertificate is true")
            self.assertNotIn('AcmCertificateArn', viewer_certificate,
                            "AcmCertificateArn should not be present when CloudFrontDefaultCertificate is true")
            self.assertNotIn('IamCertificateId', viewer_certificate,
                            "IamCertificateId should not be present when CloudFrontDefaultCertificate is true")
        # If CloudFrontDefaultCertificate is false, SslSupportMethod must be present along with a certificate
        else:
            self.assertIn('SslSupportMethod', viewer_certificate,
                         "SslSupportMethod must be present when CloudFrontDefaultCertificate is false")
            self.assertTrue(
                'AcmCertificateArn' in viewer_certificate or 'IamCertificateId' in viewer_certificate,
                "Either AcmCertificateArn or IamCertificateId must be present when CloudFrontDefaultCertificate is false"
            )
            
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
        self.assertEqual(bucket_policy['Properties']['Bucket']['Ref'], 'S3BucketFlatstonesolutionsuseast1')
        
        # Check that the policy document has the correct structure
        policy_doc = bucket_policy['Properties']['PolicyDocument']
        self.assertEqual(policy_doc['Version'], '2008-10-17')
        self.assertEqual(policy_doc['Id'], 'PolicyForCloudFrontPrivateContent')
        
        # Check the statement
        statement = policy_doc['Statement'][0]
        self.assertEqual(statement['Sid'], 'AllowCloudFrontServicePrincipal')
        self.assertEqual(statement['Effect'], 'Allow')
        self.assertEqual(statement['Principal']['Service'], 'cloudfront.amazonaws.com')
        self.assertEqual(statement['Action'], 's3:GetObject')
        
        # Check the resource pattern
        self.assertIn('Resource', statement)
        
        # Check the condition - should use StringLike to support multiple distributions
        self.assertIn('Condition', statement)
        self.assertIn('StringLike', statement['Condition'])
        self.assertIn('AWS:SourceArn', statement['Condition']['StringLike'])
        
    def test_cloudfront_distribution_id_output(self):
        """Test that the CloudFront distribution ID is included in the outputs."""
        # Check that the CloudFrontDistributionId output exists
        self.assertIn('CloudFrontDistributionId', self.template_content['Outputs'])
        
        # Check that it references the CloudFront distribution
        output = self.template_content['Outputs']['CloudFrontDistributionId']
        self.assertIn('Value', output)
        self.assertIn('Ref', output['Value'])
        self.assertEqual(output['Value']['Ref'], 'CloudFrontDistribution')

if __name__ == '__main__':
    unittest.main()












