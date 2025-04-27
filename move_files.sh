#!/bin/bash
# Script to move static website files to the content directory

# Create the content directory if it doesn't exist
mkdir -p /workspace/iac/static_website/content

# Copy the files to the content directory
cp /workspace/iac/static_website/index.html /workspace/iac/static_website/content/
cp /workspace/iac/static_website/index.css /workspace/iac/static_website/content/
cp /workspace/iac/static_website/me.png /workspace/iac/static_website/content/

echo "Files copied to content directory"