output "cluster_name" {
  description = "EKS cluster identifier"
  value       = aws_eks_cluster.pf_eks.name
}

output "cluster_endpoint" {
  description = "EKS cluster control plane endpoint"
  value       = aws_eks_cluster.pf_eks.endpoint
}

output "database_endpoint" {
  description = "RDS Multi-AZ PostgreSQL endpoint"
  value       = aws_db_instance.pf_postgres_ha.endpoint
}

output "artifacts_bucket_name" {
  description = "S3 bucket for artifacts storage"
  value       = aws_s3_bucket.pf_artifacts.id
}
