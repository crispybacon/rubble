#!/usr/bin/env python3
"""
Update Website Script

This script updates the static website with API endpoints and adds solution demonstrations.
"""

import argparse
import boto3
import os
import sys
import yaml
import re
from pathlib import Path


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Update Website Script')
    parser.add_argument('--config', type=str, default='config.yaml',
                        help='Path to configuration file')
    parser.add_argument('--stack_name', type=str,
                        help='CloudFormation stack name for the messaging solution')
    parser.add_argument('--static_website_stack', type=str,
                        help='Name of the static website stack to update')
    parser.add_argument('--streaming_stack', type=str,
                        help='CloudFormation stack name for the streaming media solution')
    parser.add_argument('--region', type=str,
                        help='AWS region (overrides config file)')
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


def get_api_endpoint(stack_name, region):
    """
    Get the API endpoint from CloudFormation stack outputs.
    
    Args:
        stack_name: Name of the CloudFormation stack
        region: AWS region
        
    Returns:
        str: API endpoint URL or None if not found
    """
    try:
        # Initialize CloudFormation client
        cfn = boto3.client('cloudformation', region_name=region)
        
        # Get stack outputs
        response = cfn.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0].get('Outputs', [])
        
        # Find the ApiEndpoint output
        for output in outputs:
            if output['OutputKey'] == 'ApiEndpoint':
                return output['OutputValue']
        
        print(f"Warning: ApiEndpoint not found in stack outputs for {stack_name}")
        return None
    except Exception as e:
        print(f"Error getting API endpoint from stack {stack_name}: {e}")
        return None


def get_streaming_endpoints(stack_name, region):
    """
    Get the streaming endpoints from CloudFormation stack outputs.
    
    Args:
        stack_name: Name of the CloudFormation stack
        region: AWS region
        
    Returns:
        dict: Dictionary containing streaming endpoints or None if not found
    """
    try:
        # Initialize CloudFormation client
        cfn = boto3.client('cloudformation', region_name=region)
        
        # Get stack outputs
        response = cfn.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0].get('Outputs', [])
        
        # Find the streaming endpoints
        endpoints = {}
        for output in outputs:
            if output['OutputKey'] == 'HlsEndpointUrl':
                endpoints['hls'] = output['OutputValue']
            elif output['OutputKey'] == 'DashEndpointUrl':
                endpoints['dash'] = output['OutputValue']
            elif output['OutputKey'] == 'MediaLiveInputUrl':
                endpoints['input'] = output['OutputValue']
            elif output['OutputKey'] == 'VodBucketName':
                endpoints['vod'] = output['OutputValue']
            elif output['OutputKey'] == 'CloudFrontDistributionId':
                endpoints['cloudfront_id'] = output['OutputValue']
            elif output['OutputKey'] == 'CloudFrontDistributionDomainName':
                endpoints['cloudfront_domain'] = output['OutputValue']
        
        if not endpoints:
            print(f"Warning: Streaming endpoints not found in stack outputs for {stack_name}")
            return None
        
        return endpoints
    except Exception as e:
        print(f"Error getting streaming endpoints from stack {stack_name}: {e}")
        return None


def update_index_html(api_endpoint, config):
    """
    Update the index.html file with the API endpoint.
    
    Args:
        api_endpoint: API endpoint URL
        config: Configuration dictionary
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        # Get the content directory from config
        static_website_dir = 'iac/static_website'
        content_dir_path = None
        
        if 'solutions' in config and 'static_website' in config['solutions']:
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
        
        # Find the index.html file
        index_path = website_dir / 'index.html'
        if not index_path.exists():
            print(f"Error: index.html not found in {website_dir}")
            return False
        
        # Read the index.html file
        with open(index_path, 'r') as f:
            content = f.read()
        
        # Replace the API endpoint placeholder
        if '${ApiEndpoint}' in content:
            content = content.replace('${ApiEndpoint}', api_endpoint)
            print(f"Updated API endpoint in index.html: {api_endpoint}")
        else:
            print("Warning: ${ApiEndpoint} placeholder not found in index.html")
        
        # Replace the email address placeholder if it exists
        if '${EmailAddress}' in content and 'messaging' in config and 'email' in config['messaging'] and 'destination' in config['messaging']['email']:
            email_address = config['messaging']['email']['destination']
            content = content.replace('${EmailAddress}', email_address)
            print(f"Updated email address in index.html: {email_address}")
        
        # Write the updated content back to the file
        with open(index_path, 'w') as f:
            f.write(content)
        
        print(f"Successfully updated index.html at {index_path}")
        return True
    except Exception as e:
        print(f"Error updating index.html: {e}")

def add_streaming_media_to_solution_demos(config):
    """
    Add the streaming media solution to the Solution Demonstrations section of the index.html file.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        # Get the content directory from config
        static_website_dir = 'iac/static_website'
        content_dir_path = None
        
        if 'solutions' in config and 'static_website' in config['solutions']:
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
        
        # Find the index.html file
        index_path = website_dir / 'index.html'
        if not index_path.exists():
            print(f"Error: index.html not found in {website_dir}")
            return False
        
        # Read the index.html file
        with open(index_path, 'r') as f:
            content = f.read()
        
        # Check if the streaming media solution is already in the file
        if 'AWS Media Services' in content:
            print("Streaming media solution already exists in index.html")
            return True
        
        # Find the Solution Demonstrations section
        solution_demos_pattern = r'<div class="solutionDemos">\s*<h2>\s*Solution Demonstrations\s*</h2>\s*<ul>(.*?)</ul>'
        match = re.search(solution_demos_pattern, content, re.DOTALL)
        
        if not match:
            print("Error: Solution Demonstrations section not found in index.html")
            return False
        
        # Get the existing solutions list
        solutions_list = match.group(1)
        
        # Create the new solution entry
        new_solution = """
      <li>
        <div class="jobPosition">
          <span class="bolded">
            AWS Media Services
          </span>
          <span>
            MediaLive, MediaPackage, CloudFront
          </span>
        </div>
        <div class="job-content">
          <div class="projectName bolded">
            <span>
              Live Streaming and Video on Demand
            </span>
          </div>
          <div class="smallText">
            <p>
              Live streaming and video on demand capabilities using AWS Media Services, with HLS and DASH delivery via CloudFront.
            </p>
          </div>
        </div>
      </li>"""
        
        # Add the new solution to the list
        updated_solutions_list = solutions_list + new_solution
        
        # Replace the old solutions list with the updated one
        updated_content = content.replace(solutions_list, updated_solutions_list)
        
        # Write the updated content back to the file
        with open(index_path, 'w') as f:
            f.write(updated_content)
        
        print(f"Successfully added streaming media solution to index.html at {index_path}")
        return True
    except Exception as e:
        print(f"Error adding streaming media solution to index.html: {e}")
        return False
def add_streaming_media_buttons(streaming_endpoints, config):
    """
    Add streaming media buttons to the index.html file.
    
    Args:
        streaming_endpoints: Dictionary containing streaming endpoints
        config: Configuration dictionary
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        # Get the content directory from config
        static_website_dir = 'iac/static_website'
        content_dir_path = None
        
        if 'solutions' in config and 'static_website' in config['solutions']:
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
        
        # Find the index.html file
        index_path = website_dir / 'index.html'
        if not index_path.exists():
            print(f"Error: index.html not found in {website_dir}")
            return False
        
        # Read the index.html file
        with open(index_path, 'r') as f:
            content = f.read()
        
        # Check if the streaming media buttons are already in the file
        if 'id="streaming-buttons"' in content:
            print("Streaming media buttons already exist in index.html")
            
            # Update the endpoints if they exist
            if 'hls' in streaming_endpoints:
                content = re.sub(r'data-hls-url="[^"]*"', f'data-hls-url="{streaming_endpoints["hls"]}"', content)
            if 'dash' in streaming_endpoints:
                content = re.sub(r'data-dash-url="[^"]*"', f'data-dash-url="{streaming_endpoints["dash"]}"', content)
            if 'vod' in streaming_endpoints:
                content = re.sub(r'data-vod-bucket="[^"]*"', f'data-vod-bucket="{streaming_endpoints["vod"]}"', content)
            
            # Write the updated content back to the file
            with open(index_path, 'w') as f:
                f.write(content)
            
            print(f"Updated streaming media endpoints in index.html at {index_path}")
            return True
        
        # Find the communication buttons section
        comm_buttons_pattern = r'<div class="communication-buttons">(.*?)</div>'
        match = re.search(comm_buttons_pattern, content, re.DOTALL)
        
        if not match:
            print("Error: Communication buttons section not found in index.html")
            return False
        
        # Get the existing buttons
        existing_buttons = match.group(0)
        
        # Create the streaming media buttons
        streaming_buttons = f"""<div class="streaming-buttons" id="streaming-buttons">
  <button class="btn btn-primary" onclick="playLiveStream()">
    <i class="fas fa-broadcast-tower"></i> Live Stream
  </button>
  <button class="btn btn-primary" onclick="playVOD()">
    <i class="fas fa-film"></i> Video on Demand
  </button>
</div>

<div id="video-modal" class="modal">
  <div class="modal-content">
    <span class="close-button" onclick="closeVideoModal()">&times;</span>
    <h2 id="video-title">Video Player</h2>
    <video id="video-player" controls></video>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<script>
  // Store streaming endpoints
  const streamingEndpoints = {{
    hls: "{streaming_endpoints.get('hls', '')}",
    dash: "{streaming_endpoints.get('dash', '')}",
    vod: "{streaming_endpoints.get('vod', '')}"
  }};
  
  // Get modal elements
  const videoModal = document.getElementById('video-modal');
  const videoPlayer = document.getElementById('video-player');
  const videoTitle = document.getElementById('video-title');
  
  // Function to play live stream
  function playLiveStream() {{
    videoTitle.textContent = 'Live Stream';
    
    if (Hls.isSupported()) {{
      const hls = new Hls();
      hls.loadSource(streamingEndpoints.hls);
      hls.attachMedia(videoPlayer);
      hls.on(Hls.Events.MANIFEST_PARSED, function() {{
        videoPlayer.play();
      }});
    }} else if (videoPlayer.canPlayType('application/vnd.apple.mpegurl')) {{
      // For Safari
      videoPlayer.src = streamingEndpoints.hls;
      videoPlayer.play();
    }}
    
    videoModal.style.display = 'block';
  }}
  
  // Function to play VOD
  function playVOD() {{
    videoTitle.textContent = 'Video on Demand';
    
    // For demo purposes, we'll use a sample video
    const vodUrl = 'https://d2zihajmogu5jn.cloudfront.net/big-buck-bunny/master.m3u8';
    
    if (Hls.isSupported()) {{
      const hls = new Hls();
      hls.loadSource(vodUrl);
      hls.attachMedia(videoPlayer);
      hls.on(Hls.Events.MANIFEST_PARSED, function() {{
        videoPlayer.play();
      }});
    }} else if (videoPlayer.canPlayType('application/vnd.apple.mpegurl')) {{
      // For Safari
      videoPlayer.src = vodUrl;
      videoPlayer.play();
    }}
    
    videoModal.style.display = 'block';
  }}
  
  // Function to close the video modal
  function closeVideoModal() {{
    videoModal.style.display = 'none';
    videoPlayer.pause();
    videoPlayer.src = '';
  }}
  
  // Close modal when clicking outside of it
  window.onclick = function(event) {{
    if (event.target == videoModal) {{
      closeVideoModal();
    }}
  }};
</script>

<style>
  .streaming-buttons {{
    display: flex;
    gap: 10px;
    margin-left: 20px;
  }}
  
  .streaming-buttons .btn-primary {{
    background-color: #0066cc;
    border-color: #0059b3;
  }}
  
  .streaming-buttons .btn-primary:hover {{
    background-color: #0059b3;
    border-color: #004c99;
  }}
  
  .modal {{
    display: none;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    overflow: auto;
    background-color: rgba(0,0,0,0.7);
  }}
  
  .modal-content {{
    background-color: #fefefe;
    margin: 10% auto;
    padding: 20px;
    border: 1px solid #888;
    width: 80%;
    max-width: 800px;
    border-radius: 5px;
  }}
  
  .close-button {{
    color: #aaa;
    float: right;
    font-size: 28px;
    font-weight: bold;
    cursor: pointer;
  }}
  
  .close-button:hover {{
    color: black;
  }}
  
  #video-player {{
    width: 100%;
    max-height: 450px;
    margin-top: 15px;
  }}
</style>"""
        
        # Add the streaming buttons after the communication buttons
        updated_content = content.replace(existing_buttons, existing_buttons + streaming_buttons)
        
        # Write the updated content back to the file
        with open(index_path, 'w') as f:
            f.write(updated_content)
        
        print(f"Successfully added streaming media buttons to index.html at {index_path}")
        return True
    except Exception as e:
        print(f"Error adding streaming media buttons to index.html: {e}")
        return False
def add_messaging_to_solution_demos(config):
    """
    Add the messaging solution to the Solution Demonstrations section of the index.html file.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        # Get the content directory from config
        static_website_dir = 'iac/static_website'
        content_dir_path = None
        
        if 'solutions' in config and 'static_website' in config['solutions']:
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
        
        # Find the index.html file
        index_path = website_dir / 'index.html'
        if not index_path.exists():
            print(f"Error: index.html not found in {website_dir}")
            return False
        
        # Read the index.html file
        with open(index_path, 'r') as f:
            content = f.read()
        
        # Check if the messaging solution is already in the file
        if 'AWS End User Messaging' in content:
            print("Messaging solution already exists in index.html")
            return True
        
        # Find the Solution Demonstrations section
        solution_demos_pattern = r'<div class="solutionDemos">\s*<h2>\s*Solution Demonstrations\s*</h2>\s*<ul>(.*?)</ul>'
        match = re.search(solution_demos_pattern, content, re.DOTALL)
        
        if not match:
            print("Error: Solution Demonstrations section not found in index.html")
            return False
        
        # Get the existing solutions list
        solutions_list = match.group(1)
        
        # Create the new solution entry
        new_solution = """
      <li>
        <div class="jobPosition">
          <span class="bolded">
            AWS End User Messaging
          </span>
          <span>
            Amazon SES, PinpointSMSVoice
          </span>
        </div>
        <div class="job-content">
          <div class="projectName bolded">
            <span>
              Contact Form with Email and SMS
            </span>
          </div>
          <div class="smallText">
            <p>
              Direct email contact via mailto link, SMS messaging via API Gateway and Lambda, and email contact form with SES.
            </p>
          </div>
        </div>
      </li>"""
        
        # Add the new solution to the list
        updated_solutions_list = solutions_list + new_solution
        
        # Replace the old solutions list with the updated one
        updated_content = content.replace(solutions_list, updated_solutions_list)
        
        # Write the updated content back to the file
        with open(index_path, 'w') as f:
            f.write(updated_content)
        
        print(f"Successfully added messaging solution to index.html at {index_path}")
        return True
    except Exception as e:
        print(f"Error adding messaging solution to index.html: {e}")
        return False
def main():
    """Main function to run the update website script."""
    # Parse arguments and load configuration
    args = parse_arguments()
    config = load_config(args.config)
    
    # Determine which region to use (CLI overrides config)
    region = args.region if args.region else config.get('region', 'us-east-1')
    
    # Check if we need to update the static website with messaging API endpoint
    if args.stack_name:
        # Get the API endpoint from the stack outputs
        api_endpoint = get_api_endpoint(args.stack_name, region)
        
        if api_endpoint:
            print(f"Found API endpoint: {api_endpoint}")
            
            # Add the static_website_stack parameter to the config if provided
            if args.static_website_stack:
                if 'solutions' not in config:
                    config['solutions'] = {}
                if 'messaging' not in config['solutions']:
                    config['solutions']['messaging'] = {}
                if 'parameters' not in config['solutions']['messaging'] or config['solutions']['messaging']['parameters'] is None:
                    config['solutions']['messaging']['parameters'] = {}
                config['solutions']['messaging']['parameters']['StaticWebsiteStackName'] = args.static_website_stack
            
            # Update the index.html file with the API endpoint
            if update_index_html(api_endpoint, config):
                print("Successfully updated index.html with API endpoint.")
            else:
                print("Failed to update index.html with API endpoint.")
                sys.exit(1)
            
            # Add the messaging solution to the Solution Demonstrations section
            if add_messaging_to_solution_demos(config):
                print("Successfully added messaging solution to Solution Demonstrations section.")
            else:
                print("Failed to add messaging solution to Solution Demonstrations section.")
                sys.exit(1)
        else:
            print("Error: Could not find API endpoint in stack outputs.")
            sys.exit(1)
    
    # Check if we need to update the static website with streaming media endpoints
    if args.streaming_stack:
        # Get the streaming endpoints from the stack outputs
        streaming_endpoints = get_streaming_endpoints(args.streaming_stack, region)
        
        if streaming_endpoints:
            print(f"Found streaming endpoints: {streaming_endpoints}")
            
            # Add the streaming media solution to the Solution Demonstrations section
            if add_streaming_media_to_solution_demos(config):
                print("Successfully added streaming media solution to Solution Demonstrations section.")
            else:
                print("Failed to add streaming media solution to Solution Demonstrations section.")
                sys.exit(1)
            
            # Add the streaming media buttons to the index.html file
            if add_streaming_media_buttons(streaming_endpoints, config):
                print("Successfully added streaming media buttons to index.html.")
            else:
                print("Failed to add streaming media buttons to index.html.")
                sys.exit(1)
        else:
            print("Error: Could not find streaming endpoints in stack outputs.")
            sys.exit(1)


if __name__ == "__main__":
    main()

