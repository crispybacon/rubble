# Static Website with CloudFormation

This directory contains both the static website content and CloudFormation templates for deploying the website infrastructure.

## Directory Structure

- `/content` - Contains the actual static website files (HTML, CSS, images) that will be uploaded to S3
- `cloudformation-template.yaml` - CloudFormation template for deploying the website infrastructure (placeholder)

## CloudFormation Template

The CloudFormation template in this directory is used to define the AWS infrastructure required for hosting the static website. This template is NOT uploaded to S3 when using the `--upload_resume` flag with the AWS Infrastructure Report Tool.

## Uploading Content

When using the AWS Infrastructure Report Tool with the `--upload_resume` flag, only the files in the `/content` directory will be uploaded to the specified S3 bucket. The CloudFormation template will remain local.

## Usage

1. Deploy the infrastructure using the CloudFormation template
2. Upload the website content using the AWS Infrastructure Report Tool:

```bash
python aws_infra_report.py --upload_resume --s3_bucket your-bucket-name
```