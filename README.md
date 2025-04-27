# AWS Infrastructure Report Tool

A Python tool for generating reports about deployed AWS infrastructure, with a focus on cost analysis.

## Features

- Scan AWS resources in specified regions
- Analyze spot instance pricing
- Generate hourly and monthly cost estimates
- Output reports in JSON format
- Display formatted reports in the console

## Requirements

- Python 3.6+
- boto3
- PyYAML

## Installation

```bash
pip install boto3 pyyaml
```

## Configuration

Create a `config.yaml` file with the following structure:

```yaml
region: us-east-1  # Default AWS region to scan
```

## Usage

```bash
# Use region from config file
python aws_infra_report.py

# Override region from command line
python aws_infra_report.py --region us-west-2
```

## Output

Reports are saved to the `reports/` directory in JSON format and also displayed in the console.

