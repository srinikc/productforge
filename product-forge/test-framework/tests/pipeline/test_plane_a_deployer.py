"""
Tests for Plane A One-Click Cloud Provisioner (BI-PF-1555).
Verifies Helm charts, Terraform configurations, orchestration workflow,
health probe verification, and non-destructive rollback.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts" / "dev") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "dev"))

from scripts.dev.plane_a_deployer import PlaneADeployer, DeploymentError


def test_helm_chart_manifest_generation():
    """Verify Helm Chart.yaml and values.yaml exist and contain required properties."""
    helm_dir = ROOT / "deploy" / "plane-a" / "helm" / "product-forge"
    chart_file = helm_dir / "Chart.yaml"
    values_file = helm_dir / "values.yaml"

    assert chart_file.exists(), "Chart.yaml must exist"
    assert values_file.exists(), "values.yaml must exist"

    chart_content = chart_file.read_text(encoding="utf-8")
    assert "name: product-forge" in chart_content
    assert "version: 1.0.0" in chart_content
    assert "apiVersion: v2" in chart_content

    values_content = values_file.read_text(encoding="utf-8")
    assert "pgvector" in values_content
    assert "reclaimPolicy: Retain" in values_content
    assert "core-api" in values_content


def test_helm_chart_postgres_pgvector_and_pv_retention():
    """Verify PostgreSQL manifest specifies pgvector image and Retain volume reclaim policy."""
    postgres_file = ROOT / "deploy" / "plane-a" / "helm" / "product-forge" / "templates" / "postgres-statefulset.yaml"
    assert postgres_file.exists(), "postgres-statefulset.yaml must exist"

    content = postgres_file.read_text(encoding="utf-8")
    assert "kind: StatefulSet" in content
    assert "pgvector" in content
    assert "platform.productforge.io/reclaim-policy: Retain" in content


def test_helm_chart_minio_and_api():
    """Verify MinIO object store and API manifests with health probes and security context."""
    minio_file = ROOT / "deploy" / "plane-a" / "helm" / "product-forge" / "templates" / "minio-deployment.yaml"
    api_file = ROOT / "deploy" / "plane-a" / "helm" / "product-forge" / "templates" / "deployment.yaml"

    assert minio_file.exists(), "minio-deployment.yaml must exist"
    assert api_file.exists(), "deployment.yaml must exist"

    values_content = (ROOT / "deploy" / "plane-a" / "helm" / "product-forge" / "values.yaml").read_text(encoding="utf-8")
    assert "/api/v1/health" in values_content
    api_content = api_file.read_text(encoding="utf-8")
    assert "probes.liveness.path" in api_content
    assert "runAsNonRoot: true" in api_content or "podSecurityContext" in api_content
    assert "prometheus.io/scrape" in api_content


def test_terraform_module_definitions():
    """Verify AWS and GCP Terraform modules declare VPC, Kubernetes cluster, and HA PostgreSQL."""
    aws_main = ROOT / "deploy" / "plane-a" / "terraform" / "aws" / "main.tf"
    gcp_main = ROOT / "deploy" / "plane-a" / "terraform" / "gcp" / "main.tf"

    assert aws_main.exists(), "AWS main.tf must exist"
    assert gcp_main.exists(), "GCP main.tf must exist"

    aws_content = aws_main.read_text(encoding="utf-8")
    assert "aws_vpc" in aws_content
    assert "aws_eks_cluster" in aws_content
    assert "aws_eks_node_group" in aws_content
    assert "aws_db_instance" in aws_content
    assert "multi_az               = true" in aws_content
    assert "vector" in aws_content

    gcp_content = gcp_main.read_text(encoding="utf-8")
    assert "google_compute_network" in gcp_content
    assert "google_container_cluster" in gcp_content
    assert "google_sql_database_instance" in gcp_content
    assert 'availability_type = "REGIONAL"' in gcp_content
    assert "cloudsql.enable_pgvector" in gcp_content


def test_plane_a_deployer_plan():
    """Verify PlaneADeployer plan stage validates manifests and outputs structured plan."""
    deployer = PlaneADeployer(provider="local", dry_run=True)
    plan = deployer.plan()

    assert plan["provider"] == "local"
    assert plan["rollback_policy"] == "non_destructive_reclaim_retain"
    assert "deploy_helm_stack" in plan["stages"]
    assert plan["estimated_time_sec"] <= 600


def test_plane_a_deployer_dry_run():
    """Verify PlaneADeployer dry-run execution succeeds end-to-end under SLA limits."""
    deployer = PlaneADeployer(provider="aws", dry_run=True, timeout_sec=600)
    result = deployer.deploy()

    assert result["status"] == "DEPLOYED"
    assert result["provider"] == "aws"
    assert result["elapsed_sec"] < 10.0
    assert len(result["trail"]) >= 4


def test_plane_a_deployer_health_timeout_and_rollback():
    """Verify that failed health probes trigger non-destructive rollback preserving state."""
    deployer = PlaneADeployer(provider="local", dry_run=False, timeout_sec=5)

    with patch.object(deployer, "deploy_helm_stack", return_value={"release_name": "pf-test", "status": "deployed"}), \
         patch.object(deployer, "health_check", return_value=False):
        with pytest.raises(DeploymentError) as exc_info:
            deployer.deploy()

        assert "Non-destructive rollback executed" in str(exc_info.value)
        # Verify rollback step recorded in trail
        steps = [entry["step"] for entry in deployer.execution_trail]
        assert "rollback" in steps
        # Check preserved resources
        rollback_entry = next(e for e in deployer.execution_trail if e["step"] == "rollback")
        assert "pvc/postgres-data (reclaimPolicy=Retain)" in rollback_entry["details"]["preserved_resources"]


def test_plane_a_deployer_cli():
    """Verify CLI tool executes with --dry-run and returns JSON output with exit code 0."""
    script_path = ROOT / "scripts" / "dev" / "deploy_plane_a.py"
    proc = subprocess.run(
        [sys.executable, str(script_path), "--provider", "gcp", "--dry-run", "--json"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"CLI exited with error: {proc.stderr}"
    output = json.loads(proc.stdout)
    assert output["status"] == "DEPLOYED"
    assert output["provider"] == "gcp"
