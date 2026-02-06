# AWS Deployment Guide for MCP Sales Analytics Server

Complete guide to deploying the MCP Sales Analytics Server on AWS with multiple architecture options.

---

## Table of Contents

1. [Architecture Options](#architecture-options)
2. [Option 1: AWS Lambda + API Gateway (SSE)](#option-1-aws-lambda--api-gateway-sse)
3. [Option 2: AWS EC2 with SSH Tunnel](#option-2-aws-ec2-with-ssh-tunnel)
4. [Option 3: ECS Fargate with SSE](#option-3-ecs-fargate-with-sse)
5. [Cost Comparison](#cost-comparison)
6. [Security Best Practices](#security-best-practices)

---

## Architecture Options

### Overview Comparison

| Option | Complexity | Cost | Scalability | Best For |
|--------|-----------|------|-------------|----------|
| **Lambda + API Gateway** | Medium | Low | Auto | Serverless, sporadic usage |
| **EC2 + SSH** | Low | Medium | Manual | Simple, persistent connection |
| **ECS Fargate** | High | Medium-High | Auto | Production, high availability |

---

## Option 1: AWS Lambda + API Gateway (SSE)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT SIDE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │  Claude Desktop  │         │  Gemini Client   │             │
│  │  (Local)         │         │  (Local)         │             │
│  └────────┬─────────┘         └────────┬─────────┘             │
│           │                            │                        │
│           │ MCP over SSE               │ MCP over SSE          │
│           │ (HTTPS)                    │ (HTTPS)               │
│           │                            │                        │
└───────────┼────────────────────────────┼────────────────────────┘
            │                            │
            │                            │
            ▼                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                         AWS CLOUD                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              API Gateway (REST API)                       │  │
│  │  Endpoint: https://api-id.execute-api.region.amazonaws... │  │
│  │  Routes:                                                  │  │
│  │    POST /sse  → Lambda Function                          │  │
│  └────────────────────────┬─────────────────────────────────┘  │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           AWS Lambda Function                             │  │
│  │  Runtime: Python 3.11                                     │  │
│  │  Memory: 512 MB                                           │  │
│  │  Timeout: 30s                                             │  │
│  │                                                           │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  MCP Server (mcp_server.py)                        │  │  │
│  │  │  - SSE Transport Layer                             │  │  │
│  │  │  - Tool: top_n_products                            │  │  │
│  │  │  - Tool: forecast_sales                            │  │  │
│  │  └────────────────┬───────────────────────────────────┘  │  │
│  └───────────────────┼──────────────────────────────────────┘  │
│                      │                                          │
│                      ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Amazon S3 Bucket                             │  │
│  │  - sample_sales_data.csv                                  │  │
│  │  - Versioned data files                                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              CloudWatch Logs                              │  │
│  │  - Lambda execution logs                                  │  │
│  │  - API Gateway access logs                                │  │
│  │  - MCP tool call metrics                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Steps

#### Step 1: Prepare Lambda Package

Create a new file `lambda_handler.py`:

```python
import json
import asyncio
from mcp.server.sse import sse_server
from mcp_server import app

async def handle_sse_request(event, context):
    """Handle SSE requests from API Gateway"""
    
    # Parse the incoming request
    body = json.loads(event.get('body', '{}'))
    
    # Create SSE server
    async with sse_server() as (read_stream, write_stream):
        # Run MCP server
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
    }

def lambda_handler(event, context):
    """AWS Lambda entry point"""
    return asyncio.run(handle_sse_request(event, context))
```

#### Step 2: Create Deployment Package

```bash
# Create deployment directory
mkdir lambda-deployment
cd lambda-deployment

# Copy your code
cp ../mcp_server.py .
cp ../lambda_handler.py .

# Install dependencies
pip install -t . mcp pandas prophet

# Download data file (or configure S3 access)
mkdir data
cp ../data/sample_sales_data.csv data/

# Create ZIP package
zip -r mcp-server-lambda.zip .
```

#### Step 3: Deploy to AWS Lambda

**Using AWS CLI**:

```bash
# Create IAM role for Lambda
aws iam create-role \
  --role-name mcp-lambda-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach basic execution policy
aws iam attach-role-policy \
  --role-name mcp-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Create Lambda function
aws lambda create-function \
  --function-name mcp-sales-analytics \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/mcp-lambda-role \
  --handler lambda_handler.lambda_handler \
  --zip-file fileb://mcp-server-lambda.zip \
  --timeout 30 \
  --memory-size 512
```

**Using AWS Console**:

1. Go to AWS Lambda Console
2. Click "Create function"
3. Choose "Author from scratch"
4. Function name: `mcp-sales-analytics`
5. Runtime: Python 3.11
6. Upload `mcp-server-lambda.zip`
7. Set handler: `lambda_handler.lambda_handler`
8. Configure:
   - Memory: 512 MB
   - Timeout: 30 seconds

#### Step 4: Create API Gateway

```bash
# Create REST API
aws apigateway create-rest-api \
  --name mcp-sales-analytics-api \
  --description "MCP Sales Analytics API"

# Get API ID (from output above)
API_ID="your-api-id"

# Get root resource ID
ROOT_ID=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --query 'items[0].id' \
  --output text)

# Create /sse resource
RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_ID \
  --path-part sse \
  --query 'id' \
  --output text)

# Create POST method
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method POST \
  --authorization-type NONE

# Integrate with Lambda
aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:REGION:ACCOUNT_ID:function:mcp-sales-analytics/invocations

# Deploy API
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name prod
```

#### Step 5: Configure Client

Update your client configuration to use the API Gateway endpoint:

**For Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "sales-analytics": {
      "url": "https://YOUR_API_ID.execute-api.REGION.amazonaws.com/prod/sse",
      "transport": "sse"
    }
  }
}
```

**For Gemini Client** (create `gemini_client_sse.py`):

```python
from mcp.client.sse import sse_client

async def connect_to_remote_server():
    """Connect to remote MCP server via SSE"""
    
    server_url = "https://YOUR_API_ID.execute-api.REGION.amazonaws.com/prod/sse"
    
    async with sse_client(server_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Use session to call tools
            result = await session.call_tool(
                "top_n_products",
                {"n": 5, "operation": "Dallas"}
            )
            print(result)
```

### Advantages

✅ **Serverless** - No server management  
✅ **Auto-scaling** - Handles traffic spikes  
✅ **Pay-per-use** - Only charged for actual usage  
✅ **Low latency** - Fast cold starts with Python 3.11  

### Disadvantages

❌ **Cold starts** - First request may be slow  
❌ **Timeout limits** - 30s max execution time  
❌ **Package size** - Prophet is large (~200MB)  

---

## Option 2: AWS EC2 with SSH Tunnel

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT SIDE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │  Claude Desktop  │         │  Gemini Client   │             │
│  │  (Local)         │         │  (Local)         │             │
│  └────────┬─────────┘         └────────┬─────────┘             │
│           │                            │                        │
│           │ SSH Tunnel                 │ SSH Tunnel            │
│           │ (Port 22)                  │ (Port 22)             │
│           │                            │                        │
└───────────┼────────────────────────────┼────────────────────────┘
            │                            │
            │                            │
            ▼                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                         AWS CLOUD                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              EC2 Instance (t3.small)                      │  │
│  │  OS: Ubuntu 22.04 LTS                                     │  │
│  │  Public IP: 54.xxx.xxx.xxx                                │  │
│  │                                                           │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  SSH Server (Port 22)                              │  │  │
│  │  │  - Key-based authentication                        │  │  │
│  │  │  - Security group: Allow SSH from your IP          │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  Python Environment                                │  │  │
│  │  │  - Python 3.11                                     │  │  │
│  │  │  - uv package manager                              │  │  │
│  │  │  - MCP server dependencies                         │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  MCP Server (mcp_server.py)                        │  │  │
│  │  │  - Runs on demand via SSH                          │  │  │
│  │  │  - stdio transport                                 │  │  │
│  │  │  - Data: /home/ubuntu/mcp-server/data/             │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Security Group                               │  │
│  │  Inbound Rules:                                           │  │
│  │    - SSH (22) from YOUR_IP/32                             │  │
│  │  Outbound Rules:                                          │  │
│  │    - All traffic                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Steps

#### Step 1: Launch EC2 Instance

**Using AWS Console**:

1. Go to EC2 Dashboard
2. Click "Launch Instance"
3. Configure:
   - **Name**: mcp-sales-analytics-server
   - **AMI**: Ubuntu Server 22.04 LTS
   - **Instance type**: t3.small (2 vCPU, 2 GB RAM)
   - **Key pair**: Create new or use existing
   - **Network**: Default VPC
   - **Security group**: Create new
     - Allow SSH (port 22) from your IP
4. Launch instance

**Using AWS CLI**:

```bash
# Create security group
aws ec2 create-security-group \
  --group-name mcp-server-sg \
  --description "Security group for MCP server"

# Get your public IP
MY_IP=$(curl -s ifconfig.me)

# Allow SSH from your IP
aws ec2 authorize-security-group-ingress \
  --group-name mcp-server-sg \
  --protocol tcp \
  --port 22 \
  --cidr $MY_IP/32

# Launch instance
aws ec2 run-instances \
  --image-id ami-0c7217cdde317cfec \
  --instance-type t3.small \
  --key-name YOUR_KEY_PAIR \
  --security-groups mcp-server-sg \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=mcp-sales-analytics}]'
```

#### Step 2: Setup Server

SSH into your instance:

```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

Install dependencies:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Create project directory
mkdir -p ~/mcp-server/data
cd ~/mcp-server

# Clone or upload your code
# Option 1: Git
git clone YOUR_REPO_URL .

# Option 2: SCP from local
# (Run from your local machine)
# scp -i your-key.pem -r /path/to/MCP-Exploration/* ubuntu@YOUR_EC2_IP:~/mcp-server/

# Install dependencies
uv venv
source .venv/bin/activate
uv pip install mcp pandas prophet

# Upload data file
# scp -i your-key.pem data/sample_sales_data.csv ubuntu@YOUR_EC2_IP:~/mcp-server/data/
```

#### Step 3: Configure Client

**For Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "sales-analytics": {
      "command": "ssh",
      "args": [
        "-i", "/path/to/your-key.pem",
        "ubuntu@YOUR_EC2_PUBLIC_IP",
        "cd ~/mcp-server && source .venv/bin/activate && python mcp_server.py"
      ]
    }
  }
}
```

**For Gemini Client**, create `gemini_client_ssh.py`:

```python
import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

async def connect_via_ssh():
    """Connect to remote MCP server via SSH"""
    
    server_params = StdioServerParameters(
        command="ssh",
        args=[
            "-i", "/path/to/your-key.pem",
            "ubuntu@YOUR_EC2_PUBLIC_IP",
            "cd ~/mcp-server && source .venv/bin/activate && python mcp_server.py"
        ]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Use session
            result = await session.call_tool(
                "top_n_products",
                {"n": 5, "operation": "Dallas"}
            )
            print(result)

asyncio.run(connect_via_ssh())
```

### Advantages

✅ **Simple setup** - Minimal code changes  
✅ **Full control** - Complete server access  
✅ **No timeouts** - Long-running operations OK  
✅ **Easy debugging** - Direct SSH access  

### Disadvantages

❌ **Manual scaling** - Need to manage capacity  
❌ **Always running** - Pay for idle time  
❌ **Security** - Need to manage SSH keys  
❌ **Maintenance** - OS updates, patches  

---

## Option 3: ECS Fargate with SSE

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT SIDE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │  Claude Desktop  │         │  Gemini Client   │             │
│  │  (Local)         │         │  (Local)         │             │
│  └────────┬─────────┘         └────────┬─────────┘             │
│           │                            │                        │
│           │ HTTPS (MCP/SSE)            │ HTTPS (MCP/SSE)       │
│           │                            │                        │
└───────────┼────────────────────────────┼────────────────────────┘
            │                            │
            ▼                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                         AWS CLOUD                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │     Application Load Balancer (ALB)                       │  │
│  │  DNS: mcp-server.your-domain.com                          │  │
│  │  Port: 443 (HTTPS)                                        │  │
│  │  SSL Certificate: AWS Certificate Manager                 │  │
│  └────────────────────────┬─────────────────────────────────┘  │
│                           │                                     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              ECS Cluster                                  │  │
│  │                                                           │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  ECS Service (Fargate)                             │  │  │
│  │  │  Desired count: 2                                  │  │  │
│  │  │  Auto-scaling: 2-10 tasks                          │  │  │
│  │  │                                                    │  │  │
│  │  │  ┌──────────────────┐  ┌──────────────────┐      │  │  │
│  │  │  │  Task 1          │  │  Task 2          │      │  │  │
│  │  │  │  (Container)     │  │  (Container)     │      │  │  │
│  │  │  │                  │  │                  │      │  │  │
│  │  │  │  ┌────────────┐  │  │  ┌────────────┐  │      │  │  │
│  │  │  │  │ FastAPI    │  │  │  │ FastAPI    │  │      │  │  │
│  │  │  │  │ + MCP SSE  │  │  │  │ + MCP SSE  │  │      │  │  │
│  │  │  │  └────────────┘  │  │  └────────────┘  │      │  │  │
│  │  │  │                  │  │                  │      │  │  │
│  │  │  │  Port: 8000      │  │  Port: 8000      │      │  │  │
│  │  │  └──────────────────┘  └──────────────────┘      │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Amazon ECR (Container Registry)              │  │
│  │  Image: mcp-sales-analytics:latest                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Amazon S3                                    │  │
│  │  - sample_sales_data.csv                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              CloudWatch                                   │  │
│  │  - Container logs                                         │  │
│  │  - Metrics & alarms                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Steps

#### Step 1: Create FastAPI Wrapper

Create `app.py`:

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from mcp.server.sse import sse_server
from mcp_server import app as mcp_app
import asyncio

app = FastAPI(title="MCP Sales Analytics Server")

@app.get("/health")
async def health_check():
    """Health check endpoint for ALB"""
    return {"status": "healthy"}

@app.post("/sse")
async def sse_endpoint():
    """SSE endpoint for MCP communication"""
    
    async def event_generator():
        async with sse_server() as (read_stream, write_stream):
            await mcp_app.run(
                read_stream,
                write_stream,
                mcp_app.create_initialization_options()
            )
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### Step 2: Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml .
COPY mcp_server.py .
COPY app.py .
COPY data/ ./data/

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    mcp \
    pandas \
    prophet

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Step 3: Build and Push to ECR

```bash
# Create ECR repository
aws ecr create-repository --repository-name mcp-sales-analytics

# Get login credentials
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t mcp-sales-analytics .

# Tag image
docker tag mcp-sales-analytics:latest \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/mcp-sales-analytics:latest

# Push to ECR
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/mcp-sales-analytics:latest
```

#### Step 4: Create ECS Cluster and Service

```bash
# Create cluster
aws ecs create-cluster --cluster-name mcp-cluster

# Create task definition (save as task-definition.json)
```

```json
{
  "family": "mcp-sales-analytics",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "mcp-server",
      "image": "YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/mcp-sales-analytics:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/mcp-sales-analytics",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create service
aws ecs create-service \
  --cluster mcp-cluster \
  --service-name mcp-service \
  --task-definition mcp-sales-analytics \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

#### Step 5: Setup Load Balancer

1. Create Application Load Balancer
2. Create target group (port 8000)
3. Register ECS tasks with target group
4. Configure health checks (`/health`)
5. Add HTTPS listener with SSL certificate

### Advantages

✅ **Production-ready** - High availability  
✅ **Auto-scaling** - Handles traffic automatically  
✅ **Container-based** - Easy deployments  
✅ **Load balanced** - Distributed traffic  

### Disadvantages

❌ **Complex setup** - More moving parts  
❌ **Higher cost** - Always-on containers  
❌ **Learning curve** - Docker + ECS knowledge needed  

---

## Cost Comparison

### Monthly Cost Estimates (US East 1)

| Option | Light Usage | Medium Usage | Heavy Usage |
|--------|-------------|--------------|-------------|
| **Lambda + API Gateway** | $5-10 | $20-50 | $100-200 |
| **EC2 (t3.small)** | $15-20 | $15-20 | $15-20 |
| **ECS Fargate (2 tasks)** | $30-40 | $30-40 | $30-40 |

**Assumptions**:
- Light: 1,000 requests/month
- Medium: 10,000 requests/month
- Heavy: 100,000 requests/month

### Cost Breakdown

**Lambda + API Gateway**:
- Lambda: $0.20 per 1M requests + $0.0000166667 per GB-second
- API Gateway: $3.50 per million requests
- S3: $0.023 per GB storage

**EC2**:
- t3.small: $0.0208/hour = ~$15/month
- EBS: $0.10 per GB-month
- Data transfer: $0.09 per GB

**ECS Fargate**:
- vCPU: $0.04048 per vCPU-hour
- Memory: $0.004445 per GB-hour
- 2 tasks (0.5 vCPU, 1GB each) = ~$30/month

---

## Security Best Practices

### 1. Authentication & Authorization

**API Key Authentication**:

```python
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

@app.post("/sse", dependencies=[Depends(verify_api_key)])
async def sse_endpoint():
    # ... endpoint code
```

**Client Configuration**:

```json
{
  "mcpServers": {
    "sales-analytics": {
      "url": "https://api.example.com/sse",
      "transport": "sse",
      "headers": {
        "X-API-Key": "your-secret-key"
      }
    }
  }
}
```

### 2. Network Security

**Security Group Rules**:

```bash
# Lambda/Fargate: No inbound rules needed (behind ALB)
# ALB: Allow HTTPS (443) from anywhere
# EC2: Allow SSH (22) from your IP only

aws ec2 authorize-security-group-ingress \
  --group-id sg-xxx \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0
```

### 3. Data Encryption

**In Transit**:
- Use HTTPS/TLS for all connections
- AWS Certificate Manager for SSL certificates

**At Rest**:
- Enable S3 encryption for data files
- Use encrypted EBS volumes for EC2

### 4. Secrets Management

**AWS Secrets Manager**:

```python
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Use in your code
api_key = get_secret('mcp-api-key')['key']
```

### 5. Monitoring & Logging

**CloudWatch Alarms**:

```bash
# High error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name mcp-high-errors \
  --alarm-description "Alert on high error rate" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

**Log Analysis**:

```python
# Add structured logging
import logging
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def log_tool_call(tool_name, args, result):
    logger.info(json.dumps({
        'event': 'tool_call',
        'tool': tool_name,
        'args': args,
        'success': 'error' not in result
    }))
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Test locally with all clients
- [ ] Review and optimize data files
- [ ] Set up AWS account and credentials
- [ ] Choose deployment option
- [ ] Estimate costs

### Deployment

- [ ] Create IAM roles and policies
- [ ] Deploy infrastructure (Lambda/EC2/ECS)
- [ ] Upload data to S3 or instance
- [ ] Configure networking and security groups
- [ ] Set up monitoring and alarms
- [ ] Test endpoints

### Post-Deployment

- [ ] Update client configurations
- [ ] Test end-to-end functionality
- [ ] Monitor logs and metrics
- [ ] Set up backup strategy
- [ ] Document deployment process

---

## Troubleshooting

### Common Issues

**Issue**: Lambda timeout
- **Solution**: Increase timeout to 30s, optimize Prophet model

**Issue**: Cold start latency
- **Solution**: Use provisioned concurrency or keep EC2/Fargate warm

**Issue**: SSH connection refused
- **Solution**: Check security group, verify instance is running

**Issue**: SSE connection drops
- **Solution**: Implement reconnection logic, check ALB timeout settings

**Issue**: High costs
- **Solution**: Review CloudWatch metrics, optimize resource allocation

---

## Next Steps

1. **Choose your deployment option** based on requirements
2. **Follow the implementation steps** for your chosen option
3. **Test thoroughly** before production use
4. **Set up monitoring** to track performance and costs
5. **Document your setup** for team members

---

## Additional Resources

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

**Questions or Issues?** Refer to the troubleshooting section or AWS support.
