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
            }
        ]
        
        report = aws_infra_report.generate_report('us-west-2', instances_data)
        
        self.assertEqual(report['region'], 'us-west-2')
        self.assertEqual(report['summary']['total_instances'], 2)
        self.assertEqual(report['summary']['running_instances'], 1)
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


if __name__ == '__main__':
    unittest.main()