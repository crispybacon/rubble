#!/usr/bin/env python3
"""
AWS Infrastructure Report Tool

This script generates reports about deployed AWS infrastructure,
focusing on cost analysis for spot instances. It also provides
functionality to deploy CloudFormation templates for various solutions.
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
    parser.add_argument('--deploy', type=str, choices=['static_website'],
                        help='Deploy a CloudFormation template for the specified solution')
    parser.add_argument('--export_template', action='store_true',
                        help='Export the deployed CloudFormation template to the deployed directory')
    parser.add_argument('--stack_name', type=str,
                        help='CloudFormation stack name for deployment')
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


def deploy_cloudformation_template(solution_name, stack_name, region, config, export_template=False):
    """
    Deploy a CloudFormation template for a specific solution.
    
    Args:
        solution_name: Name of the solution to deploy (e.g., 'static_website')
        stack_name: Name of the CloudFormation stack
        region: AWS region for deployment
        config: Configuration dictionary
        export_template: Whether to export the template after deployment
        
    Returns:
        dict: Deployment result with status and outputs
    """
    try:
        # Check if the solution exists in the config
        if solution_name not in config.get('solutions', {}):
            print(f"Error: Solution '{solution_name}' not found in configuration.")
            return {'status': 'error', 'message': f"Solution '{solution_name}' not found in configuration."}
        
        solution_config = config['solutions'][solution_name]
        template_path = solution_config.get('template_path')
        
        if not template_path or not Path(template_path).exists():
            print(f"Error: Template file '{template_path}' not found.")
            return {'status': 'error', 'message': f"Template file '{template_path}' not found."}
        
        # Read the template file
        with open(template_path, 'r') as file:
            template_body = file.read()
        
        # Initialize CloudFormation client
        cfn = boto3.client('cloudformation', region_name=region)
        
        # Prepare parameters for CloudFormation
        parameters = []
        for key, value in solution_config.get('parameters', {}).items():
            parameters.append({
                'ParameterKey': key,
                'ParameterValue': value
            })
        
        # Add region parameter if it exists in the template
        parameters.append({
            'ParameterKey': 'AwsRegion',
            'ParameterValue': region
        })
        
        # Add tag parameters if they exist in the config
        if 'tags' in config:
            if 'organization' in config['tags']:
                parameters.append({
                    'ParameterKey': 'OrganizationTag',
                    'ParameterValue': config['tags']['organization']
                })
            if 'business_unit' in config['tags']:
                parameters.append({
                    'ParameterKey': 'BusinessUnitTag',
                    'ParameterValue': config['tags']['business_unit']
                })
            if 'environment' in config['tags']:
                parameters.append({
                    'ParameterKey': 'EnvironmentTag',
                    'ParameterValue': config['tags']['environment']
                })
        
        print(f"Deploying CloudFormation stack '{stack_name}' for solution '{solution_name}'...")
        
        # Create or update the stack
        try:
            # Check if stack exists
            cfn.describe_stacks(StackName=stack_name)
            # Stack exists, update it
            response = cfn.update_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=parameters,
                Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM', 'CAPABILITY_AUTO_EXPAND']
            )
            operation = 'update'
        except cfn.exceptions.ClientError as e:
            if 'does not exist' in str(e):
                # Stack doesn't exist, create it
                response = cfn.create_stack(
                    StackName=stack_name,
                    TemplateBody=template_body,
                    Parameters=parameters,
                    Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM', 'CAPABILITY_AUTO_EXPAND']
                )
                operation = 'create'
            elif 'No updates are to be performed' in str(e):
                print("No updates are to be performed on the stack.")
                # Get stack outputs
                stack_info = cfn.describe_stacks(StackName=stack_name)
                outputs = {output['OutputKey']: output['OutputValue'] 
                          for output in stack_info['Stacks'][0].get('Outputs', [])}
                
                if export_template and 'CloudFrontDistributionDomainName' in outputs:
                    export_deployed_template(solution_name, stack_name, region, config)
                
                # Check if we need to attach a bucket policy for the static website solution
                if solution_name == 'static_website' and 'S3BucketName' in outputs:
                    # Check if the template already has a bucket policy
                    template_has_bucket_policy = 'S3BucketPolicy' in yaml.safe_load(template_body).get('Resources', {})
                    
                    if not template_has_bucket_policy:
                        print("Template doesn't include bucket policy. Attaching it programmatically...")
                        
                        # Get CloudFront distribution ARN
                        cf = boto3.client('cloudfront', region_name=region)
                        distribution_id = outputs.get('CloudFrontDistributionId')
                        
                        if distribution_id:
                            distribution_response = cf.get_distribution(Id=distribution_id)
                            cloudfront_arn = distribution_response['Distribution']['ARN']
                        else:
                            cloudfront_arn = None
                        
                        # Attach bucket policy
                        attach_bucket_policy(outputs['S3BucketName'], region, cloudfront_arn)
                
                return {
                    'status': 'success', 
                    'message': 'No updates were performed on the stack.',
                    'outputs': outputs
                }
            else:
                raise
        
        # Wait for stack creation/update to complete
        print(f"Waiting for stack {operation} to complete...")
        waiter = cfn.get_waiter(f'stack_{operation}_complete')
        waiter.wait(StackName=stack_name)
        
        # Get stack outputs
        stack_info = cfn.describe_stacks(StackName=stack_name)
        outputs = {output['OutputKey']: output['OutputValue'] 
                  for output in stack_info['Stacks'][0].get('Outputs', [])}
        
        print(f"Stack {operation} completed successfully!")
        
        # Print CloudFront URL if available
        if 'CloudFrontDistributionDomainName' in outputs:
            print(f"\nCloudFront Distribution URL: https://{outputs['CloudFrontDistributionDomainName']}")
        
        # Export the template if requested
        if export_template:
            export_deployed_template(solution_name, stack_name, region, config)
        
        # Check if we need to attach a bucket policy for the static website solution
        if solution_name == 'static_website' and 'S3BucketName' in outputs:
            # Check if the template already has a bucket policy
            template_has_bucket_policy = 'S3BucketPolicy' in yaml.safe_load(template_body).get('Resources', {})
            
            if not template_has_bucket_policy:
                print("Template doesn't include bucket policy. Attaching it programmatically...")
                
                # Get CloudFront distribution ARN
                cf = boto3.client('cloudfront', region_name=region)
                distribution_id = outputs.get('CloudFrontDistributionId')
                
                if distribution_id:
                    distribution_response = cf.get_distribution(Id=distribution_id)
                    cloudfront_arn = distribution_response['Distribution']['ARN']
                else:
                    cloudfront_arn = None
                
                # Attach bucket policy
                attach_bucket_policy(outputs['S3BucketName'], region, cloudfront_arn)
        
        return {
            'status': 'success',
            'message': f"Stack {operation} completed successfully!",
            'outputs': outputs
        }
    
    except Exception as e:
        print(f"Error deploying CloudFormation template: {e}")
        return {'status': 'error', 'message': str(e)}


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


def export_deployed_template(solution_name, stack_name, region, config):
    """
    Export a deployed CloudFormation template to the deployed directory.
    
    Args:
        solution_name: Name of the solution
        stack_name: Name of the CloudFormation stack
        region: AWS region
        config: Configuration dictionary
        
    Returns:
        bool: True if export was successful, False otherwise
    """
    try:
        # Get the deployed directory from config
        solution_config = config['solutions'][solution_name]
        deployed_dir = solution_config.get('deployed_dir', 'iac/deployed')
        
        # Create the deployed directory if it doesn't exist
        Path(deployed_dir).mkdir(exist_ok=True, parents=True)
        
        # Initialize CloudFormation client
        cfn = boto3.client('cloudformation', region_name=region)
        
        # Get the template body
        response = cfn.get_template(
            StackName=stack_name,
            TemplateStage='Original'
        )
        
        template_body = response['TemplateBody']
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{solution_name}_{stack_name}_{timestamp}.yaml"
        filepath = os.path.join(deployed_dir, filename)
        
        # Write template to file
        if isinstance(template_body, dict):
            with open(filepath, 'w') as f:
                yaml.dump(template_body, f, default_flow_style=False)
        else:
            with open(filepath, 'w') as f:
                f.write(template_body)
        
        print(f"Exported deployed template to: {filepath}")
        return True
    
    except Exception as e:
        print(f"Error exporting deployed template: {e}")
        return False


def attach_bucket_policy(bucket_name, region, cloudfront_distribution_arn=None):
    """
    Attach a bucket policy to allow CloudFront to access the S3 bucket.
    If a policy already exists, it will be updated to include the new CloudFront distribution
    while preserving existing permissions.
    
    Args:
        bucket_name: Name of the S3 bucket
        region: AWS region
        cloudfront_distribution_arn: ARN of the CloudFront distribution (if None, will be fetched)
        
    Returns:
        bool: True if policy was attached successfully, False otherwise
    """
    try:
        # Initialize S3 client
        s3 = boto3.client('s3', region_name=region)
        
        # If CloudFront distribution ARN is not provided, try to fetch it
        if not cloudfront_distribution_arn:
            # Initialize CloudFront client
            cf = boto3.client('cloudfront', region_name=region)
            
            # List distributions to find one that matches our bucket
            response = cf.list_distributions()
            
            if 'DistributionList' in response and 'Items' in response['DistributionList']:
                for distribution in response['DistributionList']['Items']:
                    # Check if this distribution has our bucket as an origin
                    for origin in distribution.get('Origins', {}).get('Items', []):
                        if bucket_name in origin.get('DomainName', ''):
                            cloudfront_distribution_arn = distribution['ARN']
                            print(f"Found CloudFront distribution ARN: {cloudfront_distribution_arn}")
                            break
                    
                    if cloudfront_distribution_arn:
                        break
        
        # If we still don't have a CloudFront distribution ARN, we can't proceed
        if not cloudfront_distribution_arn:
            print(f"Error: Could not find CloudFront distribution for bucket {bucket_name}")
            return False
        
        # Check if a bucket policy already exists
        existing_policy = None
        try:
            response = s3.get_bucket_policy(Bucket=bucket_name)
            if 'Policy' in response:
                existing_policy = json.loads(response['Policy'])
                print(f"Found existing bucket policy for {bucket_name}")
        except s3.exceptions.NoSuchBucketPolicy:
            print(f"No existing bucket policy found for {bucket_name}")
        except Exception as e:
            print(f"Error retrieving bucket policy: {e}")
        
        # If there's an existing policy, check if we need to update it
        if existing_policy:
            # Check if this CloudFront distribution is already in the policy
            cloudfront_already_in_policy = False
            cloudfront_statement_index = -1
            
            for i, statement in enumerate(existing_policy.get('Statement', [])):
                # Look for CloudFront service principal statements
                if (statement.get('Principal', {}).get('Service') == 'cloudfront.amazonaws.com' and
                    statement.get('Action') == 's3:GetObject' and
                    statement.get('Resource') == f"arn:aws:s3:::{bucket_name}/*"):
                    
                    cloudfront_statement_index = i
                    
                    # Check if this specific CloudFront ARN is already in the condition
                    condition = statement.get('Condition', {})
                    string_equals = condition.get('StringEquals', {})
                    source_arn = string_equals.get('AWS:SourceArn')
                    
                    if source_arn == cloudfront_distribution_arn:
                        cloudfront_already_in_policy = True
                        print(f"CloudFront distribution {cloudfront_distribution_arn} already in bucket policy")
                        break
                    
                    # Check if the condition is using StringLike with a list of ARNs
                    string_like = condition.get('StringLike', {})
                    source_arns = string_like.get('AWS:SourceArn', [])
                    
                    if isinstance(source_arns, list) and cloudfront_distribution_arn in source_arns:
                        cloudfront_already_in_policy = True
                        print(f"CloudFront distribution {cloudfront_distribution_arn} already in bucket policy")
                        break
            
            # If the CloudFront distribution is not in the policy, add it
            if not cloudfront_already_in_policy:
                if cloudfront_statement_index >= 0:
                    # Update existing CloudFront statement to use StringLike with a list of ARNs
                    statement = existing_policy['Statement'][cloudfront_statement_index]
                    
                    # Get the current ARN(s)
                    current_arns = []
                    if 'Condition' in statement:
                        if 'StringEquals' in statement['Condition'] and 'AWS:SourceArn' in statement['Condition']['StringEquals']:
                            current_arns.append(statement['Condition']['StringEquals']['AWS:SourceArn'])
                            # Remove the StringEquals condition
                            del statement['Condition']['StringEquals']
                        elif 'StringLike' in statement['Condition'] and 'AWS:SourceArn' in statement['Condition']['StringLike']:
                            if isinstance(statement['Condition']['StringLike']['AWS:SourceArn'], list):
                                current_arns.extend(statement['Condition']['StringLike']['AWS:SourceArn'])
                            else:
                                current_arns.append(statement['Condition']['StringLike']['AWS:SourceArn'])
                    
                    # Add the new ARN
                    if cloudfront_distribution_arn not in current_arns:
                        current_arns.append(cloudfront_distribution_arn)
                    
                    # Update the condition to use StringLike with the list of ARNs
                    if 'Condition' not in statement:
                        statement['Condition'] = {}
                    
                    statement['Condition']['StringLike'] = {
                        'AWS:SourceArn': current_arns
                    }
                    
                    print(f"Updated bucket policy to include CloudFront distribution {cloudfront_distribution_arn}")
                else:
                    # Add a new statement for this CloudFront distribution
                    new_statement = {
                        "Sid": "AllowCloudFrontServicePrincipal",
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "cloudfront.amazonaws.com"
                        },
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{bucket_name}/*",
                        "Condition": {
                            "StringEquals": {
                                "AWS:SourceArn": cloudfront_distribution_arn
                            }
                        }
                    }
                    existing_policy['Statement'].append(new_statement)
                    print(f"Added new statement for CloudFront distribution {cloudfront_distribution_arn}")
                
                # Update the bucket policy
                bucket_policy_json = json.dumps(existing_policy)
                s3.put_bucket_policy(
                    Bucket=bucket_name,
                    Policy=bucket_policy_json
                )
                print(f"Successfully updated bucket policy for {bucket_name}")
            
            return True
        else:
            # Create a new bucket policy
            bucket_policy = {
                "Version": "2008-10-17",
                "Id": "PolicyForCloudFrontPrivateContent",
                "Statement": [
                    {
                        "Sid": "AllowCloudFrontServicePrincipal",
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "cloudfront.amazonaws.com"
                        },
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{bucket_name}/*",
                        "Condition": {
                            "StringEquals": {
                                "AWS:SourceArn": cloudfront_distribution_arn
                            }
                        }
                    }
                ]
            }
            
            # Convert policy to JSON string
            bucket_policy_json = json.dumps(bucket_policy)
            
            # Attach the policy to the bucket
            s3.put_bucket_policy(
                Bucket=bucket_name,
                Policy=bucket_policy_json
            )
            
            print(f"Successfully attached new bucket policy to {bucket_name}")
            return True
    
    except Exception as e:
        print(f"Error attaching bucket policy: {e}")
        return False


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


def upload_static_website(s3_bucket, region, config=None):
    """
    Upload static website content to an S3 bucket.
    
    Args:
        s3_bucket: Name of the S3 bucket
        region: AWS region
        config: Configuration dictionary
        
    Returns:
        bool: True if upload was successful, False otherwise
    """
    try:
        # Initialize S3 client
        s3 = boto3.client('s3', region_name=region)
        
        # Get the content directory from config if available
        static_website_dir = 'iac/static_website'
        content_dir_path = None
        
        if config and 'solutions' in config and 'static_website' in config['solutions']:
            solution_config = config['solutions']['static_website']
            if 'content_dir' in solution_config:
                content_dir_path = solution_config['content_dir']
        
        # Check if the directory exists
        website_dir = Path(static_website_dir)
        if not website_dir.exists() or not website_dir.is_dir():
            print(f"Error: Static website directory '{static_website_dir}' not found.")
            return False
        
        # Use the content directory from config if specified, otherwise check for a content subdirectory
        if content_dir_path:
            content_dir = Path(content_dir_path)
            if content_dir.exists() and content_dir.is_dir():
                website_dir = content_dir
                print(f"Using content directory from config: {content_dir}")
            else:
                print(f"Content directory from config not found: {content_dir_path}")
                # Fall back to checking for a content subdirectory
                content_subdir = website_dir / 'content'
                if content_subdir.exists() and content_subdir.is_dir():
                    website_dir = content_subdir
                    print(f"Using content subdirectory: {content_subdir}")
                else:
                    print(f"Content subdirectory not found, using main directory: {website_dir}")
        else:
            # Check if the content directory exists, if not, use the main directory
            content_subdir = website_dir / 'content'
            if content_subdir.exists() and content_subdir.is_dir():
                website_dir = content_subdir
                print(f"Using content subdirectory: {content_subdir}")
            else:
                print(f"Content subdirectory not found, using main directory: {website_dir}")
        
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
                if file_path.suffix.lower() in ['.yaml', '.yml', '.json'] and ('cloudformation' in file_path.name.lower() or 'template' in file_path.name.lower()):
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
    
    # Check if we need to deploy a CloudFormation template
    if args.deploy:
        solution_name = args.deploy
        
        # Check if stack name is provided
        if not args.stack_name:
            print("Error: Stack name is required for deployment. Please provide it via --stack_name option.")
            sys.exit(1)
            
        stack_name = args.stack_name
        
        print(f"Deploying CloudFormation template for solution '{solution_name}' with stack name '{stack_name}'...")
        result = deploy_cloudformation_template(solution_name, stack_name, region, config, args.export_template)
        
        if result['status'] == 'error':
            print(f"Error deploying CloudFormation template: {result['message']}")
            sys.exit(1)
        
        # Print CloudFront URL if available
        if 'outputs' in result and 'CloudFrontDistributionDomainName' in result['outputs']:
            print(f"\nCloudFront Distribution URL: https://{result['outputs']['CloudFrontDistributionDomainName']}")
            print("\nYou can access your static website at the URL above.")
            
        # Provide instructions for exporting the template
        if not args.export_template:
            print("\nTIP: You can export the deployed template for future reference with:")
            print(f"python aws_infra_report.py --deploy {solution_name} --stack_name {stack_name} --export_template")
            
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




















