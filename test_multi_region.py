#!/usr/bin/env python3
"""
Test script to verify the multi-region CloudFront distribution fix.
This script simulates adding multiple CloudFront distributions to an S3 bucket policy.
"""

import json
import boto3
from unittest.mock import MagicMock, patch
import aws_infra_report

def test_multi_region_bucket_policy():
    """Test that the bucket policy can handle multiple CloudFront distributions."""
    print("Testing multi-region bucket policy functionality...")
    
    # Create a mock S3 client
    mock_s3 = MagicMock()
    
    # Patch boto3.client to return our mock
    with patch('boto3.client', return_value=mock_s3):
        # First, simulate no existing policy
        mock_s3.get_bucket_policy.side_effect = mock_s3.exceptions.NoSuchBucketPolicy({}, 'GetBucketPolicy')
        
        # Add first CloudFront distribution
        print("\n1. Adding first CloudFront distribution...")
        aws_infra_report.attach_bucket_policy(
            'test-bucket', 
            'us-east-1',
            'arn:aws:cloudfront::123456789012:distribution/DISTRIBUTION1'
        )
        
        # Get the policy that was set
        args, kwargs = mock_s3.put_bucket_policy.call_args
        policy1 = json.loads(kwargs['Policy'])
        print(f"Policy after first distribution:\n{json.dumps(policy1, indent=2)}")
        
        # Reset mock and set up existing policy
        mock_s3.reset_mock()
        mock_s3.get_bucket_policy.side_effect = None
        mock_s3.get_bucket_policy.return_value = {'Policy': json.dumps(policy1)}
        
        # Add second CloudFront distribution
        print("\n2. Adding second CloudFront distribution...")
        aws_infra_report.attach_bucket_policy(
            'test-bucket', 
            'us-west-2',
            'arn:aws:cloudfront::123456789012:distribution/DISTRIBUTION2'
        )
        
        # Get the updated policy
        args, kwargs = mock_s3.put_bucket_policy.call_args
        policy2 = json.loads(kwargs['Policy'])
        print(f"Policy after second distribution:\n{json.dumps(policy2, indent=2)}")
        
        # Verify the policy has both distributions
        statement = policy2['Statement'][0]
        condition = statement.get('Condition', {})
        
        if 'StringLike' in condition and 'AWS:SourceArn' in condition['StringLike']:
            arns = condition['StringLike']['AWS:SourceArn']
            if isinstance(arns, list) and len(arns) == 2:
                print("\nSUCCESS: Policy correctly includes both CloudFront distributions!")
            else:
                print("\nFAILURE: Policy does not correctly include both distributions.")
        else:
            print("\nFAILURE: Policy does not use StringLike condition as expected.")

if __name__ == "__main__":
    test_multi_region_bucket_policy()