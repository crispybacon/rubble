def deploy_cloudformation_template(solution_name, stack_name, region, config, export_template=False, force_update=False):
    """
    Deploy a CloudFormation template for a specific solution.
    
    Args:
        solution_name: Name of the solution to deploy (e.g., 'static_website')
        stack_name: Name of the CloudFormation stack
        region: AWS region for deployment
        config: Configuration dictionary
        export_template: Whether to export the template after deployment
        force_update: Whether to force an update even if no changes are detected
        
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