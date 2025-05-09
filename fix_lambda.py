#!/usr/bin/env python3

# Read the template file
with open('iac/streaming_media/template.yaml', 'r') as file:
    content = file.read()

# Find the Lambda function code
lambda_start = content.find("ZipFile: |")
lambda_end = content.find("UpdateCloudFrontRole:", lambda_start)
lambda_code = content[lambda_start:lambda_end]

# Check for syntax error in the result dictionary
import re
result_dict = re.search(r"result = \{.*?'DomainName': response\['Distribution'\]\['DomainName'\](.*?)\s+\}", lambda_code, re.DOTALL)
if result_dict:
    extra_chars = result_dict.group(1).strip()
    if extra_chars:
        print(f"Found extra characters in result dictionary: '{extra_chars}'")
    else:
        print("No extra characters found in result dictionary")

# Create a fixed version with a corrected Lambda function
# The issue is likely a syntax error in the Lambda function code
fixed_content = content.replace(
    "                        'DomainName': response['Distribution']['DomainName']",
    "                        'DomainName': response['Distribution']['DomainName']"
)

# Check for a return statement that might be in the wrong place
# This is a common issue that can cause the function to exit early
lines = lambda_code.split('\n')
for i, line in enumerate(lines):
    if "return" in line and i > 0 and i < len(lines) - 1:
        prev_line = lines[i-1].strip()
        next_line = lines[i+1].strip()
        if prev_line.endswith("cfnresponse.send") or "cfnresponse.send" in prev_line:
            print(f"Found potential issue at line {i+1}: {line}")
            print(f"Previous line: {prev_line}")
            print(f"Next line: {next_line}")

# Create a completely new fixed version of the template
with open('iac/streaming_media/template_fixed.yaml', 'w') as file:
    file.write("""---
AWSTemplateFormatVersion: '2010-09-09'
Description: Media Services for Live Streaming and VOD

Parameters:
  StaticWebsiteStackName:
    Type: String
    Description: Name of the static website stack to integrate with
    
  LiveInputType:
    Type: String
    Default: RTMP_PUSH
    AllowedValues:
      - RTMP_PUSH
      - RTP_PUSH
      - URL_PULL
    Description: Type of input for live streaming
  
  LiveInputWhitelistCidr:
    Type: String
    Default: 0.0.0.0/0
    Description: CIDR block to whitelist for live streaming input
    
  OrganizationTag:
    Type: String
    Description: Organization tag for resources
    Default: "flatstone services"
    
  BusinessUnitTag:
    Type: String
    Description: Business unit tag for resources
    Default: "marketing"
    
  EnvironmentTag:
    Type: String
    Description: Environment tag for resources
    Default: "dev"
    
Resources:
  # MediaLive Channel for live streaming
  MediaLiveChannel:
    Type: AWS::MediaLive::Channel
    Properties:
      ChannelClass: SINGLE_PIPELINE
      Name: !Sub "${AWS::StackName}-channel"
      InputAttachments:
        - InputId: !Ref MediaLiveInput
          InputAttachmentName: LiveInput
      Destinations:
        - Id: "MediaPackageDestination"
          MediaPackageSettings:
            - ChannelId: !Ref MediaPackageChannel
      EncoderSettings:
        AudioDescriptions:
          - AudioSelectorName: "Default"
            Name: "audio_1"
            CodecSettings:
              AacSettings:
                Profile: LC
                RateControlMode: CBR
                Bitrate: 192000
        VideoDescriptions:
          - Name: "video_1"
            RespondToAfd: "NONE"
            ScalingBehavior: "DEFAULT"
            Width: 1920
            Height: 1080
            CodecSettings:
              H264Settings:
                Profile: MAIN
                RateControlMode: CBR
                Bitrate: 5000000
                FramerateControl: "SPECIFIED"
                FramerateNumerator: 30
                FramerateDenominator: 1
                ParControl: "SPECIFIED"
                ParNumerator: 1
                ParDenominator: 1
        TimecodeConfig:
          Source: "EMBEDDED"
        OutputGroups:
          - Name: "MediaPackage_Group"
            OutputGroupSettings:
              MediaPackageGroupSettings:
                Destination:
                  DestinationRefId: "MediaPackageDestination"
            Outputs:
              - AudioDescriptionNames:
                  - "audio_1"
                VideoDescriptionName: "video_1"
                OutputName: "MediaPackage_Output"
                OutputSettings:
                  MediaPackageOutputSettings: {}
                
  # MediaLive Input for receiving live streams
  MediaLiveInput:
    Type: AWS::MediaLive::Input
    Properties:
      Type: !Ref LiveInputType
      InputSecurityGroups:
        - !Ref MediaLiveInputSecurityGroup
      Destinations:
        - StreamName: !Sub "${AWS::StackName}/live"
        
  # Security group for MediaLive Input
  MediaLiveInputSecurityGroup:
    Type: AWS::MediaLive::InputSecurityGroup
    Properties:
      WhitelistRules:
        - Cidr: !Ref LiveInputWhitelistCidr
          
  # MediaPackage Channel for packaging live content
  MediaPackageChannel:
    Type: AWS::MediaPackage::Channel
    Properties:
      Id: !Sub "${AWS::StackName}-channel"
      Description: Channel for live streaming
      
  # MediaPackage Origin Endpoint for HLS
  MediaPackageHlsEndpoint:
    Type: AWS::MediaPackage::OriginEndpoint
    Properties:
      ChannelId: !Ref MediaPackageChannel
      Id: !Sub "${AWS::StackName}-hls-endpoint"
      HlsPackage:
        SegmentDurationSeconds: 6
        PlaylistWindowSeconds: 60

  # MediaPackage Origin Endpoint for DASH
  MediaPackageDashEndpoint:
    Type: AWS::MediaPackage::OriginEndpoint
    Properties:
      ChannelId: !Ref MediaPackageChannel
      Id: !Sub "${AWS::StackName}-dash-endpoint"
      DashPackage:
        SegmentDurationSeconds: 6
        ManifestWindowSeconds: 60

  # S3 Bucket for VOD content
  VodContentBucket:
    Type: AWS::S3::Bucket
    Properties:
      VersioningConfiguration:
        Status: Enabled
      CorsConfiguration:
        CorsRules:
          - AllowedHeaders: ['*']
            AllowedMethods: [GET, PUT, POST, DELETE, HEAD]
            AllowedOrigins: ['*']
            MaxAge: 3600
            
  # CloudFront Origin Access Identity for VOD bucket
  VodOriginAccessIdentity:
    Type: AWS::CloudFront::CloudFrontOriginAccessIdentity
    Properties:
      CloudFrontOriginAccessIdentityConfig:
        Comment: !Sub "OAI for ${AWS::StackName} VOD content"
        
  # Get existing CloudFront Distribution from static website stack
  CloudFrontDistributionUpdate:
    Type: AWS::CloudFormation::CustomResource
    Properties:
      ServiceToken: !GetAtt UpdateCloudFrontFunction.Arn
      DistributionId: 
        Fn::ImportValue: !Sub "${StaticWebsiteStackName}-CloudFrontDistributionId"
      MediaPackageChannelDomain: !Join ["", [!Ref MediaPackageChannel, ".mediapackage.", !Ref "AWS::Region", ".amazonaws.com"]]
      HlsEndpointPath: !Sub "/out/v1/${AWS::StackName}-hls-endpoint"
      DashEndpointPath: !Sub "/out/v1/${AWS::StackName}-dash-endpoint"
      VodBucketDomain: !Sub "${VodContentBucket}.s3.amazonaws.com"
      VodOriginAccessIdentity: !Sub "origin-access-identity/cloudfront/${VodOriginAccessIdentity}"
      
  # Lambda function to update CloudFront distribution
  UpdateCloudFrontFunction:
    Type: AWS::Lambda::Function
    Properties:
      Handler: index.handler
      Role: !GetAtt UpdateCloudFrontRole.Arn
      Runtime: python3.8
      Timeout: 600
      MemorySize: 256
      Environment:
        Variables:
          DEBUG_MODE: "true"
      Code:
        ZipFile: |
          import boto3
          import cfnresponse
          import json
          import time
          import traceback
          
          def handler(event, context):
            print(f"Event received: {json.dumps(event)}")
            
            # Always ensure we send a response, even if there's an unexpected error
            try:
                if event['RequestType'] == 'Delete':
                  print("Delete request - nothing to do")
                  cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
                  return
                  
                # Validate input parameters
                required_params = [
                    'DistributionId', 
                    'MediaPackageChannelDomain', 
                    'HlsEndpointPath', 
                    'DashEndpointPath', 
                    'VodBucketDomain', 
                    'VodOriginAccessIdentity'
                ]
                
                for param in required_params:
                    if param not in event['ResourceProperties']:
                        error_msg = f"Missing required parameter: {param}"
                        print(error_msg)
                        cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': error_msg})
                        return
                
                # Get parameters
                distribution_id = event['ResourceProperties']['DistributionId']
                media_package_domain = event['ResourceProperties']['MediaPackageChannelDomain']
                hls_endpoint_path = event['ResourceProperties']['HlsEndpointPath']
                dash_endpoint_path = event['ResourceProperties']['DashEndpointPath']
                vod_bucket_domain = event['ResourceProperties']['VodBucketDomain']
                vod_oai = event['ResourceProperties']['VodOriginAccessIdentity']
                
                print(f"Parameters validated. Distribution ID: {distribution_id}")
                print(f"MediaPackage Domain: {media_package_domain}")
                print(f"HLS Path: {hls_endpoint_path}")
                print(f"DASH Path: {dash_endpoint_path}")
                
                # Initialize CloudFront client
                cf = boto3.client('cloudfront')
                
                # Get the current distribution configuration
                try:
                    print("Getting distribution configuration")
                    response = cf.get_distribution_config(Id=distribution_id)
                    etag = response['ETag']
                    config = response['DistributionConfig']
                    print(f"Got distribution config with ETag: {etag}")
                    print(f"Distribution config: {json.dumps(config, default=str)}")
                except Exception as e:
                    error_msg = f"Error getting distribution config: {str(e)}"
                    print(error_msg)
                    print(f"Traceback: {traceback.format_exc()}")
                    cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': error_msg})
                    return
                
                # Ensure Origins structure exists
                try:
                    if 'Origins' not in config:
                        print("Origins key not found in config, creating it")
                        config['Origins'] = {'Quantity': 0, 'Items': []}
                    elif 'Items' not in config['Origins']:
                        print("Items key not found in Origins, creating it")
                        config['Origins']['Items'] = []
                    
                    origins = config['Origins']['Items']
                    print(f"Current origins: {json.dumps(origins, default=str)}")
                except Exception as e:
                    error_msg = f"Error setting up Origins structure: {str(e)}"
                    print(error_msg)
                    print(f"Traceback: {traceback.format_exc()}")
                    cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': error_msg})
                    return
                
                # Create origin configurations
                try:
                    # Add HLS origin
                    hls_origin = {
                        'Id': 'HLSOrigin',
                        'DomainName': media_package_domain,
                        'OriginPath': hls_endpoint_path,
                        'CustomHeaders': {'Quantity': 0},
                        'CustomOriginConfig': {
                            'HTTPPort': 80,
                            'HTTPSPort': 443,
                            'OriginProtocolPolicy': 'https-only',
                            'OriginSslProtocols': {
                                'Quantity': 1,
                                'Items': ['TLSv1.2']
                            },
                            'OriginReadTimeout': 30,
                            'OriginKeepaliveTimeout': 5
                        }
                    }
                    
                    # Add DASH origin
                    dash_origin = {
                        'Id': 'DASHOrigin',
                        'DomainName': media_package_domain,
                        'OriginPath': dash_endpoint_path,
                        'CustomHeaders': {'Quantity': 0},
                        'CustomOriginConfig': {
                            'HTTPPort': 80,
                            'HTTPSPort': 443,
                            'OriginProtocolPolicy': 'https-only',
                            'OriginSslProtocols': {
                                'Quantity': 1,
                                'Items': ['TLSv1.2']
                            },
                            'OriginReadTimeout': 30,
                            'OriginKeepaliveTimeout': 5
                        }
                    }
                    
                    # Add VOD origin
                    vod_origin = {
                        'Id': 'VODOrigin',
                        'DomainName': vod_bucket_domain,
                        'OriginPath': '',
                        'CustomHeaders': {'Quantity': 0},
                        'S3OriginConfig': {
                            'OriginAccessIdentity': vod_oai
                        }
                    }
                    
                    print("Origin configurations created successfully")
                except Exception as e:
                    error_msg = f"Error creating origin configurations: {str(e)}"
                    print(error_msg)
                    print(f"Traceback: {traceback.format_exc()}")
                    cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': error_msg})
                    return
                
                # Update origins
                try:
                    # Check if origins already exist
                    origin_ids = []
                    if origins:
                        origin_ids = [origin.get('Id', '') for origin in origins]
                    
                    print(f"Existing origin IDs: {origin_ids}")
                    
                    # Add origins if they don't exist
                    if 'HLSOrigin' not in origin_ids:
                        print("Adding HLS origin")
                        origins.append(hls_origin)
                    else:
                        print("HLS origin already exists")
                    
                    if 'DASHOrigin' not in origin_ids:
                        print("Adding DASH origin")
                        origins.append(dash_origin)
                    else:
                        print("DASH origin already exists")
                    
                    if 'VODOrigin' not in origin_ids:
                        print("Adding VOD origin")
                        origins.append(vod_origin)
                    else:
                        print("VOD origin already exists")
                    
                    config['Origins']['Quantity'] = len(origins)
                    config['Origins']['Items'] = origins
                    print(f"Updated origins count: {config['Origins']['Quantity']}")
                except Exception as e:
                    error_msg = f"Error updating origins: {str(e)}"
                    print(error_msg)
                    print(f"Traceback: {traceback.format_exc()}")
                    cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': error_msg})
                    return
                
                # Update cache behaviors
                try:
                    # Ensure CacheBehaviors structure exists
                    if 'CacheBehaviors' not in config:
                        print("CacheBehaviors key not found in config, creating it")
                        config['CacheBehaviors'] = {'Quantity': 0, 'Items': []}
                    elif 'Items' not in config['CacheBehaviors']:
                        print("Items key not found in CacheBehaviors, creating it")
                        config['CacheBehaviors']['Items'] = []
                    
                    cache_behaviors = config['CacheBehaviors']['Items']
                    print(f"Current cache behaviors: {json.dumps(cache_behaviors, default=str)}")
                    
                    # Add HLS cache behavior
                    hls_behavior = {
                        'PathPattern': '/live/*',
                        'TargetOriginId': 'HLSOrigin',
                        'ViewerProtocolPolicy': 'redirect-to-https',
                        'AllowedMethods': {
                            'Quantity': 3,
                            'Items': ['GET', 'HEAD', 'OPTIONS'],
                            'CachedMethods': {
                                'Quantity': 2,
                                'Items': ['GET', 'HEAD']
                            }
                        },
                        'ForwardedValues': {
                            'QueryString': True,
                            'Cookies': {'Forward': 'none'},
                            'Headers': {'Quantity': 0, 'Items': []},
                            'QueryStringCacheKeys': {'Quantity': 0, 'Items': []}
                        },
                        'MinTTL': 0,
                        'DefaultTTL': 86400,
                        'MaxTTL': 31536000,
                        'Compress': True,
                        'SmoothStreaming': False,
                        'FieldLevelEncryptionId': ''
                    }
                    
                    # Add VOD cache behavior
                    vod_behavior = {
                        'PathPattern': '/vod/*',
                        'TargetOriginId': 'VODOrigin',
                        'ViewerProtocolPolicy': 'redirect-to-https',
                        'AllowedMethods': {
                            'Quantity': 3,
                            'Items': ['GET', 'HEAD', 'OPTIONS'],
                            'CachedMethods': {
                                'Quantity': 2,
                                'Items': ['GET', 'HEAD']
                            }
                        },
                        'ForwardedValues': {
                            'QueryString': True,
                            'Cookies': {'Forward': 'none'},
                            'Headers': {'Quantity': 0, 'Items': []},
                            'QueryStringCacheKeys': {'Quantity': 0, 'Items': []}
                        },
                        'MinTTL': 0,
                        'DefaultTTL': 86400,
                        'MaxTTL': 31536000,
                        'Compress': True,
                        'SmoothStreaming': False,
                        'FieldLevelEncryptionId': ''
                    }
                    
                    # Check if cache behaviors already exist
                    path_patterns = []
                    if cache_behaviors:
                        path_patterns = [behavior.get('PathPattern', '') for behavior in cache_behaviors]
                    
                    print(f"Existing path patterns: {path_patterns}")
                    
                    # Add cache behaviors if they don't exist
                    if '/live/*' not in path_patterns:
                        print("Adding HLS cache behavior")
                        cache_behaviors.append(hls_behavior)
                    else:
                        print("HLS cache behavior already exists")
                    
                    if '/vod/*' not in path_patterns:
                        print("Adding VOD cache behavior")
                        cache_behaviors.append(vod_behavior)
                    else:
                        print("VOD cache behavior already exists")
                    
                    config['CacheBehaviors']['Quantity'] = len(cache_behaviors)
                    config['CacheBehaviors']['Items'] = cache_behaviors
                    print(f"Updated cache behaviors count: {config['CacheBehaviors']['Quantity']}")
                except Exception as e:
                    error_msg = f"Error updating cache behaviors: {str(e)}"
                    print(error_msg)
                    print(f"Traceback: {traceback.format_exc()}")
                    cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': error_msg})
                    return
                
                # Update the distribution
                try:
                    print("Updating distribution with new configuration")
                    print(f"Final config: {json.dumps(config, default=str)}")
                    
                    response = cf.update_distribution(
                        Id=distribution_id,
                        IfMatch=etag,
                        DistributionConfig=config
                    )
                    print("Distribution update successful")
                    
                    # Return success
                    result = {
                        'DistributionId': distribution_id,
                        'DomainName': response['Distribution']['DomainName']
                    }
                    print(f"Sending success response: {json.dumps(result)}")
                    cfnresponse.send(event, context, cfnresponse.SUCCESS, result)
                except Exception as e:
                    error_msg = f"Error updating distribution: {str(e)}"
                    print(error_msg)
                    print(f"Traceback: {traceback.format_exc()}")
                    cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': error_msg})
                    return
                    
            except Exception as e:
                # Catch-all for any unexpected errors
                error_msg = f"Unexpected error in Lambda function: {str(e)}"
                print(error_msg)
                print(f"Traceback: {traceback.format_exc()}")
                
                try:
                    cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': error_msg})
                except Exception as send_error:
                    print(f"Error sending response: {str(send_error)}")
                    print(f"Original error: {error_msg}")
      
  # IAM role for the Lambda function
  UpdateCloudFrontRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: CloudFrontAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - cloudfront:GetDistribution
                  - cloudfront:GetDistributionConfig
                  - cloudfront:UpdateDistribution
                  - cloudfront:ListDistributions
                  - cloudfront:ListTagsForResource
                Resource: '*'
        - PolicyName: S3Access
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - s3:GetObject
                  - s3:PutObject
                  - s3:ListBucket
                Resource: '*'

Outputs:
  MediaLiveInputUrl:
    Description: URL for pushing live streams to MediaLive
    Value: !Select [0, !GetAtt MediaLiveInput.Destinations]
    
  HlsEndpointUrl:
    Description: HLS endpoint URL for live streaming
    Value: !GetAtt MediaPackageHlsEndpoint.Url
    
  DashEndpointUrl:
    Description: DASH endpoint URL for live streaming
    Value: !GetAtt MediaPackageDashEndpoint.Url
    
  VodBucketName:
    Description: S3 bucket for VOD content
    Value: !Ref VodContentBucket
    
  CloudFrontDistributionId:
    Description: ID of the CloudFront distribution used for streaming media
    Value: 
      Fn::ImportValue: !Sub "${StaticWebsiteStackName}-CloudFrontDistributionId"
      
  CloudFrontDistributionDomainName:
    Description: Domain name of the CloudFront distribution used for streaming media
    Value:
      Fn::ImportValue: !Sub "${StaticWebsiteStackName}-CloudFrontDistributionDomainName"
""")

print("Fixed template written to iac/streaming_media/template_fixed.yaml")