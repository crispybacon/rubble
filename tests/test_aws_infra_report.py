#!/usr/bin/env python3
"""
Unit tests for the AWS Infrastructure Report Tool
"""

import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import the main script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aws_infra_report
from deploy_function import attach_bucket_policy, export_deployed_template, load_cloudformation_yaml


class TestAWSInfraReport(unittest.TestCase):
    """Test cases for AWS Infrastructure Report Tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_config = {
            'region': 'us-west-2',
            'output': {
                'report_dir': 'test_reports',
                'report_prefix': 'test_report'
            },
            's3': {
                'bucket': 'test-bucket'
            },
            'tags': {
                'organization': 'flatstone services',
                'business_unit': 'marketing',
                'environment': 'dev'
            }
        }
        
        # Create test reports directory
        Path('test_reports').mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up after tests."""
        # Clean up test files
        for file in Path('test_reports').glob('test_report_*.json'):
            file.unlink()
        
        # Try to remove the directory (will only succeed if empty)
        try:
            Path('test_reports').rmdir()
        except:
            pass

    @patch('aws_infra_report.load_config')
    def test_load_config(self, mock_load_config):
        """Test loading configuration from file."""
        mock_load_config.return_value = self.test_config
        config = aws_infra_report.load_config('dummy_path')
        self.assertEqual(config['region'], 'us-west-2')
        self.assertEqual(config['output']['report_dir'], 'test_reports')

    def test_calculate_costs(self):
        """Test cost calculation function."""
        # Test with valid spot price
        costs = aws_infra_report.calculate_costs(0.1234)
        self.assertEqual(costs['hourly'], 0.1234)
        self.assertAlmostEqual(costs['monthly'], 90.06, places=2)
        
        # Test with None spot price
        costs = aws_infra_report.calculate_costs(None)
        self.assertIsNone(costs['hourly'])
        self.assertIsNone(costs['monthly'])

    @patch('boto3.client')
    def test_get_spot_price(self, mock_boto_client):
        """Test getting spot price for an instance."""
        # Mock EC2 client
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        
        # Mock instance details
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-12345',
                    'InstanceType': 't2.micro',
                    'Placement': {'AvailabilityZone': 'us-west-2a'}
                }]
            }]
        }
        
        # Mock spot price history
        mock_ec2.describe_spot_price_history.return_value = {
            'SpotPriceHistory': [{'SpotPrice': '0.0123'}]
        }
        
        # Test the function
        spot_price = aws_infra_report.get_spot_price(mock_ec2, 'i-12345')
        self.assertEqual(spot_price, 0.0123)
        
        # Test with empty spot price history
        mock_ec2.describe_spot_price_history.return_value = {'SpotPriceHistory': []}
        spot_price = aws_infra_report.get_spot_price(mock_ec2, 'i-12345')
        self.assertIsNone(spot_price)
        
    @patch('boto3.client')
    def test_get_instance_details(self, mock_boto_client):
        """Test getting instance details with and without tags."""
        # Mock EC2 client
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        
        # Mock instance details with tags
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-12345',
                    'InstanceType': 't2.micro',
                    'State': {'Name': 'running'},
                    'Placement': {'AvailabilityZone': 'us-west-2a'},
                    'LaunchTime': datetime.now(),
                    'Tags': [
                        {'Key': 'Name', 'Value': 'test-instance'},
                        {'Key': 'environment', 'Value': 'test'}
                    ]
                }]
            }]
        }
        
        # Test with existing tags
        details = aws_infra_report.get_instance_details(mock_ec2, 'i-12345', self.test_config)
        self.assertEqual(details['InstanceId'], 'i-12345')
        self.assertEqual(details['InstanceType'], 't2.micro')
        self.assertEqual(details['State'], 'running')
        self.assertEqual(details['Tags']['Name'], 'test-instance')
        # The instance tag should take precedence over the config tag
        self.assertEqual(details['Tags']['environment'], 'test')
        # Config tags should be added if not present on the instance
        self.assertEqual(details['Tags']['organization'], 'flatstone services')
        self.assertEqual(details['Tags']['business_unit'], 'marketing')
        
        # Mock instance details without tags
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-67890',
                    'InstanceType': 't2.small',
                    'State': {'Name': 'stopped'},
                    'Placement': {'AvailabilityZone': 'us-west-2b'},
                    'LaunchTime': datetime.now()
                    # No Tags
                }]
            }]
        }
        
        # Test without tags
        details = aws_infra_report.get_instance_details(mock_ec2, 'i-67890', self.test_config)
        self.assertEqual(details['InstanceId'], 'i-67890')
        self.assertEqual(details['InstanceType'], 't2.small')
        self.assertEqual(details['State'], 'stopped')
        # All config tags should be added
        self.assertEqual(details['Tags']['organization'], 'flatstone services')
        self.assertEqual(details['Tags']['business_unit'], 'marketing')
        self.assertEqual(details['Tags']['environment'], 'dev')

    def test_generate_report(self):
        """Test report generation."""
        instances_data = [
            {
                'InstanceId': 'i-12345',
                'InstanceType': 't2.micro',
                'State': 'running',
                'AvailabilityZone': 'us-west-2a',
                'LaunchTime': '2023-01-01T00:00:00',
                'SpotPrice': 0.0123,
                'Costs': {'hourly': 0.0123, 'monthly': 9.01}
            },
            {
                'InstanceId': 'i-67890',
                'InstanceType': 't2.small',
                'State': 'stopped',
                'AvailabilityZone': 'us-west-2b',
                'LaunchTime': '2023-01-02T00:00:00',
                'SpotPrice': None,
                'Costs': {'hourly': None, 'monthly': None}
            },
            {
                'InstanceId': 'i-abcde',
                'InstanceType': 't2.medium',
                'State': 'terminated',
                'AvailabilityZone': 'us-west-2c',
                'LaunchTime': '2023-01-03T00:00:00',
                'SpotPrice': 0.0456,
                'Costs': {'hourly': 0.0456, 'monthly': 33.42}
            }
        ]
        
        report = aws_infra_report.generate_report('us-west-2', instances_data)
        
        self.assertEqual(report['region'], 'us-west-2')
        self.assertEqual(report['summary']['total_instances'], 3)
        self.assertEqual(report['summary']['running_instances'], 1)
        # Verify that terminated instances are excluded from cost calculations
        self.assertEqual(report['summary']['total_hourly_cost'], 0.0123)
        self.assertEqual(report['summary']['total_monthly_cost'], 9.01)

    @patch('json.dump')
    def test_save_report(self, mock_json_dump):
        """Test saving report to file."""
        report = {'test': 'data'}
        
        with patch('builtins.open', unittest.mock.mock_open()) as mock_open:
            filepath = aws_infra_report.save_report(report, 'test_reports', 'test_report')
            
            # Check that the file was opened for writing
            mock_open.assert_called_once()
            
            # Check that json.dump was called with the report
            mock_json_dump.assert_called_once()
            args, _ = mock_json_dump.call_args
            self.assertEqual(args[0], report)

    @patch('boto3.client')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('pathlib.Path.glob')
    @patch('pathlib.Path.is_file')
    @patch('pathlib.Path.relative_to')
    @patch('pathlib.Path.__truediv__')  # Mock the / operator for Path
    @patch('builtins.open', unittest.mock.mock_open(read_data='test data'))
    def test_upload_static_website(self, mock_truediv, mock_relative_to, mock_is_file, mock_glob, mock_is_dir, mock_exists, mock_boto_client):
        """Test uploading static website to S3."""
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        
        # Mock Path methods
        mock_exists.return_value = True
        mock_is_dir.return_value = True
        
        # Mock the content directory
        mock_content_dir = MagicMock()
        mock_truediv.return_value = mock_content_dir
        
        # Mock file paths
        mock_file1 = MagicMock()
        mock_file1.suffix = '.html'
        mock_file1.name = 'index.html'
        mock_file1.__str__.return_value = 'iac/static_website/content/index.html'
        
        mock_file2 = MagicMock()
        mock_file2.suffix = '.css'
        mock_file2.name = 'index.css'
        mock_file2.__str__.return_value = 'iac/static_website/content/index.css'
        
        mock_file3 = MagicMock()
        mock_file3.suffix = '.png'
        mock_file3.name = 'me.png'
        mock_file3.__str__.return_value = 'iac/static_website/content/me.png'
        
        # CloudFormation template that should be skipped
        mock_file4 = MagicMock()
        mock_file4.suffix = '.yaml'
        mock_file4.name = 'cloudformation-template.yaml'
        mock_file4.__str__.return_value = 'iac/static_website/cloudformation-template.yaml'
        
        mock_glob.return_value = [mock_file1, mock_file2, mock_file3, mock_file4]
        mock_is_file.return_value = True
        
        # Mock relative_to to return the filename
        mock_relative_to.side_effect = lambda x: Path(str(mock_relative_to._mock_self).split('/')[-1])
        
        # Test the function
        result = aws_infra_report.upload_static_website('test-bucket', 'us-west-2')
        
        # Check that the function returned True (success)
        self.assertTrue(result)
        
        # Check that put_object was called for each file except the CloudFormation template
        self.assertEqual(mock_s3.put_object.call_count, 3)
        
        # Check content types were set correctly
        content_types = [call[1].get('ContentType') for call in mock_s3.put_object.call_args_list]
        self.assertIn('text/html', content_types)
        self.assertIn('text/css', content_types)
        self.assertIn('image/png', content_types)
        
        # Check that files are uploaded to the root of the bucket (no static_website prefix)
        keys = [call[1].get('Key') for call in mock_s3.put_object.call_args_list]
        for key in keys:
            self.assertFalse(key.startswith('static_website/'), f"Key '{key}' should not start with 'static_website/'")

    @patch('boto3.client')
    @patch('aws_infra_report.load_config')
    def test_deploy_cloudformation_template(self, mock_load_config, mock_boto_client):
        """Test deploying a CloudFormation template."""
        # Mock configuration
        mock_load_config.return_value = {
            'solutions': {
                'static_website': {
                    'template_path': 'iac/static_website/template.yaml',
                    'deployed_dir': 'iac/deployed',
                    'parameters': {
                        'BucketNamePrefix': 'test-bucket',
                        'OriginShieldRegion': 'us-west-2'
                    }
                }
            },
            'tags': {
                'organization': 'flatstone services',
                'business_unit': 'marketing',
                'environment': 'dev'
            }
        }
        
        # Mock CloudFormation client
        mock_cfn = MagicMock()
        mock_boto_client.return_value = mock_cfn
        
        # Mock stack creation
        mock_cfn.describe_stacks.side_effect = mock_cfn.exceptions.ClientError(
            {'Error': {'Code': 'ValidationError', 'Message': 'Stack does not exist'}},
            'DescribeStacks'
        )
        
        # Mock successful stack creation
        mock_cfn.create_stack.return_value = {'StackId': 'test-stack-id'}
        
        # Mock stack outputs
        mock_cfn.describe_stacks.side_effect = None
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'Outputs': [
                    {'OutputKey': 'CloudFrontDistributionDomainName', 'OutputValue': 'test.cloudfront.net'},
                    {'OutputKey': 'S3BucketName', 'OutputValue': 'test-bucket-us-west-2'}
                ]
            }]
        }
        
        # Mock file operations
        with patch('builtins.open', unittest.mock.mock_open(read_data='test template')):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.mkdir'):
                    # Test the function
                    result = aws_infra_report.deploy_cloudformation_template(
                        'static_website', 'test-stack', 'us-west-2', 
                        mock_load_config.return_value, False
                    )
        
        # Check the result
        self.assertEqual(result['status'], 'success')
        self.assertIn('outputs', result)
        self.assertEqual(result['outputs']['CloudFrontDistributionDomainName'], 'test.cloudfront.net')
        
        # Verify CloudFormation client was called correctly
        mock_boto_client.assert_called_with('cloudformation', region_name='us-west-2')
        mock_cfn.create_stack.assert_called_once()
        
        # Verify that the tag parameters were included
        call_args = mock_cfn.create_stack.call_args[1]
        parameters = call_args['Parameters']
        
        # Extract parameters into a dict for easier checking
        param_dict = {p['ParameterKey']: p['ParameterValue'] for p in parameters}
        
        self.assertEqual(param_dict['OrganizationTag'], 'flatstone services')
        self.assertEqual(param_dict['BusinessUnitTag'], 'marketing')
        self.assertEqual(param_dict['EnvironmentTag'], 'dev')
        

        
    @patch('deploy_function.attach_bucket_policy')
    @patch('boto3.client')
    @patch('aws_infra_report.parse_arguments')
    @patch('aws_infra_report.load_config')
    def test_main_with_attach_bucket_policy(self, mock_load_config, mock_parse_arguments, mock_boto_client, mock_attach_bucket_policy):
        """Test main function with attach_bucket_policy option."""
        # Mock arguments
        mock_args = MagicMock()
        mock_args.attach_bucket_policy = True
        mock_args.s3_bucket = 'test-bucket'
        mock_args.region = 'us-west-2'
        mock_args.cloudfront_distribution_id = 'E3V5CI7VI4S0QQ'
        mock_args.deploy = None
        mock_args.upload_resume = False
        mock_parse_arguments.return_value = mock_args
        
        # Mock config
        mock_load_config.return_value = self.test_config
        
        # Mock CloudFront client
        mock_cf = MagicMock()
        mock_boto_client.return_value = mock_cf
        
        # Mock get_distribution response
        mock_cf.get_distribution.return_value = {
            'Distribution': {
                'ARN': 'arn:aws:cloudfront::851002115632:distribution/E3V5CI7VI4S0QQ'
            }
        }
        
        # Mock attach_bucket_policy to return True (success)
        mock_attach_bucket_policy.return_value = True
        
        # Test the function
        with patch('sys.exit') as mock_exit:
            aws_infra_report.main()
            
            # Check that attach_bucket_policy was called with the correct arguments
            mock_attach_bucket_policy.assert_called_once_with(
                'test-bucket', 
                'us-west-2', 
                'arn:aws:cloudfront::851002115632:distribution/E3V5CI7VI4S0QQ'
            )
            
            # Check that sys.exit was not called (indicating success)
            mock_exit.assert_not_called()


    @patch('aws_infra_report.upload_static_website')
    @patch('aws_infra_report.load_config')
    @patch('aws_infra_report.parse_arguments')
    def test_main_with_upload_resume(self, mock_parse_arguments, mock_load_config, mock_upload_static_website):
        """Test main function with upload_resume option."""
        # Mock arguments
        mock_args = MagicMock()
        mock_args.upload_resume = True
        mock_args.s3_bucket = None
        mock_args.region = None
        mock_args.deploy = None
        mock_args.export_template = False
        mock_parse_arguments.return_value = mock_args
        
        # Mock config
        mock_load_config.return_value = self.test_config
        
        # Mock upload function to return True (success)
        mock_upload_static_website.return_value = True
        
        # Test the function
        with patch('aws_infra_report.boto3.client'), \
             patch('aws_infra_report.get_instance_details'), \
             patch('aws_infra_report.get_spot_price'), \
             patch('aws_infra_report.generate_report'), \
             patch('aws_infra_report.save_report'), \
             patch('aws_infra_report.display_report'):
            aws_infra_report.main()
        
        # Check that upload_static_website was called with the correct arguments
        mock_upload_static_website.assert_called_once_with('test-bucket', 'us-west-2', self.test_config)
        
    @patch('aws_infra_report.deploy_cloudformation_template')
    @patch('update_website.update_index_html')
    @patch('update_website.add_messaging_to_solution_demos')
    @patch('aws_infra_report.upload_static_website')
    @patch('aws_infra_report.load_config')
    @patch('aws_infra_report.parse_arguments')
    def test_main_with_messaging_deploy(self, mock_parse_arguments, mock_load_config, 
                                       mock_upload_static_website, mock_add_messaging, 
                                       mock_update_index, mock_deploy_cloudformation):
        """Test main function with messaging solution deployment."""
        # Mock arguments
        mock_args = MagicMock()
        mock_args.upload_resume = False
        mock_args.region = 'us-west-2'
        mock_args.deploy = 'messaging'
        mock_args.stack_name = 'test-messaging-stack'
        mock_args.static_website_stack = 'test-static-website-stack'
        mock_args.export_template = False
        mock_args.update = False
        mock_args.attach_bucket_policy = False
        mock_parse_arguments.return_value = mock_args
        
        # Mock config
        mock_load_config.return_value = {
            'region': 'us-west-2',
            's3': {'bucket': 'test-bucket'},
            'solutions': {
                'messaging': {
                    'template_path': 'iac/messaging/template.yaml',
                    'parameters': None  # Test with None parameters
                }
            }
        }
        
        # Mock deploy function to return success with API endpoint
        mock_deploy_cloudformation.return_value = {
            'status': 'success',
            'message': 'Stack create completed successfully!',
            'outputs': {
                'ApiEndpoint': 'https://api.example.com/prod/contact'
            }
        }
        
        # Mock update_index_html and add_messaging_to_solution_demos to return True
        mock_update_index.return_value = True
        mock_add_messaging.return_value = True
        
        # Mock upload_static_website to return True
        mock_upload_static_website.return_value = True
        
        # Test the function
        with patch('aws_infra_report.boto3.client'), \
             patch('aws_infra_report.get_instance_details'), \
             patch('aws_infra_report.get_spot_price'), \
             patch('aws_infra_report.generate_report'), \
             patch('aws_infra_report.save_report'), \
             patch('aws_infra_report.display_report'):
            aws_infra_report.main()
        
        # Check that deploy_cloudformation_template was called with the correct arguments
        mock_deploy_cloudformation.assert_called_once()
        call_args = mock_deploy_cloudformation.call_args[0]
        self.assertEqual(call_args[0], 'messaging')
        self.assertEqual(call_args[1], 'test-messaging-stack')
        self.assertEqual(call_args[2], 'us-west-2')
        
        # Check that the StaticWebsiteStackName parameter was added to the config
        config_arg = mock_deploy_cloudformation.call_args[0][3]
        self.assertEqual(
            config_arg['solutions']['messaging']['parameters']['StaticWebsiteStackName'],
            'test-static-website-stack'
        )
        
        # Check that update_index_html was called with the correct arguments
        mock_update_index.assert_called_once_with(
            'https://api.example.com/prod/contact', config_arg
        )
        
        # Check that add_messaging_to_solution_demos was called
        mock_add_messaging.assert_called_once_with(config_arg)
        
        # Check that upload_static_website was called with the correct arguments
        mock_upload_static_website.assert_called_once_with(
            'test-bucket', 'us-west-2', config_arg
        )
        
    @patch('aws_infra_report.deploy_cloudformation_template')
    @patch('update_website.add_streaming_media_to_solution_demos')
    @patch('update_website.add_streaming_media_buttons')
    @patch('aws_infra_report.upload_static_website')
    @patch('aws_infra_report.load_config')
    @patch('aws_infra_report.parse_arguments')
    def test_main_with_streaming_media_deploy(self, mock_parse_arguments, mock_load_config, 
                                           mock_upload_static_website, mock_add_buttons, 
                                           mock_add_solution_demos, mock_deploy_cloudformation):
        """Test main function with streaming media solution deployment."""
        # Mock arguments
        mock_args = MagicMock()
        mock_args.upload_resume = False
        mock_args.region = 'us-west-2'
        mock_args.deploy = 'streaming_media'
        mock_args.stack_name = 'test-streaming-media-stack'
        mock_args.static_website_stack = 'test-static-website-stack'
        mock_args.export_template = False
        mock_args.update = False
        mock_args.attach_bucket_policy = False
        mock_parse_arguments.return_value = mock_args
        
        # Mock config
        mock_load_config.return_value = {
            'region': 'us-west-2',
            's3': {'bucket': 'test-bucket'},
            'solutions': {
                'streaming_media': {
                    'template_path': 'iac/streaming_media/template.yaml',
                    'parameters': {
                        'LiveInputType': 'RTMP_PUSH',
                        'LiveInputWhitelistCidr': '0.0.0.0/0'
                    }
                }
            }
        }
        
        # Mock deploy function to return success with streaming endpoints
        mock_deploy_cloudformation.return_value = {
            'status': 'success',
            'message': 'Stack create completed successfully!',
            'outputs': {
                'HlsEndpointUrl': 'https://example.com/hls/index.m3u8',
                'DashEndpointUrl': 'https://example.com/dash/index.mpd',
                'MediaLiveInputUrl': 'rtmp://example.com/live',
                'VodBucketName': 'test-vod-bucket'
            }
        }
        
        # Mock add_streaming_media_to_solution_demos and add_streaming_media_buttons to return True
        mock_add_solution_demos.return_value = True
        mock_add_buttons.return_value = True
        
        # Mock upload_static_website to return True
        mock_upload_static_website.return_value = True
        
        # Test the function
        with patch('aws_infra_report.boto3.client'), \
             patch('aws_infra_report.get_instance_details'), \
             patch('aws_infra_report.get_spot_price'), \
             patch('aws_infra_report.generate_report'), \
             patch('aws_infra_report.save_report'), \
             patch('aws_infra_report.display_report'), \
             patch('update_website.get_streaming_endpoints') as mock_get_endpoints:
            
            # Mock get_streaming_endpoints to return the streaming endpoints
            mock_get_endpoints.return_value = {
                'hls': 'https://example.com/hls/index.m3u8',
                'dash': 'https://example.com/dash/index.mpd',
                'input': 'rtmp://example.com/live',
                'vod': 'test-vod-bucket'
            }
            
            aws_infra_report.main()
        
        # Check that deploy_cloudformation_template was called with the correct arguments
        mock_deploy_cloudformation.assert_called_once()
        call_args = mock_deploy_cloudformation.call_args[0]
        self.assertEqual(call_args[0], 'streaming_media')
        self.assertEqual(call_args[1], 'test-streaming-media-stack')
        self.assertEqual(call_args[2], 'us-west-2')
        
        # Check that the StaticWebsiteStackName parameter was added to the config
        config_arg = mock_deploy_cloudformation.call_args[0][3]
        self.assertEqual(
            config_arg['solutions']['streaming_media']['parameters']['StaticWebsiteStackName'],
            'test-static-website-stack'
        )
        
        # Check that add_streaming_media_to_solution_demos was called
        mock_add_solution_demos.assert_called_once_with(config_arg)
        
        # Check that add_streaming_media_buttons was called with the correct arguments
        mock_add_buttons.assert_called_once()
        buttons_call_args = mock_add_buttons.call_args[0]
        self.assertEqual(buttons_call_args[0]['hls'], 'https://example.com/hls/index.m3u8')
        self.assertEqual(buttons_call_args[0]['dash'], 'https://example.com/dash/index.mpd')
        self.assertEqual(buttons_call_args[0]['input'], 'rtmp://example.com/live')
        self.assertEqual(buttons_call_args[0]['vod'], 'test-vod-bucket')
        
        # Check that upload_static_website was called with the correct arguments
        mock_upload_static_website.assert_called_once_with(
            'test-bucket', 'us-west-2', config_arg
        )
        
    @patch('aws_infra_report.load_config')
    @patch('aws_infra_report.parse_arguments')
    def test_main_with_messaging_deploy_missing_static_website_stack(self, mock_parse_arguments, mock_load_config):
        """Test main function with messaging solution deployment but missing static_website_stack parameter."""
        # Mock arguments
        mock_args = MagicMock()
        mock_args.upload_resume = False
        mock_args.region = 'us-west-2'
        mock_args.deploy = 'messaging'
        mock_args.stack_name = 'test-messaging-stack'
        mock_args.static_website_stack = None  # Missing static_website_stack
        mock_args.export_template = False
        mock_args.update = False
        mock_args.attach_bucket_policy = False
        mock_parse_arguments.return_value = mock_args
        
        # Mock config
        mock_load_config.return_value = {
            'region': 'us-west-2',
            's3': {'bucket': 'test-bucket'},
            'solutions': {
                'messaging': {
                    'template_path': 'iac/messaging/template.yaml'
                }
            }
        }
        
        # Test the function - should exit with error
        with patch('sys.exit') as mock_exit, \
             patch('builtins.print') as mock_print:
            aws_infra_report.main()
            
            # Check that sys.exit was called with error code 1
            mock_exit.assert_called_once_with(1)
            
            # Check that the error message was printed
            mock_print.assert_any_call("Error: Static website stack name is required when deploying messaging solution. Please provide it via --static_website_stack option.")
        )


    @patch('aws_infra_report.load_config')
    @patch('aws_infra_report.parse_arguments')
    def test_main_with_streaming_media_deploy_missing_static_website_stack(self, mock_parse_arguments, mock_load_config):
        """Test main function with streaming media solution deployment but missing static_website_stack parameter."""
        # Mock arguments
        mock_args = MagicMock()
        mock_args.upload_resume = False
        mock_args.region = 'us-west-2'
        mock_args.deploy = 'streaming_media'
        mock_args.stack_name = 'test-streaming-media-stack'
        mock_args.static_website_stack = None  # Missing static_website_stack
        mock_args.export_template = False
        mock_args.update = False
        mock_args.attach_bucket_policy = False
        mock_parse_arguments.return_value = mock_args
        
        # Mock config
        mock_load_config.return_value = {
            'region': 'us-west-2',
            's3': {'bucket': 'test-bucket'},
            'solutions': {
                'streaming_media': {
                    'template_path': 'iac/streaming_media/template.yaml',
                    'parameters': {
                        'LiveInputType': 'RTMP_PUSH',
                        'LiveInputWhitelistCidr': '0.0.0.0/0'
                    }
                }
            }
        }
        
        # Test the function - should exit with error
        with patch('sys.exit') as mock_exit, \
             patch('builtins.print') as mock_print:
            aws_infra_report.main()
            
            # Check that sys.exit was called with error code 1
            mock_exit.assert_called_once_with(1)
            
            # Check that the error message was printed
            mock_print.assert_any_call("Error: Static website stack name is required when deploying streaming media solution. Please provide it via --static_website_stack option.")
        )


if __name__ == '__main__':
    unittest.main()








