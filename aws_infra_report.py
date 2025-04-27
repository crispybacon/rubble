#!/usr/bin/env python3
"""
AWS Infrastructure Report Tool

This script generates reports about deployed AWS infrastructure,
focusing on cost analysis for spot instances.
"""

import argparse
import boto3
import json
import os
import sys
import yaml
from datetime import datetime
from pathlib import Path


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='AWS Infrastructure Report Tool')
    parser.add_argument('--region', type=str, help='AWS region to scan')
    parser.add_argument('--config', type=str, default='config.yaml',
                        help='Path to configuration file')
    parser.add_argument('--upload_resume', action='store_true',
                        help='Upload static website content to S3 bucket')
    parser.add_argument('--s3_bucket', type=str,
                        help='S3 bucket name for resume upload (overrides config file)')
    return parser.parse_args()


def load_config(config_path):
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_path}' not found.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing configuration file: {e}")
        sys.exit(1)


def get_spot_price(ec2, instance_id):
    """
    Get the spot price for a specific instance.
    
    Args:
        ec2: boto3 EC2 client
        instance_id: EC2 instance ID
        
    Returns:
        Spot price as a float or None if not available
    """
    try:
        # Get instance details
        instance = ec2.describe_instances(InstanceIds=[instance_id])['Reservations'][0]['Instances'][0]
        az = instance['Placement']['AvailabilityZone']
        instance_type = instance['InstanceType']

        # Get spot price
        spot_price = ec2.describe_spot_price_history(
            InstanceTypes=[instance_type],
            AvailabilityZone=az,
            ProductDescriptions=['Linux/UNIX'],
            StartTime=datetime.utcnow(),
            MaxResults=1
        )

        if spot_price['SpotPriceHistory']:
            return float(spot_price['SpotPriceHistory'][0]['SpotPrice'])
        return None
    except Exception as e:
        print(f"Error getting spot price for instance {instance_id}: {e}")
        return None


def get_instance_details(ec2, instance_id):
    """Get detailed information about an EC2 instance."""
    try:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        
        # Extract relevant details
        details = {
            'InstanceId': instance_id,
            'InstanceType': instance['InstanceType'],
            'State': instance['State']['Name'],
            'AvailabilityZone': instance['Placement']['AvailabilityZone'],
            'LaunchTime': instance['LaunchTime'].isoformat(),
        }
        
        # Add tags if available
        if 'Tags' in instance:
            details['Tags'] = {tag['Key']: tag['Value'] for tag in instance['Tags']}
            
        return details
    except Exception as e:
        print(f"Error getting details for instance {instance_id}: {e}")
        return None


def calculate_costs(spot_price):
    """Calculate hourly and monthly costs based on spot price."""
    if spot_price is None:
        return {
            'hourly': None,
            'monthly': None
        }
    
    hourly = spot_price
    # Approximate monthly cost (30.44 days average per month)
    monthly = hourly * 24 * 30.44
    
    return {
        'hourly': round(hourly, 4),
        'monthly': round(monthly, 2)
    }


def generate_report(region, instances_data):
    """Generate a comprehensive report of the infrastructure."""
    report = {
        'timestamp': datetime.utcnow().isoformat(),
        'region': region,
        'instances': instances_data,
        'summary': {
            'total_instances': len(instances_data),
            'running_instances': sum(1 for i in instances_data if i['State'] == 'running'),
            'total_hourly_cost': sum(i['Costs']['hourly'] or 0 for i in instances_data if i['State'] != 'terminated'),
            'total_monthly_cost': sum(i['Costs']['monthly'] or 0 for i in instances_data if i['State'] != 'terminated')
        }
    }
    
    return report


def upload_static_website(s3_bucket, region, static_website_dir='iac/static_website'):
    """
    Upload static website content to an S3 bucket.
    
    Args:
        s3_bucket: Name of the S3 bucket
        region: AWS region
        static_website_dir: Directory containing static website files
        
    Returns:
        bool: True if upload was successful, False otherwise
    """
    try:
        # Initialize S3 client
        s3 = boto3.client('s3', region_name=region)
        
        # Check if the directory exists
        website_dir = Path(static_website_dir)
        if not website_dir.exists() or not website_dir.is_dir():
            print(f"Error: Static website directory '{static_website_dir}' not found.")
            return False
        
        # Check if the content directory exists, if not, use the main directory
        content_dir = website_dir / 'content'
        if content_dir.exists() and content_dir.is_dir():
            # Use the content subdirectory if it exists
            website_dir = content_dir
            print(f"Using content directory: {content_dir}")
        else:
            print(f"Content directory not found, using main directory: {website_dir}")
        
        # Check if the bucket exists
        try:
            s3.head_bucket(Bucket=s3_bucket)
        except Exception as e:
            print(f"Error: S3 bucket '{s3_bucket}' not accessible: {e}")
            return False
        
        # Upload all files in the directory, excluding CloudFormation templates
        file_count = 0
        for file_path in website_dir.glob('**/*'):
            if file_path.is_file():
                # Skip CloudFormation template files
                if file_path.suffix.lower() in ['.yaml', '.yml', '.json'] and 'cloudformation' in file_path.name.lower():
                    print(f"Skipping CloudFormation template: {file_path}")
                    continue
                
                # Calculate the relative path for the S3 key
                relative_path = file_path.relative_to(website_dir)
                s3_key = f"static_website/{relative_path}"
                
                # Determine content type based on file extension
                content_type = 'application/octet-stream'  # Default
                if file_path.suffix == '.html':
                    content_type = 'text/html'
                elif file_path.suffix == '.css':
                    content_type = 'text/css'
                elif file_path.suffix in ['.jpg', '.jpeg']:
                    content_type = 'image/jpeg'
                elif file_path.suffix == '.png':
                    content_type = 'image/png'
                
                # Upload the file
                print(f"Uploading {file_path} to s3://{s3_bucket}/{s3_key}")
                with open(file_path, 'rb') as file_data:
                    s3.put_object(
                        Bucket=s3_bucket,
                        Key=s3_key,
                        Body=file_data,
                        ContentType=content_type
                    )
                file_count += 1
        
        print(f"Successfully uploaded {file_count} files to s3://{s3_bucket}/static_website/")
        return True
    except Exception as e:
        print(f"Error uploading static website content: {e}")
        return False


def save_report(report, output_dir, prefix):
    """Save the report to a JSON file."""
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # Write report to file
    with open(filepath, 'w') as f:
        json.dump(report, f, indent=2)
    
    return filepath


def display_report(report):
    """Display the report in a formatted way in the console."""
    print("\n" + "="*80)
    print(f"AWS INFRASTRUCTURE REPORT - {report['region']}")
    print(f"Generated at: {report['timestamp']}")
    print("="*80)
    
    print(f"\nSUMMARY:")
    print(f"  Total Instances: {report['summary']['total_instances']}")
    print(f"  Running Instances: {report['summary']['running_instances']}")
    print(f"  Total Hourly Cost: ${report['summary']['total_hourly_cost']:.4f}")
    print(f"  Total Monthly Cost: ${report['summary']['total_monthly_cost']:.2f}")
    
    print("\nINSTANCE DETAILS:")
    for idx, instance in enumerate(report['instances'], 1):
        print(f"\n  {idx}. {instance['InstanceId']} ({instance['InstanceType']})")
        print(f"     State: {instance['State']}")
        print(f"     AZ: {instance['AvailabilityZone']}")
        
        if instance['Costs']['hourly'] is not None:
            print(f"     Hourly Cost: ${instance['Costs']['hourly']:.4f}")
            print(f"     Monthly Est: ${instance['Costs']['monthly']:.2f}")
        else:
            print(f"     Cost: Not available")
            
        if 'Tags' in instance and instance['Tags']:
            print(f"     Tags: {', '.join([f'{k}={v}' for k, v in instance['Tags'].items()])}")
    
    print("\n" + "="*80)


def main():
    """Main function to run the AWS infrastructure report."""
    # Parse arguments and load configuration
    args = parse_arguments()
    config = load_config(args.config)
    
    # Determine which region to use (CLI overrides config)
    region = args.region if args.region else config.get('region', 'us-east-1')
    
    # Get output settings
    output_dir = config.get('output', {}).get('report_dir', 'reports')
    report_prefix = config.get('output', {}).get('report_prefix', 'aws_infra_report')
    
    # Check if we need to upload the static website
    if args.upload_resume:
        # Get S3 bucket from CLI args or config file
        s3_bucket = args.s3_bucket if args.s3_bucket else config.get('s3', {}).get('bucket')
        
        if not s3_bucket:
            print("Error: No S3 bucket specified. Please provide it via --s3_bucket option or in the config file.")
            sys.exit(1)
            
        print(f"Uploading static website content to S3 bucket: {s3_bucket}")
        success = upload_static_website(s3_bucket, region)
        
        if not success:
            print("Failed to upload static website content.")
            sys.exit(1)
            
        # If only uploading the website, exit after upload
        if not args.region and not config.get('always_generate_report', False):
            print("Static website upload completed. Exiting.")
            return
    
    print(f"Scanning AWS infrastructure in region: {region}")
    
    # Initialize AWS clients
    ec2 = boto3.client('ec2', region_name=region)
    
    # Get all instances in the region
    try:
        response = ec2.describe_instances()
        instance_ids = []
        
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_ids.append(instance['InstanceId'])
                
        print(f"Found {len(instance_ids)} instances in region {region}")
    except Exception as e:
        print(f"Error retrieving instances: {e}")
        sys.exit(1)
    
    # Collect data for each instance
    instances_data = []
    for instance_id in instance_ids:
        details = get_instance_details(ec2, instance_id)
        if details:
            spot_price = get_spot_price(ec2, instance_id)
            details['SpotPrice'] = spot_price
            details['Costs'] = calculate_costs(spot_price)
            instances_data.append(details)
    
    # Generate and save report
    report = generate_report(region, instances_data)
    report_path = save_report(report, output_dir, report_prefix)
    print(f"Report saved to: {report_path}")
    
    # Display report in console
    display_report(report)


if __name__ == "__main__":
    main()




