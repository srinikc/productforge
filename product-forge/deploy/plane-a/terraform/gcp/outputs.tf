output "cluster_name" {
  description = "GKE cluster identifier"
  value       = google_container_cluster.pf_gke.name
}

output "cluster_endpoint" {
  description = "GKE cluster control plane endpoint"
  value       = google_container_cluster.pf_gke.endpoint
}

output "database_connection_name" {
  description = "Cloud SQL HA database connection string name"
  value       = google_sql_database_instance.pf_sql_ha.connection_name
}

output "artifacts_bucket_name" {
  description = "GCS bucket for artifacts storage"
  value       = google_storage_bucket.pf_artifacts.name
}
