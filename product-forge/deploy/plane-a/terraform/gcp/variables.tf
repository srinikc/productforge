variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "product-forge-platform"
}

variable "region" {
  description = "GCP Region for cluster deployment"
  type        = string
  default     = "us-central1"
}

variable "cluster_name" {
  description = "GKE cluster identifier"
  type        = string
  default     = "product-forge-gke"
}

variable "db_tier" {
  description = "Cloud SQL machine tier (High Availability Regional)"
  type        = string
  default     = "db-custom-4-16384"
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
