import boto3
import yaml
import json
import os
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
        
        # Add messaging parameters if they exist in the config
        if 'messaging' in config:
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
                try:
                    waiter.wait(
                        StackName=stack_name,
                        ChangeSetName=change_set_name
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
        
        return {
            'status': 'success',
            'message': f"Stack {operation} completed successfully!",
            'outputs': outputs
        }
    
    except Exception as e:
        print(f"Error deploying CloudFormation template: {e}")
        return {'status': 'error', 'message': str(e)}