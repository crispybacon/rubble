#!/usr/bin/env python3
"""
Unit tests for the Update Website Script
"""

import unittest
import sys
import os
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add parent directory to path to import the script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import update_website


class TestUpdateWebsite(unittest.TestCase):
    """Test cases for Update Website Script."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_config = {
            'solutions': {
                'static_website': {
                    'content_dir': 'test_content'
                }
            }
        }
        
        # Create a temporary directory for test content
        self.temp_dir = tempfile.TemporaryDirectory()
        self.content_path = Path(self.temp_dir.name)
        
        # Create a test index.html file
        self.test_html = """<!DOCTYPE html>
<html>
<head>
  <title>Test Page</title>
</head>
<body>
  <script>
    document.addEventListener('DOMContentLoaded', function() {
      fetch('${ApiEndpoint}', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          messageType: 'email',
          message: 'Test message'
        })
      });
    });
  </script>
  <div class="solutionDemos">
    <h2>
      Solution Demonstrations
    </h2>
    <ul>
      <li>
        <div class="jobPosition">
          <span class="bolded">
            Static Website
          </span>
          <span>
            AWS CloudFormation
          </span>
        </div>
        <div class="job-content">
          <div class="projectName bolded">
            <span>
              Professional Resume/Portfolio Website
            </span>
          </div>
          <div class="smallText">
            <p>
              A responsive static website hosted on AWS S3 and delivered globally via CloudFront with WAF protection.
            </p>
          </div>
        </div>
      </li>
    </ul>
  </div>
</body>
</html>"""
        
        # Write the test HTML to a file
        self.index_path = self.content_path / 'index.html'
        with open(self.index_path, 'w') as f:
            f.write(self.test_html)

    def tearDown(self):
        """Clean up after tests."""
        self.temp_dir.cleanup()

    @patch('boto3.client')
    def test_get_api_endpoint(self, mock_boto_client):
        """Test getting API endpoint from CloudFormation stack outputs."""
        # Mock CloudFormation client
        mock_cfn = MagicMock()
        mock_boto_client.return_value = mock_cfn
        
        # Mock describe_stacks response
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'Outputs': [
                    {'OutputKey': 'ApiEndpoint', 'OutputValue': 'https://api.example.com/prod/contact'}
                ]
            }]
        }
        
        # Test the function
        api_endpoint = update_website.get_api_endpoint('test-stack', 'us-west-2')
        self.assertEqual(api_endpoint, 'https://api.example.com/prod/contact')
        
        # Verify CloudFormation client was called correctly
        mock_boto_client.assert_called_with('cloudformation', region_name='us-west-2')
        mock_cfn.describe_stacks.assert_called_with(StackName='test-stack')
        
        # Test with missing ApiEndpoint
        mock_cfn.describe_stacks.return_value = {
            'Stacks': [{
                'Outputs': [
                    {'OutputKey': 'OtherOutput', 'OutputValue': 'some-value'}
                ]
            }]
        }
        
        api_endpoint = update_website.get_api_endpoint('test-stack', 'us-west-2')
        self.assertIsNone(api_endpoint)
        
        # Test with exception
        mock_cfn.describe_stacks.side_effect = Exception('Test exception')
        api_endpoint = update_website.get_api_endpoint('test-stack', 'us-west-2')
        self.assertIsNone(api_endpoint)

    def test_update_index_html(self):
        """Test updating index.html with API endpoint."""
        # Override the content_dir in the test config
        self.test_config['solutions']['static_website']['content_dir'] = str(self.content_path)
        
        # Test the function
        api_endpoint = 'https://api.example.com/prod/contact'
        result = update_website.update_index_html(api_endpoint, self.test_config)
        
        # Check that the function returned True (success)
        self.assertTrue(result)
        
        # Read the updated file
        with open(self.index_path, 'r') as f:
            updated_content = f.read()
        
        # Check that the API endpoint was updated
        self.assertIn(f"fetch('{api_endpoint}'", updated_content)
        self.assertNotIn("fetch('${ApiEndpoint}'", updated_content)
        
        # Test with non-existent content directory
        self.test_config['solutions']['static_website']['content_dir'] = 'non_existent_dir'
        
        # Create a backup of the original index.html
        with open(self.index_path, 'r') as f:
            original_content = f.read()
        
        # Create a new index.html in the parent directory
        parent_index_path = Path('iac/static_website/index.html')
        os.makedirs(os.path.dirname(parent_index_path), exist_ok=True)
        with open(parent_index_path, 'w') as f:
            f.write(self.test_html)
        
        try:
            # Test the function with the parent directory
            result = update_website.update_index_html(api_endpoint, self.test_config)
            
            # Check that the function returned True (success)
            self.assertTrue(result)
            
            # Read the updated file
            with open(parent_index_path, 'r') as f:
                updated_content = f.read()
            
            # Check that the API endpoint was updated
            self.assertIn(f"fetch('{api_endpoint}'", updated_content)
            self.assertNotIn("fetch('${ApiEndpoint}'", updated_content)
        finally:
            # Clean up the parent index.html
            if parent_index_path.exists():
                os.remove(parent_index_path)
            
            # Restore the original index.html
            with open(self.index_path, 'w') as f:
                f.write(original_content)

    def test_add_messaging_to_solution_demos(self):
        """Test adding messaging solution to Solution Demonstrations section."""
        # Override the content_dir in the test config
        self.test_config['solutions']['static_website']['content_dir'] = str(self.content_path)
        
        # Test the function
        result = update_website.add_messaging_to_solution_demos(self.test_config)
        
        # Check that the function returned True (success)
        self.assertTrue(result)
        
        # Read the updated file
        with open(self.index_path, 'r') as f:
            updated_content = f.read()
        
        # Check that the messaging solution was added
        self.assertIn("AWS End User Messaging", updated_content)
        self.assertIn("SMS and Email Contact Forms", updated_content)
        
        # Test adding it again (should not duplicate)
        result = update_website.add_messaging_to_solution_demos(self.test_config)
        self.assertTrue(result)
        
        # Read the updated file
        with open(self.index_path, 'r') as f:
            updated_content = f.read()
        
        # Count occurrences of the messaging solution
        count = updated_content.count("AWS End User Messaging")
        self.assertEqual(count, 1, "Messaging solution should only appear once")
        
    @patch('update_website.parse_arguments')
    @patch('update_website.load_config')
    @patch('update_website.get_api_endpoint')
    @patch('update_website.update_index_html')
    @patch('update_website.add_messaging_to_solution_demos')
    def test_main_with_static_website_stack(self, mock_add_messaging, mock_update_index, 
                                           mock_get_api_endpoint, mock_load_config, mock_parse_arguments):
        """Test main function with static_website_stack parameter."""
        # Mock arguments
        mock_args = MagicMock()
        mock_args.config = 'config.yaml'
        mock_args.stack_name = 'test-messaging-stack'
        mock_args.static_website_stack = 'test-static-website-stack'
        mock_args.region = 'us-west-2'
        mock_parse_arguments.return_value = mock_args
        
        # Mock config
        mock_config = {
            'region': 'us-west-2',
            'solutions': {
                'static_website': {
                    'content_dir': 'test_content'
                }
            }
        }
        mock_load_config.return_value = mock_config
        
        # Mock API endpoint
        mock_get_api_endpoint.return_value = 'https://api.example.com/prod/contact'
        
        # Mock update functions to return True
        mock_update_index.return_value = True
        mock_add_messaging.return_value = True
        
        # Test the function
        with patch('sys.exit') as mock_exit:
            update_website.main()
            
            # Check that sys.exit was not called (indicating success)
            mock_exit.assert_not_called()
        
        # Check that get_api_endpoint was called with the correct arguments
        mock_get_api_endpoint.assert_called_once_with('test-messaging-stack', 'us-west-2')
        
        # Check that the static_website_stack parameter was added to the config
        self.assertEqual(
            mock_config['solutions']['messaging']['parameters']['StaticWebsiteStackName'],
            'test-static-website-stack'
        )
        
        # Check that update_index_html was called with the correct arguments
        mock_update_index.assert_called_once_with('https://api.example.com/prod/contact', mock_config)
        
        # Check that add_messaging_to_solution_demos was called with the correct arguments
        mock_add_messaging.assert_called_once_with(mock_config)
        self.assertEqual(count, 1, "Messaging solution should only appear once")


if __name__ == '__main__':
    unittest.main()