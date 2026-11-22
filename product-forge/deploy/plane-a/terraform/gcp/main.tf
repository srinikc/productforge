terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# --- VPC Infrastructure ---
resource "google_compute_network" "pf_network" {
  name                    = "${var.cluster_name}-network"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "pf_subnet" {
  name          = "${var.cluster_name}-subnet"
  ip_cidr_range = "10.200.0.0/16"
  region        = var.region
  network       = google_compute_network.pf_network.id

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.201.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.202.0.0/20"
  }
}

# --- Managed Kubernetes (GKE) ---
resource "google_container_cluster" "pf_gke" {
  name     = var.cluster_name
  location = var.region

  network    = google_compute_network.pf_network.name
  subnetwork = google_compute_subnetwork.pf_subnet.name

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  remove_default_node_pool = true
  initial_node_count       = 1
  deletion_protection      = true
}

resource "google_container_node_pool" "pf_nodes" {
  name       = "${var.cluster_name}-node-pool"
  location   = var.region
  cluster    = google_container_cluster.pf_gke.name
  node_count = 3

  node_config {
    machine_type = "e2-standard-4"
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
}

# --- High-Availability Cloud SQL PostgreSQL Database ---
resource "google_sql_database_instance" "pf_sql_ha" {
  name             = "${var.cluster_name}-sql-ha"
  database_version = "POSTGRES_16"
  region           = var.region
  deletion_protection = true

  settings {
    tier              = var.db_tier
    availability_type = "REGIONAL" # High Availability multi-zone

    database_flags {
      name  = "cloudsql.enable_pgvector"
      value = "on"
    }

    backup_configuration {
      enabled    = true
      point_in_time_recovery_enabled = true
    }
  }
}

resource "google_sql_database" "pf_db" {
  name     = var.db_name
  instance = google_sql_database_instance.pf_sql_ha.name
}

resource "google_sql_user" "pf_user" {
  name     = var.db_username
  instance = google_sql_database_instance.pf_sql_ha.name
  password = var.db_password
}

# --- GCS Artifact Storage Bucket ---
resource "google_storage_bucket" "pf_artifacts" {
  name          = "${var.project_id}-${var.cluster_name}-artifacts"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true
}
