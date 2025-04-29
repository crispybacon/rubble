# AWS Infrastructure Report Tool

A Python tool for generating reports about deployed AWS infrastructure, with a focus on cost analysis. The tool also provides functionality to deploy and manage various AWS solutions.

## Recent Fixes

### AwsRegion Parameter Fix

Fixed an issue where the deployment would fail with the error:
```
Error deploying CloudFormation template: An error occurred (ValidationError) when calling the CreateStack operation: Parameters: [AwsRegion] do not exist in the template
```

The fix ensures that the `AwsRegion` parameter is only added to CloudFormation templates that actually define this parameter. Previously, the code was unconditionally adding this parameter to all templates, causing validation errors for templates that didn't include it.

## Features

- Scan AWS resources in specified regions
- Analyze spot instance pricing
- Generate hourly and monthly cost estimates
- Output reports in JSON format
- Display formatted reports in the console
- Deploy and manage AWS solutions using CloudFormation
- Update existing CloudFormation stacks with changes
- Automatic bucket policy configuration for S3 buckets to allow CloudFront access
- SMS and email contact forms for static website

## Requirements

- Python 3.6+
- boto3
- PyYAML
- AWS CLI configured with appropriate permissions

## Installation

```bash
pip install boto3 pyyaml
```

## Configuration

Create a `config.yaml` file with the following structure:

```yaml
region: us-east-1  # Default AWS region to scan
solutions:
  static_website:
    template_path: "iac/static_website/template.yaml"
    deployed_dir: "iac/deployed"
    content_dir: "iac/static_website/content"
    parameters:
      BucketNamePrefix: "your-bucket-prefix"
      OriginShieldRegion: "us-east-1"
  messaging:
    template_path: "iac/messaging/template.yaml"
    deployed_dir: "iac/deployed"
    parameters:
      # No additional parameters needed as they are pulled from the messaging section
s3:
  bucket: "your-s3-bucket-name"
messaging:
  email:
    destination: "your-email@example.com"
  sms:
    destination: "+12345678901"  # Must be in E.164 format
    country: "US"  # ISO 3166-1 alpha-2 code
```

## Usage

```bash
# Use region from config file
python aws_infra_report.py

# Override region from command line
python aws_infra_report.py --region us-west-2

# Deploy a CloudFormation stack for a solution
python aws_infra_report.py --deploy static_website --stack_name your-stack-name

# Update an existing CloudFormation stack with changes
python aws_infra_report.py --deploy static_website --stack_name your-stack-name --update

# Deploy the messaging solution for SMS and email contact forms
python aws_infra_report.py --deploy messaging --stack_name your-messaging-stack --static_website_stack your-static-website-stack

# Update an existing messaging solution
python aws_infra_report.py --deploy messaging --stack_name your-messaging-stack --static_website_stack your-static-website-stack --update

# Note: The bucket policy is automatically attached during CloudFormation deployment.
# The following commands are only needed if you want to manually update an existing bucket policy:

# Manually attach bucket policy to allow CloudFront to access S3 bucket
python aws_infra_report.py --attach_bucket_policy --s3_bucket your-s3-bucket-name

# Manually attach bucket policy with specific CloudFront distribution ID
python aws_infra_report.py --attach_bucket_policy --s3_bucket your-s3-bucket-name --cloudfront_distribution_id EDFDVBD6EXAMPLE
```

## Output

Reports are saved to the `reports/` directory in JSON format and also displayed in the console.

## Deployed Solutions

<details>
<summary><strong>Static Website</strong> - Professional resume/portfolio website with CloudFront distribution</summary>

### Static Website Solution

This solution deploys a professional resume/portfolio website using AWS CloudFormation. The architecture includes:

- S3 bucket for hosting static content
- CloudFront distribution for global content delivery
- WAF (Web Application Firewall) for security
- CloudWatch Logs for monitoring
- Origin Shield for improved caching and reduced origin load
- SMS and email contact forms with AWS End User Messaging
- API Gateway and Lambda for processing contact form submissions

The static website features a responsive design with collapsible sections for work experience and solution demonstrations.

### Deployment Instructions

1. Update the configuration in `config.yaml` with your preferred settings:
   ```yaml
   solutions:
     static_website:
       parameters:
         BucketNamePrefix: "your-bucket-prefix"
         OriginShieldRegion: "us-east-1"
   s3:
     bucket: "your-s3-bucket-name"
   ```

2. Deploy the CloudFormation stack:
   ```bash
   python aws_infra_report.py --deploy static_website --stack_name your-stack-name
   ```

3. Upload the website content to the S3 bucket:
   ```bash
   python aws_infra_report.py --upload_resume --s3_bucket your-s3-bucket-name
   ```

4. The CloudFormation template automatically attaches a bucket policy that allows CloudFront to access the S3 bucket. No additional action is required for this step.

5. Access your website using the CloudFront URL provided in the deployment output.

### Customization

To customize the website content:
1. Modify the HTML, CSS, and image files in the `iac/static_website` directory
2. Re-upload the content using the `--upload_resume` flag

### Contact Form Configuration

The static website includes SMS and email contact forms that allow visitors to send messages directly to you. To configure these forms:

1. Update the `messaging` section in your `config.yaml` file:
   ```yaml
   messaging:
     email:
       destination: "your-email@example.com"  # The email address where form submissions will be sent
     sms:
       destination: "+12345678901"  # Your phone number in E.164 format (e.g., +12345678901)
       country: "US"  # Currently only US numbers are supported
   ```

2. Deploy the messaging solution:
   ```bash
   python aws_infra_report.py --deploy messaging --stack_name your-messaging-stack
   ```

3. After deployment, the contact form functionality will be available on your website. Visitors can click the email or SMS icons in the top right corner to open the respective contact forms.

**Note:** The email address specified in the configuration must be verified in Amazon SES before it can be used for sending emails. The verification process is initiated automatically during deployment, but you'll need to check your email and confirm the verification.

### Updating Deployed Solutions

To update an existing CloudFormation stack with changes:

```bash
# Update the static website stack
python aws_infra_report.py --deploy static_website --stack_name your-stack-name --update

# Update the messaging stack
python aws_infra_report.py --deploy messaging --stack_name your-messaging-stack --static_website_stack your-static-website-stack --update
```

When you update the messaging solution, the static website will be automatically updated with the new API endpoint and the messaging solution will be added to the Solution Demonstrations section.

### Exporting Deployed Template

To export the deployed CloudFormation template for reference:
```bash
python aws_infra_report.py --deploy static_website --stack_name your-stack-name --export_template
```
The exported template will be saved to the `iac/deployed` directory.

</details>

<details>
<summary><strong>AWS End User Messaging</strong> - SMS and email contact forms with AWS messaging services</summary>

### AWS End User Messaging Solution

This solution deploys the infrastructure needed for SMS and email contact forms using AWS messaging services. The architecture includes:

- AWS PinpointSMSVoice for SMS messaging
- Amazon SES for email delivery
- API Gateway for handling form submissions
- Lambda function for processing messages
- KMS for encryption
- CloudWatch Logs for monitoring

### Deployment Instructions

1. Update the configuration in `config.yaml` with your messaging settings:
   ```yaml
   messaging:
     email:
       destination: "your-email@example.com"  # The email address where form submissions will be sent
     sms:
       destination: "+12345678901"  # Your phone number in E.164 format (e.g., +12345678901)
       country: "US"  # Currently only US numbers are supported
   ```

2. Deploy the CloudFormation stack:
   ```bash
   python aws_infra_report.py --deploy messaging --stack_name your-messaging-stack --static_website_stack your-static-website-stack
   ```
   
   **Note:** The `--static_website_stack` parameter is required and should specify the name of the static website stack that you want to update with the messaging API endpoint. This is necessary because there could be multiple static website deployments in the same AWS account.

3. The deployment will automatically update the static website with the API endpoint for the contact forms. If you've already deployed the static website, the messaging solution will be added to the Solution Demonstrations section.

4. If you need to update the messaging solution later:
   ```bash
   python aws_infra_report.py --deploy messaging --stack_name your-messaging-stack --update
   ```

### Security Considerations

- All data is encrypted using KMS
- API Gateway is configured with appropriate CORS headers
- Lambda function has minimal IAM permissions
- Dead Letter Queue for handling failed message deliveries

</details>

<!-- Additional solutions can be added here following the same pattern -->














