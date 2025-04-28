# AWS Infrastructure Report Tool

A Python tool for generating reports about deployed AWS infrastructure, with a focus on cost analysis. The tool also provides functionality to deploy and manage various AWS solutions.

## Features

- Scan AWS resources in specified regions
- Analyze spot instance pricing
- Generate hourly and monthly cost estimates
- Output reports in JSON format
- Display formatted reports in the console
- Deploy and manage AWS solutions using CloudFormation
- Automatic bucket policy configuration for S3 buckets to allow CloudFront access

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
s3:
  bucket: "your-s3-bucket-name"
```

## Usage

```bash
# Use region from config file
python aws_infra_report.py

# Override region from command line
python aws_infra_report.py --region us-west-2

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

### Exporting Deployed Template

To export the deployed CloudFormation template for reference:
```bash
python aws_infra_report.py --deploy static_website --stack_name your-stack-name --export_template
```
The exported template will be saved to the `iac/deployed` directory.

</details>

<!-- Additional solutions can be added here following the same pattern -->









