provider "aws"{
 region = "us-east-1"
}

data "aws_ami" "this" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "architecture"
    values = ["arm64"]
  }
  filter {
    name   = "name"
    #values = ["al2023-ami-*-arm64"] # For Amazon Linux 2023
    # Or use ["amzn2-ami-hvm-*-arm64-gp2"] for Amazon Linux 2
    values = ["amzn2-ami-hvm-*-arm64-gp2"]
  }
}

resource "aws_instance" "this" {
  ami = data.aws_ami.this.id
  instance_market_options {
    market_type = "spot"
    spot_options {
      max_price = 0.0031
    }
  }
  instance_type = "t4g.nano"
  tags = {
    Name = "test-spot"
  }
}