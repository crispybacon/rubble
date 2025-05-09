# AWS Resource Manager

A Python tool for managing AWS resources, including generating reports about deployed infrastructure with a focus on cost analysis. The tool also provides functionality to deploy and manage various AWS solutions.

## Recent Fixes

### Combined Website and Streaming Media Solution

Added a new combined solution that deploys both the static website and streaming media resources in a single CloudFormation stack. This eliminates the need for the Lambda function that was previously used to update the CloudFront distribution with streaming media origins and behaviors. The combined solution:

1. Creates separate S3 buckets for static web content and streaming media content
2. Configures a single CloudFront distribution with origins for both static content and streaming media
3. Sets up path-based behaviors for live streaming and video on demand
4. Deploys all resources in a single stack, simplifying the deployment process

To deploy the combined solution:
```bash
python aws_resource_manager.py --deploy combined_website --stack_name your-combined-stack-name
```

### CloudFront Distribution Deployment Timeout Fix

Fixed an issue where the CloudFront distribution would fail to deploy with the error:
```
Resource handler returned message: "Exceeded attempts to wait" (RequestToken: 7c3bf81b-9f74-3289-9208-7329a4ec5e6e, HandlerErrorCode: NotStabilized)
```

The fix increases the CloudFormation waiter timeout configuration to accommodate the longer deployment time needed for CloudFront distributions. CloudFront distributions can take 15-30 minutes to fully deploy and stabilize, which exceeds the default CloudFormation waiter timeout. The following changes were made:

1. Increased the waiter delay from 15 to 30 seconds
2. Increased the maximum number of attempts from 40 to 120 (allowing up to 60 minutes for deployment)
3. Added custom waiter configurations for all CloudFormation operations (stack creation, updates, and change sets)

### CloudFrontRealTimeLogConfig SamplingRate Fix

Fixed an issue where the CloudFrontRealTimeLogConfig resource would fail to create with the error:
```
Resource handler returned message: "Model validation failed (#: required key [SamplingRate] not found)" (RequestToken: d609279e-700d-33bc-b036-190e196ec859, HandlerErrorCode: InvalidRequest)
```

The fix adds the required SamplingRate parameter to the CloudFrontRealTimeLogConfig resource in the CloudFormation template. The SamplingRate parameter specifies what percentage of requests should be logged in real-time (value set to 100 for full logging).

### AwsRegion Parameter Fix

Fixed an issue where the deployment would fail with the error:
```
Error deploying CloudFormation template: An error occurred (ValidationError) when calling the CreateStack operation: Parameters: [AwsRegion] do not exist in the template
```

The fix ensures that the `AwsRegion` parameter is only added to CloudFormation templates that actually define this parameter. Previously, the code was unconditionally adding this parameter to all templates, causing validation errors for templates that didn't include it.

### Deployment Order Fix

Fixed an issue where the static_website stack would fail to deploy with the error:
```
The resource ContactFormFunction is in a CREATE_FAILED state
This AWS::Lambda::Function resource is in a CREATE_FAILED state.
Resource handler returned message: "The provided execution role does not have permissions to call SendMessage on SQS"
```

The fix removes the dependency on SQS in the static_website stack, allowing it to be deployed before the messaging stack. The full SMS and Email notification infrastructure is now only installed when the AWS End User Messaging stack is deployed.

**Important:** To ensure proper functionality, deploy the stacks in this order:
1. First deploy the static_website stack
2. Then deploy the messaging stack

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
      OriginShieldRegion: "us-east-2"
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
python aws_resource_manager.py

# Override region from command line
python aws_resource_manager.py --region us-west-2

# Deploy a CloudFormation stack for a solution
python aws_resource_manager.py --deploy static_website --stack_name your-stack-name

# Update an existing CloudFormation stack with changes
python aws_resource_manager.py --deploy static_website --stack_name your-stack-name --update

# Deploy the messaging solution for SMS and email contact forms
python aws_resource_manager.py --deploy messaging --stack_name your-messaging-stack --static_website_stack your-static-website-stack

# Update an existing messaging solution
python aws_resource_manager.py --deploy messaging --stack_name your-messaging-stack --static_website_stack your-static-website-stack --update

# Note: The bucket policy is automatically attached during CloudFormation deployment.
# The following commands are only needed if you want to manually update an existing bucket policy:

# Manually attach bucket policy to allow CloudFront to access S3 bucket
python aws_resource_manager.py --attach_bucket_policy --s3_bucket your-s3-bucket-name

# Manually attach bucket policy with specific CloudFront distribution ID
python aws_resource_manager.py --attach_bucket_policy --s3_bucket your-s3-bucket-name --cloudfront_distribution_id EDFDVBD6EXAMPLE
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
         OriginShieldRegion: "us-east-2"
   s3:
     bucket: "your-s3-bucket-name"
   ```

2. Deploy the static_website CloudFormation stack first:
   ```bash
   python aws_resource_manager.py --deploy static_website --stack_name your-stack-name
   ```

3. Upload the website content to the S3 bucket:
   ```bash
   python aws_resource_manager.py --upload_resume --s3_bucket your-s3-bucket-name
   ```

4. The CloudFormation template automatically attaches a bucket policy that allows CloudFront to access the S3 bucket. No additional action is required for this step.

5. Deploy the messaging stack to enable the contact form functionality:
   ```bash
   python aws_resource_manager.py --deploy messaging --stack_name your-messaging-stack --static_website_stack your-stack-name
   ```

6. Access your website using the CloudFront URL provided in the deployment output.

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
       originator_id: "YourName"    # Sender ID for SMS messages (max 11 alphanumeric characters)
   ```

2. Make sure you've already deployed the static_website stack first:
   ```bash
   python aws_resource_manager.py --deploy static_website --stack_name your-stack-name
   ```

3. Then deploy the messaging solution:
   ```bash
   python aws_resource_manager.py --deploy messaging --stack_name your-messaging-stack --static_website_stack your-stack-name
   ```

4. After deployment, the contact form functionality will be available on your website. Visitors can click the email or SMS icons in the top right corner to open the respective contact forms.

**Note:** The email address specified in the configuration must be verified in Amazon SES before it can be used for sending emails. The verification process is initiated automatically during deployment, but you'll need to check your email and confirm the verification.

### Updating Deployed Solutions

To update an existing CloudFormation stack with changes:

```bash
# Update the static website stack
python aws_resource_manager.py --deploy static_website --stack_name your-stack-name --update

# Update the messaging stack
python aws_resource_manager.py --deploy messaging --stack_name your-messaging-stack --static_website_stack your-static-website-stack --update
```

When you update the messaging solution, the static website will be automatically updated with the new API endpoint and the messaging solution will be added to the Solution Demonstrations section.

### Exporting Deployed Template

To export the deployed CloudFormation template for reference:
```bash
python aws_resource_manager.py --deploy static_website --stack_name your-stack-name --export_template
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
       originator_id: "YourName"    # Sender ID for SMS messages (max 11 alphanumeric characters)
   ```

2. First, make sure you've deployed the static_website stack:
   ```bash
   python aws_resource_manager.py --deploy static_website --stack_name your-static-website-stack
   ```

3. Then deploy the messaging CloudFormation stack:
   ```bash
   python aws_resource_manager.py --deploy messaging --stack_name your-messaging-stack --static_website_stack your-static-website-stack
   ```
   
   **Important:** The `--static_website_stack` parameter is required and should specify the name of the static website stack that you want to update with the messaging API endpoint. This is necessary because there could be multiple static website deployments in the same AWS account.

4. The deployment will automatically update the static website with the API endpoint for the contact forms. If you've already deployed the static website, the messaging solution will be added to the Solution Demonstrations section.

5. If you need to update the messaging solution later:
   ```bash
   python aws_resource_manager.py --deploy messaging --stack_name your-messaging-stack --static_website_stack your-static-website-stack --update
   ```

### Security Considerations

- All data is encrypted using KMS
- API Gateway is configured with appropriate CORS headers
- Lambda function has minimal IAM permissions
- Dead Letter Queue for handling failed message deliveries

</details>

<details>
<summary><strong>Combined Website and Streaming Media</strong> - Single stack deployment of static website and streaming media</summary>

### Combined Website and Streaming Media Solution

This solution deploys a static website with streaming media capabilities using a single CloudFormation stack. The architecture includes:

- Separate S3 buckets for static content and VOD content
- CloudFront distribution with origins for static content, live streaming, and VOD
- MediaLive for ingesting and transcoding live video
- MediaPackage for packaging and protecting live content
- Path-based behaviors for different content types

### Deployment Instructions

1. Update the configuration in `config.yaml` with your preferred settings:
   ```yaml
   solutions:
     combined_website:
       parameters:
         BucketNamePrefix: "your-bucket-prefix"
         OriginShieldRegion: "us-east-2"
         LiveInputType: "RTMP_PUSH"
         LiveInputWhitelistCidr: "0.0.0.0/0"  # Restrict this to your IP range for production
   ```

2. Deploy the combined CloudFormation stack:
   ```bash
   python aws_resource_manager.py --deploy combined_website --stack_name your-combined-stack-name
   ```

3. Upload the website content to the S3 bucket:
   ```bash
   python aws_resource_manager.py --upload_resume --s3_bucket your-s3-bucket-name
   ```

4. Access your website using the CloudFront URL provided in the deployment output.

### Using the Streaming Media Features

#### Live Streaming

1. To stream live content, use a streaming software like OBS Studio or FFmpeg to push to the MediaLive input URL provided in the CloudFormation outputs.
2. Configure your streaming software with the following settings:
   - Protocol: RTMP (or as configured in your deployment)
   - URL: The MediaLive input URL from the CloudFormation outputs
   - Stream key: As provided in the MediaLive input URL
   - Video codec: H.264
   - Audio codec: AAC
   - Resolution: 1080p or 720p recommended
   - Bitrate: 5 Mbps or as needed for your quality requirements

3. On your website, click the "Live Stream" button to view the live stream.

#### Video on Demand (VOD)

1. Upload your video files to the S3 bucket created for VOD content (provided in the CloudFormation outputs).
2. The videos will be automatically processed and made available for streaming.
3. On your website, click the "Video on Demand" button to access the VOD content.

### Security Considerations

- The default configuration allows streaming input from any IP address (0.0.0.0/0). For production use, restrict the `LiveInputWhitelistCidr` parameter to your specific IP range.
- All content is delivered via CloudFront with HTTPS for secure transmission.
- Static web content and streaming media content are stored in separate S3 buckets for enhanced security.
- All S3 buckets have public access blocked and are only accessible through CloudFront.

### Updating the Deployed Solution

To update an existing CloudFormation stack with changes:

```bash
python aws_resource_manager.py --deploy combined_website --stack_name your-combined-stack-name --update
```

</details>

<!-- Additional solutions can be added here following the same pattern -->

<details>
<summary><strong>AWS Media Services</strong> - Live Streaming and Video on Demand with AWS Media Services</summary>

### AWS Media Services Solution

This solution deploys the infrastructure needed for live streaming and video on demand using AWS Media Services. The architecture includes:

- AWS Elemental MediaLive for ingesting and transcoding live video
- AWS Elemental MediaPackage for packaging and protecting live content
- S3 bucket for storing VOD content
- CloudFront for delivering both live streams and VOD content
- Security groups for controlling access to the streaming infrastructure

### Deployment Instructions

1. Update the configuration in `config.yaml` with your preferred settings:
   ```yaml
   solutions:
     streaming_media:
       parameters:
         LiveInputType: "RTMP_PUSH"  # Options: RTMP_PUSH, RTP_PUSH, URL_PULL
         LiveInputWhitelistCidr: "0.0.0.0/0"  # Restrict this to your IP range for production
   ```

2. First, make sure you've deployed the static_website stack:
   ```bash
   python aws_resource_manager.py --deploy static_website --stack_name your-static-website-stack
   ```

3. Then deploy the streaming media CloudFormation stack:
   ```bash
   python aws_resource_manager.py --deploy streaming_media --stack_name your-streaming-media-stack --static_website_stack your-static-website-stack
   ```

4. The deployment will automatically update the static website with streaming media buttons and add the solution to the Solution Demonstrations section.

5. If you need to update the streaming media solution later:
   ```bash
   python aws_resource_manager.py --deploy streaming_media --stack_name your-streaming-media-stack --static_website_stack your-static-website-stack --update
   ```

### Using the Streaming Media Solution

#### Live Streaming

1. To stream live content, use a streaming software like OBS Studio or FFmpeg to push to the MediaLive input URL provided in the CloudFormation outputs.
2. Configure your streaming software with the following settings:
   - Protocol: RTMP (or as configured in your deployment)
   - URL: The MediaLive input URL from the CloudFormation outputs
   - Stream key: As provided in the MediaLive input URL
   - Video codec: H.264
   - Audio codec: AAC
   - Resolution: 1080p or 720p recommended
   - Bitrate: 5 Mbps or as needed for your quality requirements

3. On your website, click the "Live Stream" button to view the live stream.

#### Video on Demand (VOD)

1. Upload your video files to the S3 bucket created for VOD content (provided in the CloudFormation outputs).
2. The videos will be automatically processed and made available for streaming.
3. On your website, click the "Video on Demand" button to access the VOD content.

### Security Considerations

- The default configuration allows streaming input from any IP address (0.0.0.0/0). For production use, restrict the `LiveInputWhitelistCidr` parameter to your specific IP range.
- All content is delivered via CloudFront with HTTPS for secure transmission.
- Consider implementing token-based authentication for sensitive content.

### Troubleshooting

- If the live stream doesn't appear, check that your streaming software is correctly configured and connected to the MediaLive input URL.
- For VOD issues, verify that the video files are properly uploaded to the S3 bucket and have the correct permissions.
- Check CloudWatch Logs for MediaLive and MediaPackage for any error messages.

</details>










