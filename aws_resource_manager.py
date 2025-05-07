#!/usr/bin/env python3
"""
AWS Resource Manager

This script manages AWS resources including generating reports about deployed infrastructure,
focusing on cost analysis for spot instances. It also provides functionality to deploy
CloudFormation templates for various solutions and manage S3 website content.
"""

import argparse
import boto3
import json
import os
import sys
import yaml
import shutil
from datetime import datetime
from pathlib import Path
from deploy_function import deploy_cloudformation_template, attach_bucket_policy, export_deployed_template, upload_static_website, update_stack_parameters


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='AWS Resource Manager')
    parser.add_argument('--region', type=str, help='AWS region to scan')
    parser.add_argument('--config', type=str, default='config.yaml',
                        help='Path to configuration file')
    parser.add_argument('--upload_resume', action='store_true',
                        help='Upload static website content to S3 bucket')
    parser.add_argument('--s3_bucket', type=str,
                        help='S3 bucket name for resume upload (overrides config file)')
    parser.add_argument('--deploy', type=str, choices=['static_website', 'messaging', 'streaming_media'],
                        help='Deploy a CloudFormation template for the specified solution')
    parser.add_argument('--update', action='store_true',
                        help='Update an existing CloudFormation stack with changes')
    parser.add_argument('--export_template', action='store_true',
                        help='Export the deployed CloudFormation template to the deployed directory')
    parser.add_argument('--stack_name', type=str,
                        help='CloudFormation stack name for deployment')
    parser.add_argument('--static_website_stack', type=str,
                        help='Name of the static website stack (required when deploying messaging solution)')
    parser.add_argument('--streaming_stack', type=str,
                        help='Name of the streaming media stack (required when deploying streaming media solution)')
    parser.add_argument('--attach_bucket_policy', action='store_true',
                        help='Attach bucket policy to allow CloudFront to access the S3 bucket')
    parser.add_argument('--cloudfront_distribution_id', type=str,
                        help='CloudFront distribution ID for bucket policy (optional)')
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




def get_instance_details(ec2, instance_id, config=None):
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
        else:
            # If no tags are present, initialize an empty dictionary
            details['Tags'] = {}
            
        # Check if we need to add default tags from config
        if config and 'tags' in config:
            # Only add default tags if they don't already exist on the instance
            for key, value in config['tags'].items():
                if key not in details['Tags']:
                    details['Tags'][key] = value
            
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
    print(f"AWS RESOURCE REPORT - {report['region']}")
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
    """Main function to run the AWS resource manager."""
    # Parse arguments and load configuration
    args = parse_arguments()
    config = load_config(args.config)
    
    # Determine which region to use (CLI overrides config)
    region = args.region if args.region else config.get('region', 'us-east-1')
    
    # Get output settings
    output_dir = config.get('output', {}).get('report_dir', 'reports')
    report_prefix = config.get('output', {}).get('report_prefix', 'aws_resource_report')
    
    # Check if we need to attach a bucket policy
    if args.attach_bucket_policy:
        # Get S3 bucket from CLI args or config file
        s3_bucket = args.s3_bucket if args.s3_bucket else config.get('s3', {}).get('bucket')
        
        if not s3_bucket:
            print("Error: No S3 bucket specified. Please provide it via --s3_bucket option or in the config file.")
            sys.exit(1)
            
        # Get CloudFront distribution ID if provided
        cloudfront_distribution_id = args.cloudfront_distribution_id
        cloudfront_arn = None
        
        if cloudfront_distribution_id:
            # Get CloudFront distribution ARN
            cf = boto3.client('cloudfront', region_name=region)
            try:
                distribution_response = cf.get_distribution(Id=cloudfront_distribution_id)
                cloudfront_arn = distribution_response['Distribution']['ARN']
            except Exception as e:
                print(f"Error getting CloudFront distribution: {e}")
                sys.exit(1)
        
        print(f"Attaching bucket policy to S3 bucket: {s3_bucket}")
        success = attach_bucket_policy(s3_bucket, region, cloudfront_arn)
        
        if not success:
            print("Failed to attach bucket policy.")
            sys.exit(1)
            
        print("Bucket policy attached successfully.")
        return
    
    # Check if we need to deploy or update a CloudFormation template
    if args.deploy:
        solution_name = args.deploy
        
        # Check if stack name is provided
        if not args.stack_name:
            print("Error: Stack name is required for deployment. Please provide it via --stack_name option.")
            sys.exit(1)
            
        stack_name = args.stack_name
        
        # Check if static_website_stack is provided when deploying messaging solution
        if solution_name == 'messaging' and not args.static_website_stack:
            print("Error: Static website stack name is required when deploying messaging solution. Please provide it via --static_website_stack option.")
            sys.exit(1)
            
        # Check if static_website_stack is provided when deploying streaming media solution
        if solution_name == 'streaming_media' and not args.static_website_stack:
            print("Error: Static website stack name is required when deploying streaming media solution. Please provide it via --static_website_stack option.")
            sys.exit(1)
            
        # Add static_website_stack to parameters if provided
        if solution_name == 'messaging' and args.static_website_stack:
            if 'solutions' not in config:
                config['solutions'] = {}
            if 'messaging' not in config['solutions']:
                config['solutions']['messaging'] = {}
            if 'parameters' not in config['solutions']['messaging'] or config['solutions']['messaging']['parameters'] is None:
                config['solutions']['messaging']['parameters'] = {}
            config['solutions']['messaging']['parameters']['StaticWebsiteStackName'] = args.static_website_stack
            
        # Add static_website_stack to parameters for streaming media solution
        if solution_name == 'streaming_media' and args.static_website_stack:
            if 'solutions' not in config:
                config['solutions'] = {}
            if 'streaming_media' not in config['solutions']:
                config['solutions']['streaming_media'] = {}
            if 'parameters' not in config['solutions']['streaming_media'] or config['solutions']['streaming_media']['parameters'] is None:
                config['solutions']['streaming_media']['parameters'] = {}
            config['solutions']['streaming_media']['parameters']['StaticWebsiteStackName'] = args.static_website_stack
        
        if args.update:
            print(f"Updating CloudFormation stack '{stack_name}' for solution '{solution_name}'...")
        else:
            print(f"Deploying CloudFormation template for solution '{solution_name}' with stack name '{stack_name}'...")
            
        result = deploy_cloudformation_template(solution_name, stack_name, region, config, args.export_template, args.update)
        
        if result['status'] == 'error':
            print(f"Error {'updating' if args.update else 'deploying'} CloudFormation template: {result['message']}")
            sys.exit(1)
        
        # Print CloudFront URL if available
        if 'outputs' in result and 'CloudFrontDistributionDomainName' in result['outputs']:
            print(f"\nCloudFront Distribution URL: https://{result['outputs']['CloudFrontDistributionDomainName']}")
            print("\nYou can access your static website at the URL above.")
        
        # If this is the messaging solution, update the static website with the API endpoint
        if solution_name == 'messaging' and 'outputs' in result and 'ApiEndpoint' in result['outputs']:
            print("\nUpdating static website with messaging API endpoint...")
            try:
                # First, update the static website stack with the messaging stack name
                if args.static_website_stack:
                    print(f"\nUpdating static website stack '{args.static_website_stack}' with messaging stack name '{stack_name}'...")
                    update_result = update_stack_parameters(
                        args.static_website_stack,
                        region,
                        {'MessagingStackName': stack_name},
                        config
                    )
                    
                    if update_result['status'] == 'error':
                        print(f"Warning: Failed to update static website stack with messaging stack name: {update_result['message']}")
                    else:
                        print(f"Successfully updated static website stack with messaging stack name.")
                
                # Import the update_website module
                import update_website
                
                # Update the website
                api_endpoint = result['outputs']['ApiEndpoint']
                static_website_stack = args.static_website_stack
                if not update_website.update_index_html(api_endpoint, config):
                    print("Warning: Failed to update index.html with API endpoint.")
                
                # Add the messaging solution to the Solution Demonstrations section
                if not update_website.add_messaging_to_solution_demos(config):
                    print("Warning: Failed to add messaging solution to Solution Demonstrations section.")
                
                # Upload the updated website content if S3 bucket is available
                s3_bucket = config.get('s3', {}).get('bucket')
                if s3_bucket:
                    print(f"\nUploading updated static website content to S3 bucket: {s3_bucket}")
                    success = upload_static_website(s3_bucket, region, config)
                    if not success:
                        print("Warning: Failed to upload updated static website content.")
            except Exception as e:
                print(f"Warning: Failed to update static website: {e}")
        
        # If this is the streaming media solution, update the static website with the streaming endpoints
        if solution_name == 'streaming_media' and 'outputs' in result:
            print("\nUpdating static website with streaming media endpoints...")
            try:
                # First, update the static website stack with the streaming media stack name
                if args.static_website_stack:
                    print(f"\nUpdating static website stack '{args.static_website_stack}' with streaming media stack name '{stack_name}'...")
                    update_result = update_stack_parameters(
                        args.static_website_stack,
                        region,
                        {'StreamingMediaStackName': stack_name},
                        config
                    )
                    
                    if update_result['status'] == 'error':
                        print(f"Warning: Failed to update static website stack with streaming media stack name: {update_result['message']}")
                    else:
                        print(f"Successfully updated static website stack with streaming media stack name.")
                
                # Import the update_website module
                import update_website
                
                # Get the streaming endpoints from the result
                streaming_endpoints = {}
                if 'HlsEndpointUrl' in result['outputs']:
                    streaming_endpoints['hls'] = result['outputs']['HlsEndpointUrl']
                if 'DashEndpointUrl' in result['outputs']:
                    streaming_endpoints['dash'] = result['outputs']['DashEndpointUrl']
                if 'MediaLiveInputUrl' in result['outputs']:
                    streaming_endpoints['input'] = result['outputs']['MediaLiveInputUrl']
                if 'VodBucketName' in result['outputs']:
                    streaming_endpoints['vod'] = result['outputs']['VodBucketName']
                
                # Add the streaming media solution to the Solution Demonstrations section
                if not update_website.add_streaming_media_to_solution_demos(config):
                    print("Warning: Failed to add streaming media solution to Solution Demonstrations section.")
                
                # Add the streaming media buttons to the website
                if not update_website.add_streaming_media_buttons(streaming_endpoints, config):
                    print("Warning: Failed to add streaming media buttons to the website.")
                
                # Upload the updated website content if S3 bucket is available
                s3_bucket = config.get('s3', {}).get('bucket')
                if s3_bucket:
                    print(f"\nUploading updated static website content to S3 bucket: {s3_bucket}")
                    success = upload_static_website(s3_bucket, region, config)
                    if not success:
                        print("Warning: Failed to upload updated static website content.")
            except Exception as e:
                print(f"Warning: Failed to update static website with streaming media: {e}")
            
        # Provide instructions for exporting the template
        if not args.export_template:
            print("\nTIP: You can export the deployed template for future reference with:")
            print(f"python aws_resource_manager.py --deploy {solution_name} --stack_name {stack_name} --export_template")
            
        # If only deploying, exit after deployment
        if not args.upload_resume and not args.region:
            return
    
    # Check if we need to upload the static website
    if args.upload_resume:
        # Get S3 bucket from CLI args or config file
        s3_bucket = args.s3_bucket if args.s3_bucket else config.get('s3', {}).get('bucket')
        
        if not s3_bucket:
            print("Error: No S3 bucket specified. Please provide it via --s3_bucket option or in the config file.")
            sys.exit(1)
            
        print(f"Uploading static website content to S3 bucket: {s3_bucket}")
        success = upload_static_website(s3_bucket, region, config)
        
        if not success:
            print("Failed to upload static website content.")
            sys.exit(1)
            
        # If only uploading the website, exit after upload
        if not args.region and not args.deploy and not config.get('always_generate_report', False):
            print("Static website upload completed. Exiting.")
            return
    
    # If no specific action was requested, generate the infrastructure report
    if not args.deploy and not args.upload_resume and not args.attach_bucket_policy:
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
            details = get_instance_details(ec2, instance_id, config)
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