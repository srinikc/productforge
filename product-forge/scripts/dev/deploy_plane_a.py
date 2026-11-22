#!/usr/bin/env python3
"""
CLI entrypoint for Plane A Cloud Provisioner (BI-PF-1555).
Automates Product Forge cluster deployment with Helm and Terraform.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from core.paths import ROOT
if str(ROOT / "scripts" / "dev") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "dev"))

from plane_a_deployer import PlaneADeployer, DeploymentError


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plane A One-Click Cloud Provisioner for Product Forge cluster deployment"
    )
    parser.add_argument(
        "--provider",
        choices=["aws", "gcp", "local"],
        default="local",
        help="Target cloud provider (default: local)",
    )
    parser.add_argument(
        "--cluster-name",
        default="product-forge-cluster",
        help="Kubernetes cluster identifier",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate deployment and validate templates without mutating cloud resources",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Deployment timeout in seconds (default: 600)",
    )
    parser.add_argument(
        "--health-endpoint",
        default=None,
        help="Override health probe endpoint URL",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit output as JSON",
    )

    args = parser.parse_args()

    deployer = PlaneADeployer(
        provider=args.provider,
        dry_run=args.dry_run,
        timeout_sec=args.timeout,
        cluster_name=args.cluster_name,
    )

    try:
        result = deployer.deploy(health_endpoint=args.health_endpoint)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"[SUCCESS] Product Forge Plane A deployed successfully on {args.provider} in {result['elapsed_sec']}s")
            print(f"Cluster: {result['cluster_name']}")
        return 0
    except DeploymentError as e:
        if args.json:
            print(json.dumps({"status": "FAILED", "error": str(e), "trail": deployer.execution_trail}, indent=2), file=sys.stderr)
        else:
            print(f"[FAILED] Plane A deployment error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
