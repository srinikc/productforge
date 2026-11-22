variable "aws_region" {
  description = "AWS region for Product Forge cluster deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name (production, staging, dev)"
  type        = string
  default     = "production"
}

variable "cluster_name" {
  description = "EKS cluster identifier"
  type        = string
  default     = "product-forge-cluster"
}

variable "vpc_cidr" {
  description = "CIDR block for the dedicated VPC"
  type        = string
  default     = "10.100.0.0/16"
}

variable "db_instance_class" {
  description = "RDS PostgreSQL instance class (High Availability Multi-AZ)"
  type        = string
  default     = "db.r6g.large"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in gigabytes"
  type        = number
  default     = 100
}

variable "db_name" {
  description = "Initial database name"
  type        = string
  default     = "productforge"
}

variable "db_username" {
  description = "Master database username"
  type        = string
  default     = "pf_admin"
}

variable "db_password" {
  description = "Master database password"
  type        = string
  sensitive   = true
  default     = "change-in-production-vault"
}
