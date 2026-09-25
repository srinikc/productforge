# Cloud Engineering Standards

> AWS cloud architecture, services, and best practices for MyWorld Central Portal.

## Table of Contents

1. [AWS Account Structure](#aws-account-structure)
2. [Networking (VPC)](#networking-vpc)
3. [Compute (ECS Fargate)](#compute-ecs-fargate)
4. [Storage (S3)](#storage-s3)
5. [Database (RDS)](#database-rds)
6. [Caching (ElastiCache)](#caching-elasticache)
7. [Message Queue (SQS/SNS)](#message-queue-sqssns)
8. [CDN and DNS (CloudFront/Route 53)](#cdn-and-dns-cloudfrontroute-53)
9. [Load Balancing (ALB)](#load-balancing-alb)
10. [Auto Scaling](#auto-scaling)
11. [Monitoring and Logging](#monitoring-and-logging)
12. [Cost Optimization](#cost-optimization)
13. [Disaster Recovery](#disaster-recovery)

---

## AWS Account Structure

### Multi-Account Strategy

```
AWS Organizations
├── Production Account
│   ├── Runs live workloads
│   ├── Strict access controls
│   └── High audit logging
├── Staging Account
│   ├── Mirrors production
│   └── Used for pre-release testing
├── Development Account
│   ├── Shared dev environment
│   └── Looser controls
├── Shared Services Account
│   ├── ECR (container registry)
│   ├── Route 53 hosted zone
│   └── Certificate Manager
└── Security/Audit Account
    ├── CloudTrail logs
    ├── GuardDuty
    └── Security Hub
```

### Environment Isolation

```hcl
# terraform/environments/production/main.tf
provider "aws" {
  region = "us-east-1"
  assume_role {
    role_arn = "arn:aws:iam::PRODUCTION_ACCOUNT:role/TerraformExecutionRole"
  }
}
```

---

## Networking (VPC)

### VPC Design

```hcl
# modules/networking/main.tf
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.5.0"

  name = "myworld-${var.environment}"
  cidr = var.vpc_cidr  # e.g., "10.0.0.0/16"

  azs             = ["${var.region}a", "${var.region}b", "${var.region}c"]
  private_subnets = [
    "10.0.1.0/24",   # AZ-a
    "10.0.2.0/24",   # AZ-b
    "10.0.3.0/24",   # AZ-c
  ]
  public_subnets = [
    "10.0.101.0/24",  # AZ-a
    "10.0.102.0/24",  # AZ-b
    "10.0.103.0/24",  # AZ-c
  ]
  database_subnets = [
    "10.0.201.0/24",  # AZ-a
    "10.0.202.0/24",  # AZ-b
    "10.0.203.0/24",  # AZ-c
  ]

  enable_nat_gateway     = true
  single_nat_gateway     = var.environment != "production"
  one_nat_gateway_per_az = var.environment == "production"

  enable_vpn_gateway = false

  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_iam_role             = true

  tags = {
    Environment = var.environment
  }
}
```

### Security Groups

```hcl
# ALB Security Group
resource "aws_security_group" "alb" {
  name_prefix = "${var.environment}-alb-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Public HTTPS
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Redirect to HTTPS
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}


# API Security Group
resource "aws_security_group" "api" {
  name_prefix = "${var.environment}-api-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]  # Only from ALB
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}


# Database Security Group
resource "aws_security_group" "db" {
  name_prefix = "${var.environment}-db-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.api.id]  # Only from API
  }
}
```

---

## Compute (ECS Fargate)

### ECS Cluster

```hcl
# modules/compute/main.tf
resource "aws_ecs_cluster" "main" {
  name = "myworld-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 70
    base              = 1
  }

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 30
  }
}
```

### Task Definition

```json
# ecs/task-api.json
{
  "family": "myworld-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/myworld-api:1.0.0",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        },
        {
          "name": "LOG_LEVEL",
          "value": "INFO"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:myworld/production/database:url::"
        },
        {
          "name": "SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:myworld/production/jwt:secret::"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/myworld-api",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs",
          "awslogs-create-group": "true"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 30
      },
      "ulimits": [
        {
          "name": "nofile",
          "softLimit": 65536,
          "hardLimit": 65536
        }
      ]
    }
  ]
}
```

### ECS Service

```hcl
resource "aws_ecs_service" "api" {
  name            = "api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 3
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.api_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.api_target_group_arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100

  enable_execute_command = true  # For debugging

  tags = {
    Name = "myworld-api"
  }
}
```

---

## Storage (S3)

### Bucket Policy

```hcl
# modules/storage/main.tf
resource "aws_s3_bucket" "uploads" {
  bucket = "myworld-${var.environment}-uploads"

  tags = {
    Name        = "myworld-uploads"
    Environment = var.environment
  }
}

# Versioning
resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_id
    }
  }
}

# Public access block
resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle policy
resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    id     = "transition-old-to-ia"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 365
      storage_class = "GLACIER"
    }
  }

  rule {
    id     = "delete-incomplete-multipart"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# CORS
resource "aws_s3_bucket_cors_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST"]
    allowed_origins = var.allowed_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}
```

### S3 Upload (Presigned URL)

```python
import boto3
from datetime import timedelta


s3_client = boto3.client("s3", region_name="us-east-1")


def generate_presigned_upload_url(
    bucket: str, key: str, content_type: str, expires_in: int = 3600
) -> str:
    """Generate a presigned URL for direct browser upload."""
    return s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )


def generate_presigned_download_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for temporary download access."""
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )
```

---

## Database (RDS)

### RDS Instance

```hcl
# Already covered in infrastructure/docker.md, but key production settings:

resource "aws_db_instance" "main" {
  identifier     = "myworld-${var.environment}"
  engine         = "postgres"
  engine_version = "16.4"
  instance_class = "db.r6g.large"

  allocated_storage     = 100
  max_allocated_storage = 1000
  storage_type          = "gp3"
  storage_encrypted     = true
  iops                  = 3000

  multi_az               = var.environment == "production"
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.db_security_group_id]

  backup_retention_period = 30
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:00:00-Mon:03:00"
  copy_tags_to_snapshot   = true

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn

  performance_insights_enabled          = true
  performance_insights_kms_key_id       = var.kms_key_id
  performance_insights_retention_period = 7

  deletion_protection = true
  skip_final_snapshot = false

  auto_minor_version_upgrade = true
  apply_immediately          = false  # Maintenance window

  tags = {
    Environment = var.environment
  }
}


# Read replica
resource "aws_db_instance" "read_replica" {
  count                  = var.environment == "production" ? 2 : 0
  identifier             = "myworld-${var.environment}-replica-${count.index}"
  replicate_source_db    = aws_db_instance.main.identifier
  instance_class         = "db.r6g.large"
  storage_encrypted      = true
  monitoring_interval    = 60
  monitoring_role_arn    = aws_iam_role.rds_monitoring.arn

  tags = {
    Environment = var.environment
  }
}
```

---

## Caching (ElastiCache)

### Redis Cluster

```hcl
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "myworld-${var.environment}"
  replication_group_description = "Redis cluster for MyWorld"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = "cache.r6g.large"
  number_cache_clusters      = var.environment == "production" ? 3 : 1

  port                       = 6379
  parameter_group_name       = "default.redis7"
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [var.redis_security_group_id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.redis_auth_token

  automatic_failover_enabled = var.environment == "production"
  multi_az_enabled           = var.environment == "production"

  snapshot_retention_limit = 5
  snapshot_window          = "03:00-05:00"

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_slow.name
    destination_type = "cloudwatch-logs"
    log_format       = "text"
    log_type         = "slow-log"
  }

  tags = {
    Environment = var.environment
  }
}
```

---

## Message Queue (SQS/SNS)

### SQS Queue (Background Jobs)

```hcl
resource "aws_sqs_queue" "email_jobs" {
  name                       = "myworld-${var.environment}-email-jobs"
  delay_seconds              = 0
  max_message_size           = 262144  # 256 KB
  message_retention_seconds  = 345600  # 4 days
  receive_wait_time_seconds  = 20  # Long polling
  visibility_timeout_seconds = 60

  # Dead letter queue
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.email_jobs_dlq.arn
    maxReceiveCount     = 3
  })

  # Server-side encryption
  sqs_managed_sse_enabled = true

  tags = {
    Environment = var.environment
  }
}

resource "aws_sqs_queue" "email_jobs_dlq" {
  name                      = "myworld-${var.environment}-email-jobs-dlq"
  message_retention_seconds = 1209600  # 14 days
  sqs_managed_sse_enabled   = true
}


# IAM policy for ECS task to send/receive
resource "aws_iam_policy" "sqs_access" {
  name = "myworld-sqs-access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
        ]
        Resource = [
          aws_sqs_queue.email_jobs.arn,
          aws_sqs_queue.email_jobs_dlq.arn,
        ]
      }
    ]
  })
}
```

### SNS Topic (Notifications)

```hcl
resource "aws_sns_topic" "alerts" {
  name              = "myworld-${var.environment}-alerts"
  kms_master_key_id = var.kms_key_id
}

resource "aws_sns_topic_subscription" "email_alerts" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = "alerts@myworld.com"
}
```

### Application Code (Python)

```python
import boto3


sqs_client = boto3.client("sqs", region_name="us-east-1")
QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/ACCOUNT/myworld-production-email-jobs"


def send_email_job(to: str, subject: str, body: str) -> str:
    """Send email job to SQS queue."""
    response = sqs_client.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps({
            "to": to,
            "subject": subject,
            "body": body,
        }),
        MessageAttributes={
            "Priority": {
                "StringValue": "normal",
                "DataType": "String",
            }
        },
    )
    return response["MessageId"]


def process_email_jobs():
    """Worker: Process email jobs from SQS."""
    while True:
        response = sqs_client.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20,  # Long polling
            VisibilityTimeout=60,
        )

        for message in response.get("Messages", []):
            try:
                job = json.loads(message["Body"])
                send_smtp_email(job["to"], job["subject"], job["body"])

                # Delete message on success
                sqs_client.delete_message(
                    QueueUrl=QUEUE_URL,
                    ReceiptHandle=message["ReceiptHandle"],
                )
            except Exception as e:
                logger.error(f"Failed to process job: {e}")
                # Message will be retried (up to maxReceiveCount)
                # Then moved to DLQ
```

---

## CDN and DNS (CloudFront/Route 53)

### CloudFront Distribution

```hcl
resource "aws_cloudfront_distribution" "web" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"  # US, Canada, Europe
  aliases             = ["myworld.com", "www.myworld.com"]

  origin {
    domain_name = aws_lb.web.dns_name
    origin_id   = "ALB"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2", "TLSv1.3"]
    }
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "DELETE"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    target_origin_id       = "ALB"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = true
      headers      = ["Authorization", "CloudFront-Forwarded-Proto"]
      cookies {
        forward = "all"
      }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  # Static assets (long cache)
  ordered_cache_behavior {
    path_pattern     = "/_next/static/*"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "ALB"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 31536000  # 1 year
    default_ttl = 31536000
    max_ttl     = 31536000
    compress    = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = var.acm_certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  web_acl_id = var.waf_acl_arn  # WAF integration

  tags = {
    Environment = var.environment
  }
}
```

### Route 53

```hcl
# Hosted zone
data "aws_route53_zone" "main" {
  name = "myworld.com."
}


# ALIAS record for CloudFront
resource "aws_route53_record" "web" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "myworld.com"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.web.domain_name
    zone_id                = aws_cloudfront_distribution.web.hosted_zone_id
    evaluate_target_health = false
  }
}


# Health check
resource "aws_route53_health_check" "api" {
  fqdn              = "api.myworld.com"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30

  tags = {
    Name = "api-health-check"
  }
}
```

---

## Load Balancing (ALB)

### Application Load Balancer

```hcl
resource "aws_lb" "main" {
  name               = "myworld-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = var.environment == "production"
  drop_invalid_header_fields = true

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.id
    prefix  = "alb"
    enabled = true
  }

  tags = {
    Environment = var.environment
  }
}


# Target group
resource "aws_lb_target_group" "api" {
  name        = "myworld-${var.environment}-api"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
    matcher             = "200"
  }

  deregistration_delay = 30

  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400
    enabled         = true
  }
}


# HTTPS listener
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}


# HTTP → HTTPS redirect
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}
```

---

## Auto Scaling

### ECS Service Auto Scaling

```hcl
resource "aws_appautoscaling_target" "api" {
  max_capacity       = 20
  min_capacity       = 3
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}


# CPU-based scaling
resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "api-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}


# Memory-based scaling
resource "aws_appautoscaling_policy" "api_memory" {
  name               = "api-memory-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    target_value       = 80.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
```

### Scheduled Scaling

```hcl
# Scale up during business hours
resource "aws_appautoscaling_scheduled_action" "api_scale_up_morning" {
  name               = "api-scale-up-morning"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  schedule = "cron(0 8 * * MON-FRI)"  # 8 AM weekdays

  scalable_target_action {
    min_capacity = 5
    max_capacity = 30
  }
}


# Scale down at night
resource "aws_appautoscaling_scheduled_action" "api_scale_down_night" {
  name               = "api-scale-down-night"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  schedule = "cron(0 20 * * MON-FRI)"  # 8 PM weekdays

  scalable_target_action {
    min_capacity = 2
    max_capacity = 10
  }
}
```

---

## Monitoring and Logging

### CloudWatch Dashboard

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/ECS", "CPUUtilization", "ServiceName", "api", "ClusterName", "myworld-production"],
          [".", "MemoryUtilization", ".", ".", ".", "."]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "API Resource Utilization"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", "myworld-production"],
          [".", "RequestCount", ".", "."],
          [".", "HTTPCode_Target_5XX_Count", ".", "."],
          [".", "HTTPCode_Target_4XX_Count", ".", "."]
        ],
        "period": 60,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "API Performance"
      }
    }
  ]
}
```

### CloudWatch Alarms

```hcl
# High CPU alarm
resource "aws_cloudwatch_metric_alarm" "api_high_cpu" {
  alarm_name          = "myworld-api-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "API CPU utilization is too high"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.api.name
  }
}


# High error rate alarm
resource "aws_cloudwatch_metric_alarm" "api_high_5xx" {
  alarm_name          = "myworld-api-high-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "API returning too many 5xx errors"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }
}


# Database connection alarm
resource "aws_cloudwatch_metric_alarm" "db_connections" {
  alarm_name          = "myworld-db-high-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 180  # 90% of max_connections
  alarm_description   = "Database connections near limit"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }
}
```

---

## Cost Optimization

### Cost Optimization Strategies

| Strategy | Savings | Trade-off |
|----------|---------|-----------|
| **Fargate Spot** | 70% | Can be interrupted |
| **Reserved Instances** | 40-60% | 1-3 year commitment |
| **Savings Plans** | 30-50% | Flexible across services |
| **S3 Intelligent-Tiering** | 20-40% | Small monitoring fee |
| **gp3 instead of io1** | 50% on storage | Slightly lower IOPS |
| **Right-sizing** | 20-30% | Requires analysis |

### Cost Monitoring

```bash
# AWS Cost Explorer CLI
aws ce get-cost-and-usage \
    --time-period Start=2026-08-01,End=2026-08-31 \
    --granularity MONTHLY \
    --metrics "UnblendedCost" \
    --group-by Type=DIMENSION,Key=SERVICE

# Set up billing alarm
aws cloudwatch put-metric-alarm \
    --alarm-name "monthly-billing-alarm" \
    --alarm-description "Alert when monthly bill exceeds $1000" \
    --metric-name EstimatedCharges \
    --namespace AWS/Billing \
    --statistic Maximum \
    --period 86400 \
    --evaluation-periods 1 \
    --threshold 1000 \
    --comparison-operator GreaterThanThreshold
```

### Resource Tagging for Cost Allocation

```hcl
# Apply to all resources
default_tags {
  tags = {
    Environment = var.environment
    Project     = "myworld"
    Team        = "platform"
    ManagedBy   = "terraform"
    CostCenter  = "engineering"
  }
}
```

---

## Disaster Recovery

### Backup Strategy

| Resource | Backup Method | Retention | RPO | RTO |
|----------|--------------|----------|-----|-----|
| **RDS** | Automated daily snapshots | 30 days | 5 min | 1 hour |
| **RDS** | Point-in-time recovery | 7 days | 5 min | 1 hour |
| **S3** | Cross-region replication | Indefinite | Real-time | 1 hour |
| **ECS Task Definitions** | Terraform | Git history | 0 | 10 min |
| **Secrets** | AWS Secrets Manager | Automatic | 0 | 5 min |
| **Logs** | S3 (CloudWatch export) | 90 days | 5 min | 1 hour |

### Multi-Region Failover

```hcl
# Route 53 failover routing
resource "aws_route53_record" "api_primary" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "api.myworld.com"
  type    = "A"
  ttl     = 60
  records = [aws_lb.primary.dns_name]  # Primary region

  health_check_id = aws_route53_health_check.api_primary.id

  failover_routing_policy {
    type = "PRIMARY"
  }
}

resource "aws_route53_record" "api_secondary" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "api.myworld.com"
  type    = "A"
  ttl     = 60
  records = [aws_lb.secondary.dns_name]  # DR region

  failover_routing_policy {
    type = "SECONDARY"
  }
}
```

---

## Best Practices Summary

| ✅ DO | ❌ DON'T |
|---|---|
| Use multi-AZ deployments | Single AZ for production |
| Use managed services (RDS, ElastiCache) | Self-host databases |
| Encrypt data at rest and in transit | Store data unencrypted |
| Use IAM roles, not access keys | Long-lived credentials |
| Enable CloudTrail in all accounts | Disable audit logging |
| Use private subnets for backends | Put databases in public subnets |
| Enable VPC Flow Logs | Skip network logging |
| Use cost allocation tags | Untagged resources |
| Set up CloudWatch alarms | Monitor reactively |
| Test disaster recovery | Hope backups work |
| Use AWS Secrets Manager | Hardcode secrets |
| Enable deletion protection | Allow accidental deletion |
| Use Fargate Spot for non-critical | Always use on-demand |
| Use CloudFront for static assets | Hit origin for every request |

---

## References

- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [AWS Architecture Center](https://aws.amazon.com/architecture/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [AWS Cost Optimization](https://aws.amazon.com/aws-cost-management/aws-cost-optimization/)
- [AWS Security Best Practices](https://aws.amazon.com/security/best-practices/)
