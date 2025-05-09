import boto3
import yaml
import json
import os
import mimetypes
from datetime import datetime
from pathlib import Path

# Custom YAML loader for CloudFormation templates
class CloudFormationYamlLoader(yaml.SafeLoader):
    """Custom YAML loader that can handle CloudFormation intrinsic functions."""
    pass

# Add constructors for CloudFormation intrinsic functions
def cfn_tag_constructor(loader, tag_suffix, node):
    """Constructor for CloudFormation intrinsic functions."""
    if isinstance(node, yaml.ScalarNode):
        return {tag_suffix: loader.construct_scalar(node)}
    elif isinstance(node, yaml.SequenceNode):
        return {tag_suffix: loader.construct_sequence(node)}
    elif isinstance(node, yaml.MappingNode):
        return {tag_suffix: loader.construct_mapping(node)}
    else:
        raise yaml.constructor.ConstructorError(None, None, f"Unexpected node type: {node.id}", node.start_mark)

# Register tag handlers for common CloudFormation intrinsic functions
for tag in ['Ref', 'GetAtt', 'Sub', 'Join', 'ImportValue', 'Base64', 'Cidr', 'FindInMap', 'GetAZs', 'Select', 'Split', 'Transform']:
    CloudFormationYamlLoader.add_multi_constructor('!', cfn_tag_constructor)

def load_cloudformation_yaml(yaml_content):
    """
    Load a CloudFormation YAML template with support for intrinsic functions.
    
    Args:
        yaml_content: YAML content as a string
        
    Returns:
        dict: Parsed YAML content
    """
    try:
        return yaml.load(yaml_content, Loader=CloudFormationYamlLoader)
    except Exception as e:
        print(f"Warning: Error parsing CloudFormation YAML: {e}")
        # Fall back to safe_load which might work for simpler templates
        return yaml.safe_load(yaml_content)

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
        
        # Upload only index.html, pictures, and CSS files
        file_count = 0
        for file_path in website_dir.glob('**/*'):
            if file_path.is_file():
                # Only allow index.html, CSS files, and image files
                if (file_path.name == 'index.html' or 
                    file_path.suffix.lower() == '.css' or 
                    file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico']):
                    
                    # Calculate the relative path for the S3 key
                    relative_path = file_path.relative_to(website_dir)
                    s3_key = str(relative_path)
                    
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
                    elif file_path.suffix == '.gif':
                        content_type = 'image/gif'
                    elif file_path.suffix == '.svg':
                        content_type = 'image/svg+xml'
                    elif file_path.suffix == '.ico':
                        content_type = 'image/x-icon'
                    
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
                else:
                    print(f"Skipping file (not index.html, CSS, or image): {file_path}")
        
        print(f"Successfully uploaded {file_count} files to s3://{s3_bucket}/")
        return True
    except Exception as e:
        print(f"Error uploading static website content: {e}")
        return False

def upload_vod_content(s3_bucket, region, config=None):
    """
    Upload video on demand content to an S3 bucket.
    
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
        
        # Get the VOD content directory from config if available
        vod_samples_dir = Path('vod-samples')
        
        if config and 'solutions' in config and 'combined_website' in config['solutions']:
            solution_config = config['solutions']['combined_website']
            if 'vod_content_dir' in solution_config:
                vod_dir_path = solution_config['vod_content_dir']
                vod_samples_dir = Path(vod_dir_path)
                print(f"Using VOD content directory from config: {vod_samples_dir}")
        
        # Check if the directory exists
        if not vod_samples_dir.exists() or not vod_samples_dir.is_dir():
            print(f"Error: VOD samples directory '{vod_samples_dir}' not found.")
            return False
        
        # Check if the bucket exists
        try:
            s3.head_bucket(Bucket=s3_bucket)
        except Exception as e:
            print(f"Error: S3 bucket '{s3_bucket}' not accessible: {e}")
            return False
        
        # Upload video files
        file_count = 0
        for file_path in vod_samples_dir.glob('**/*'):
            if file_path.is_file():
                # Calculate the relative path for the S3 key
                relative_path = file_path.relative_to(vod_samples_dir)
                # Add 'vod/' prefix to the key
                s3_key = f"vod/{str(relative_path)}"
                
                # Determine content type based on file extension
                content_type, _ = mimetypes.guess_type(str(file_path))
                if content_type is None:
                    # Default to binary/octet-stream if type cannot be determined
                    content_type = 'application/octet-stream'
                
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
        
        print(f"Successfully uploaded {file_count} VOD files to s3://{s3_bucket}/vod/")
        return True
    except Exception as e:
        print(f"Error uploading VOD content: {e}")
        return False
        
def update_streaming_endpoints(html_file_path, hls_endpoint, vod_bucket_name):
    """
    Update the streaming endpoints in the HTML file.
    
    Args:
        html_file_path: Path to the HTML file
        hls_endpoint: HLS endpoint URL
        vod_bucket_name: VOD bucket name
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        # Read the HTML file
        with open(html_file_path, 'r') as file:
            html_content = file.read()
        
        # Create the replacement string
        replacement = f'''  // These values are dynamically set during deployment
  const streamingEndpoints = {{
    hls: "{hls_endpoint}",
    vod: "/vod"
  }};'''
        
        # Replace the streaming endpoints
        updated_content = html_content.replace(
            '  // These values will be replaced during deployment with actual endpoints\n  const streamingEndpoints = {\n    hls: "/live/index.m3u8",\n    vod: "/vod"\n  };',
            replacement
        )
        
        # Write the updated content back to the file
        with open(html_file_path, 'w') as file:
            file.write(updated_content)
        
        print(f"Successfully updated streaming endpoints in {html_file_path}")
        return True
    except Exception as e:
        print(f"Error updating streaming endpoints: {e}")
        return False

def update_website_streaming_urls(stack_name, region, html_file_path=None):
    """
    Update the streaming URLs in the website HTML file and upload it to S3.
    
    Args:
        stack_name: Name of the CloudFormation stack
        region: AWS region
        html_file_path: Path to the HTML file (optional, defaults to iac/static_website/index.html)
        
    Returns:
        dict: Update result with status and message
    """
    try:
        # Initialize CloudFormation client
        cfn = boto3.client('cloudformation', region_name=region)
        
        # Get stack outputs
        try:
            stack_info = cfn.describe_stacks(StackName=stack_name)
            outputs = {output['OutputKey']: output['OutputValue'] 
                      for output in stack_info['Stacks'][0].get('Outputs', [])}
        except Exception as e:
            return {'status': 'error', 'message': f"Error getting stack outputs: {str(e)}"}
        
        # Check if required outputs exist
        required_outputs = ['HlsEndpointUrl', 'StaticWebsiteBucketName', 'VodBucketName']
        missing_outputs = [output for output in required_outputs if output not in outputs]
        if missing_outputs:
            return {'status': 'error', 'message': f"Missing required stack outputs: {', '.join(missing_outputs)}"}
        
        # Set default HTML file path if not provided
        if not html_file_path:
            html_file_path = Path('iac/static_website/index.html')
        else:
            html_file_path = Path(html_file_path)
        
        # Check if HTML file exists
        if not html_file_path.exists():
            return {'status': 'error', 'message': f"HTML file not found: {html_file_path}"}
        
        # Update streaming endpoints in HTML file
        print(f"Updating streaming endpoints in {html_file_path}")
        update_success = update_streaming_endpoints(
            html_file_path,
            outputs['HlsEndpointUrl'],
            outputs['VodBucketName']
        )
        
        if not update_success:
            return {'status': 'error', 'message': "Failed to update streaming endpoints in HTML file"}
        
        # Upload updated HTML file to S3
        s3 = boto3.client('s3', region_name=region)
        try:
            with open(html_file_path, 'rb') as file_data:
                s3.put_object(
                    Bucket=outputs['StaticWebsiteBucketName'],
                    Key='index.html',
                    Body=file_data,
                    ContentType='text/html'
                )
            print(f"Successfully uploaded updated HTML file to S3 bucket: {outputs['StaticWebsiteBucketName']}")
        except Exception as e:
            return {'status': 'error', 'message': f"Error uploading HTML file to S3: {str(e)}"}
        
        # Create CloudFront invalidation to clear cache
        try:
            if 'CloudFrontDistributionId' in outputs:
                cf = boto3.client('cloudfront', region_name=region)
                invalidation_response = cf.create_invalidation(
                    DistributionId=outputs['CloudFrontDistributionId'],
                    InvalidationBatch={
                        'Paths': {
                            'Quantity': 1,
                            'Items': ['/index.html']
                        },
                        'CallerReference': str(int(time.time()))
                    }
                )
                print(f"Created CloudFront invalidation: {invalidation_response['Invalidation']['Id']}")
        except Exception as e:
            print(f"Warning: Failed to create CloudFront invalidation: {e}")
        
        # List VOD bucket contents to verify videos are available
        try:
            vod_bucket = outputs['VodBucketName']
            print(f"Checking VOD bucket contents: {vod_bucket}")
            response = s3.list_objects_v2(Bucket=vod_bucket, Prefix='vod/')
            
            if 'Contents' in response:
                video_count = sum(1 for item in response['Contents'] if item['Key'].lower().endswith(('.mp4', '.m3u8', '.mov', '.avi', '.wmv', '.flv', '.mkv')))
                print(f"Found {video_count} video files in the VOD bucket")
                
                # Print the first few videos for verification
                print("Sample videos:")
                video_files = [item['Key'] for item in response['Contents'] 
                              if item['Key'].lower().endswith(('.mp4', '.m3u8', '.mov', '.avi', '.wmv', '.flv', '.mkv'))]
                for i, video in enumerate(video_files[:5]):
                    print(f"  {i+1}. {video}")
                
                if len(video_files) > 5:
                    print(f"  ... and {len(video_files) - 5} more")
            else:
                print("No contents found in the VOD bucket. You may need to upload videos.")
        except Exception as e:
            print(f"Warning: Failed to list VOD bucket contents: {e}")
        
        return {
            'status': 'success',
            'message': "Successfully updated streaming URLs",
            'website_url': f"https://{outputs.get('CloudFrontDistributionDomainName', 'unknown')}"
        }
    
    except Exception as e:
        return {'status': 'error', 'message': f"Error updating streaming URLs: {str(e)}"}

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

def update_stack_parameters(stack_name, region, new_parameters, config=None):
    """
    Update a CloudFormation stack's parameters without changing the template.
    
    Args:
        stack_name: Name of the CloudFormation stack
        region: AWS region
        new_parameters: Dictionary of parameter key-value pairs to update
        config: Configuration dictionary (optional)
        
    Returns:
        dict: Update result with status and message
    """
    try:
        # Initialize CloudFormation client
        cfn = boto3.client('cloudformation', region_name=region)
        
        # Get the current stack template and parameters
        try:
            stack_info = cfn.describe_stacks(StackName=stack_name)
            current_parameters = stack_info['Stacks'][0].get('Parameters', [])
            
            # Convert current parameters to dictionary for easier lookup
            current_params_dict = {param['ParameterKey']: param['ParameterValue'] for param in current_parameters}
            
            # Get the current template
            template_response = cfn.get_template(
                StackName=stack_name,
                TemplateStage='Original'
            )
            template_body = template_response['TemplateBody']
            
            # Prepare parameters for update, merging current with new
            update_parameters = []
            for key, value in current_params_dict.items():
                if key in new_parameters:
                    # Use the new value
                    update_parameters.append({
                        'ParameterKey': key,
                        'ParameterValue': new_parameters[key]
                    })
                else:
                    # Keep the current value
                    update_parameters.append({
                        'ParameterKey': key,
                        'ParameterValue': value
                    })
            
            # Add any new parameters that weren't in the current parameters
            for key, value in new_parameters.items():
                if key not in current_params_dict:
                    update_parameters.append({
                        'ParameterKey': key,
                        'ParameterValue': value
                    })
            
            # Update the stack with the new parameters
            print(f"Updating stack '{stack_name}' with new parameters: {new_parameters}")
            cfn.update_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=update_parameters,
                Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM', 'CAPABILITY_AUTO_EXPAND']
            )
            
            # Wait for the update to complete
            print(f"Waiting for stack update to complete...")
            waiter = cfn.get_waiter('stack_update_complete')
            
            # Configure the waiter with increased timeout for CloudFront distributions
            waiter_config = {
                'Delay': 30,  # Check every 30 seconds
                'MaxAttempts': 120  # Wait up to 60 minutes (120 * 30 seconds)
            }
            
            print(f"Using extended waiter configuration: {waiter_config}")
            waiter.wait(StackName=stack_name, WaiterConfig=waiter_config)
            
            print(f"Stack '{stack_name}' updated successfully with new parameters.")
            return {
                'status': 'success',
                'message': f"Stack '{stack_name}' updated successfully with new parameters."
            }
            
        except cfn.exceptions.ClientError as e:
            if 'No updates are to be performed' in str(e):
                print(f"No updates needed for stack '{stack_name}'. Parameters may already be set to the desired values.")
                return {
                    'status': 'success',
                    'message': f"No updates needed for stack '{stack_name}'. Parameters may already be set to the desired values."
                }
            else:
                raise
    
    except Exception as e:
        print(f"Error updating stack parameters: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }

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
            # If it's a string, just write it directly
            with open(filepath, 'w') as f:
                f.write(template_body)
        
        print(f"Exported deployed template to: {filepath}")
        return True
    
    except Exception as e:
        print(f"Error exporting deployed template: {e}")
        return False

def deploy_cloudformation_template(solution_name, stack_name, region, config, export_template=False, force_update=False, dry_run=False):
    """
    Deploy a CloudFormation template for a specific solution.
    
    Args:
        solution_name: Name of the solution to deploy (e.g., 'static_website')
        stack_name: Name of the CloudFormation stack
        region: AWS region for deployment
        config: Configuration dictionary
        export_template: Whether to export the template after deployment
        force_update: Whether to force an update even if no changes are detected
        dry_run: If True, only prepare the parameters but don't actually deploy
        
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
        if solution_config.get('parameters') is not None:
            for key, value in solution_config.get('parameters', {}).items():
                parameters.append({
                    'ParameterKey': key,
                    'ParameterValue': value
                })
        
        # Check if AwsRegion parameter exists in the template before adding it
        template_dict = None
        try:
            if template_path.endswith('.yaml') or template_path.endswith('.yml'):
                template_dict = load_cloudformation_yaml(template_body)
            elif template_path.endswith('.json'):
                template_dict = json.loads(template_body)
                
            # Check if the AwsRegion parameter exists in the template
            if template_dict and 'Parameters' in template_dict and 'AwsRegion' in template_dict['Parameters']:
                parameters.append({
                    'ParameterKey': 'AwsRegion',
                    'ParameterValue': region
                })
        except Exception as e:
            print(f"Warning: Error parsing template to check for AwsRegion parameter: {e}")
        
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
        
        # Add messaging parameters if they exist in the config and we're deploying the messaging solution
        if 'messaging' in config and solution_name == 'messaging':
            if 'email' in config['messaging'] and 'destination' in config['messaging']['email']:
                parameters.append({
                    'ParameterKey': 'EmailDestination',
                    'ParameterValue': config['messaging']['email']['destination']
                })
            if 'sms' in config['messaging'] and 'destination' in config['messaging']['sms']:
                parameters.append({
                    'ParameterKey': 'SmsDestination',
                    'ParameterValue': config['messaging']['sms']['destination']
                })
            if 'sms' in config['messaging'] and 'country' in config['messaging']['sms']:
                parameters.append({
                    'ParameterKey': 'SmsCountry',
                    'ParameterValue': config['messaging']['sms']['country']
                })
            if 'sms' in config['messaging'] and 'originator_id' in config['messaging']['sms']:
                parameters.append({
                    'ParameterKey': 'SmsOriginatorId',
                    'ParameterValue': config['messaging']['sms']['originator_id']
                })
        
        if force_update:
            print(f"Forcing update of CloudFormation stack '{stack_name}' for solution '{solution_name}'...")
        else:
            print(f"Deploying CloudFormation stack '{stack_name}' for solution '{solution_name}'...")
        
        # If this is a dry run, return without actually deploying
        if dry_run:
            return {
                'status': 'dry_run',
                'message': 'Dry run completed successfully',
                'parameters': parameters
            }
            
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
            elif 'No updates are to be performed' in str(e) and force_update:
                # No updates are needed, but force_update is True, so use change sets to force an update
                print("No changes detected, but forcing update using change sets...")
                
                # Create a change set
                change_set_name = f"{stack_name}-change-set-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                cfn.create_change_set(
                    StackName=stack_name,
                    ChangeSetName=change_set_name,
                    TemplateBody=template_body,
                    Parameters=parameters,
                    Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM', 'CAPABILITY_AUTO_EXPAND'],
                    ChangeSetType='UPDATE'
                )
                
                # Wait for change set creation to complete
                print("Waiting for change set creation to complete...")
                waiter = cfn.get_waiter('change_set_create_complete')
                
                # Configure the waiter with increased timeout
                waiter_config = {
                    'Delay': 15,  # Check every 15 seconds
                    'MaxAttempts': 40  # Wait up to 10 minutes (40 * 15 seconds)
                }
                
                try:
                    print(f"Using extended waiter configuration: {waiter_config}")
                    waiter.wait(
                        StackName=stack_name,
                        ChangeSetName=change_set_name,
                        WaiterConfig=waiter_config
                    )
                    
                    # Execute the change set
                    print("Executing change set...")
                    cfn.execute_change_set(
                        StackName=stack_name,
                        ChangeSetName=change_set_name
                    )
                    operation = 'update'
                except cfn.exceptions.WaiterError:
                    # If the change set has no changes, this will fail
                    print("Change set has no changes. Stack is already up to date.")
                    
                    # Get stack outputs
                    stack_info = cfn.describe_stacks(StackName=stack_name)
                    outputs = {output['OutputKey']: output['OutputValue'] 
                              for output in stack_info['Stacks'][0].get('Outputs', [])}
                    
                    if export_template and 'CloudFrontDistributionDomainName' in outputs:
                        export_deployed_template(solution_name, stack_name, region, config)
                    
                    # Check if we need to attach a bucket policy for the static website solution
                    if solution_name == 'static_website' and 'S3BucketName' in outputs:
                        # Check if the template already has a bucket policy
                        template_has_bucket_policy = 'S3BucketPolicy' in load_cloudformation_yaml(template_body).get('Resources', {})
                        
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
                    
                    # Upload the static website files to the S3 bucket if this is the static website solution
                    if solution_name == 'static_website' and 'S3BucketName' in outputs:
                        print(f"Uploading static website files to S3 bucket: {outputs['S3BucketName']}")
                        upload_success = upload_static_website(outputs['S3BucketName'], region, config)
                        if upload_success:
                            print("Successfully uploaded static website files to S3 bucket.")
                        else:
                            print("Warning: Failed to upload static website files to S3 bucket.")
                    
                    return {
                        'status': 'success', 
                        'message': 'No updates were performed on the stack.',
                        'outputs': outputs
                    }
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
                    template_has_bucket_policy = 'S3BucketPolicy' in load_cloudformation_yaml(template_body).get('Resources', {})
                    
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
                    
                    # Upload the static website files to the S3 bucket
                    print(f"Uploading static website files to S3 bucket: {outputs['S3BucketName']}")
                    upload_success = upload_static_website(outputs['S3BucketName'], region, config)
                    if upload_success:
                        print("Successfully uploaded static website files to S3 bucket.")
                    else:
                        print("Warning: Failed to upload static website files to S3 bucket.")
                
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
        
        # Configure the waiter with increased timeout for CloudFront distributions
        # CloudFront can take 15-30 minutes to deploy, so we need to increase the wait time
        waiter_config = {
            'Delay': 30,  # Check every 30 seconds instead of the default 15
            'MaxAttempts': 120  # Wait up to 60 minutes (120 * 30 seconds)
        }
        
        print(f"Using extended waiter configuration: {waiter_config}")
        waiter.wait(StackName=stack_name, WaiterConfig=waiter_config)
        
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
        if (solution_name == 'static_website' or solution_name == 'combined_website') and 'S3BucketName' in outputs:
            # Check if the template already has a bucket policy
            template_has_bucket_policy = 'S3BucketPolicy' in load_cloudformation_yaml(template_body).get('Resources', {})
            
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
            
            # Upload the static website files to the S3 bucket
            print(f"Uploading static website files to S3 bucket: {outputs['S3BucketName']}")
            upload_success = upload_static_website(outputs['S3BucketName'], region, config)
            if upload_success:
                print("Successfully uploaded static website files to S3 bucket.")
            else:
                print("Warning: Failed to upload static website files to S3 bucket.")
                
        # Handle combined_website solution - upload VOD content to the VOD bucket
        if solution_name == 'combined_website' and 'VodBucketName' in outputs:
            # Upload VOD content to the VOD bucket
            print(f"Uploading VOD content to S3 bucket: {outputs['VodBucketName']}")
            upload_success = upload_vod_content(outputs['VodBucketName'], region, config)
            if upload_success:
                print("Successfully uploaded VOD content to S3 bucket.")
            else:
                print("Warning: Failed to upload VOD content to S3 bucket.")
                
        # Handle combined_website solution - upload VOD content to the VOD bucket
        if solution_name == 'combined_website' and 'VodBucketName' in outputs:
            # Upload VOD content to the VOD bucket
            print(f"Uploading VOD content to S3 bucket: {outputs['VodBucketName']}")
            upload_success = upload_vod_content(outputs['VodBucketName'], region, config)
            if upload_success:
                print("Successfully uploaded VOD content to S3 bucket.")
            else:
                print("Warning: Failed to upload VOD content to S3 bucket.")
        
        return {
            'status': 'success',
            'message': f"Stack {operation} completed successfully!",
            'outputs': outputs
        }
    
    except Exception as e:
        print(f"Error deploying CloudFormation template: {e}")
        return {'status': 'error', 'message': str(e)}