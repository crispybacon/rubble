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
        mock_upload_static_website.assert_called_once_with('test-bucket', 'us-west-2')


if __name__ == '__main__':
    unittest.main()
