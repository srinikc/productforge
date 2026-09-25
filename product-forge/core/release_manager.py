"""
Release Manager
Manages install, upgrade, patching, and rollback mechanisms.

Industry Standard: Ring-based deployment, expand-contract migrations,
immutable artifacts, rollback plans.

Provides:
- Product install/upgrade/patch orchestration
- Rollback mechanism (backup + restore)
- Version detection and compatibility checks
- Deployment strategy selection (in-place, rolling, blue-green, canary)
- Resource footprint analysis (RAM, CPU, HDD)
- Patch management with ring-based deployment
"""

import json
import shutil
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


@dataclass
class ArtifactDescriptor:
    """Descriptor for a build artifact"""
    id: str
    version: str
    type: str  # installer, docker, npm, pypi, binary, archive
    platform: str  # windows, linux, macos, all
    architecture: str  # x64, arm64, universal
    file_path: str
    checksum_sha256: str
    size_bytes: int
    silent_switches: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactDescriptor":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DeployTicket:
    """Deployment ticket - coordination contract between agents"""
    id: str
    version: str
    artifact_id: str
    strategy: str  # in-place, rolling, blue-green, canary
    target_environment: str  # dev, staging, production
    ring: int = 0  # 0=test, 1=early adopters, 2=general, 3=critical
    canary_steps: int = 0
    gate_metrics: Dict[str, Any] = field(default_factory=dict)
    rollback_plan: Optional[Dict[str, Any]] = None
    status: str = "pending"  # pending, executing, completed, failed, rolled_back
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeployTicket":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PatchSet:
    """Set of patches to be applied"""
    id: str
    version: str
    patches: List[Dict[str, Any]]
    priority: str  # critical, high, medium, low
    cve_references: List[str] = field(default_factory=list)
    affected_components: List[str] = field(default_factory=list)
    test_status: str = "pending"  # pending, testing, passed, failed
    deployment_status: str = "pending"  # pending, deploying, deployed, rolled_back

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatchSet":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ResourceFootprint:
    """Resource requirements for a product"""
    install_disk_mb: float = 0
    runtime_disk_mb: float = 0
    min_ram_mb: float = 0
    recommended_ram_mb: float = 0
    min_cpu_cores: float = 0
    recommended_cpu_cores: float = 0
    network_requirements: List[str] = field(default_factory=list)
    ports_required: List[int] = field(default_factory=list)
    dependencies: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResourceFootprint":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ReleaseManager:
    """
    Manages install, upgrade, patching, and rollback for products.

    Industry Standard Approach:
    - SemVer for versioning (via VersionManager)
    - Immutable artifacts with checksums
    - Ring-based deployment (0=test, 1=early, 2=general, 3=critical)
    - Expand-contract for DB migrations
    - Rollback plans generated at deploy time
    - Resource footprint analysis for capacity planning
    """

    def __init__(self, project: str, products_dir: str = "products"):
        self.project = project
        self.products_dir = Path(products_dir)
        self.project_dir = self.products_dir / project
        self.release_dir = self.project_dir / "releases"
        self.backups_dir = self.project_dir / "backups"
        self.patches_dir = self.project_dir / "patches"

        # Create directories
        self.release_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.patches_dir.mkdir(parents=True, exist_ok=True)

        self.release_file = self.project_dir / "release-manifest.json"
        self._load_or_create()

    def _load_or_create(self):
        if self.release_file.exists():
            with open(self.release_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = self._create_empty()

    def _create_empty(self) -> Dict[str, Any]:
        return {
            "$schema": "release-manifest-v1",
            "version": "1.0.0",
            "artifacts": [],
            "deploy_tickets": [],
            "patch_sets": [],
            "rollbacks": [],
            "resource_footprint": {},
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "release_manager",
            },
        }

    # ==================== ARTIFACT MANAGEMENT ====================

    def register_artifact(
        self,
        version: str,
        artifact_type: str,
        platform: str,
        file_path: str,
        architecture: str = "x64",
        silent_switches: str = "",
        metadata: Dict[str, Any] = None,
    ) -> ArtifactDescriptor:
        """Register a build artifact with checksum"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found: {file_path}")

        # Calculate checksum
        sha256 = self._calculate_checksum(file_path)
        size = path.stat().st_size

        artifact_id = f"{self.project}-{version}-{platform}-{architecture}"

        descriptor = ArtifactDescriptor(
            id=artifact_id,
            version=version,
            type=artifact_type,
            platform=platform,
            architecture=architecture,
            file_path=str(path),
            checksum_sha256=sha256,
            size_bytes=size,
            silent_switches=silent_switches,
            metadata=metadata or {},
        )

        self.data["artifacts"].append(descriptor.to_dict())
        self._save()
        return descriptor

    def get_artifacts(self, version: str = None, platform: str = None) -> List[ArtifactDescriptor]:
        """Get artifacts filtered by version and/or platform"""
        artifacts = []
        for a in self.data.get("artifacts", []):
            if version and a.get("version") != version:
                continue
            if platform and a.get("platform") != platform:
                continue
            artifacts.append(ArtifactDescriptor.from_dict(a))
        return artifacts

    def verify_artifact(self, artifact_id: str) -> Dict[str, Any]:
        """Verify artifact integrity via checksum"""
        for a in self.data.get("artifacts", []):
            if a["id"] == artifact_id:
                current_checksum = self._calculate_checksum(a["file_path"])
                return {
                    "artifact_id": artifact_id,
                    "expected_checksum": a["checksum_sha256"],
                    "actual_checksum": current_checksum,
                    "is_valid": current_checksum == a["checksum_sha256"],
                }
        return {"artifact_id": artifact_id, "error": "Artifact not found"}

    # ==================== DEPLOYMENT ====================

    def create_deploy_ticket(
        self,
        version: str,
        artifact_id: str,
        strategy: str = "rolling",
        target_environment: str = "staging",
        ring: int = 0,
        canary_steps: int = 5,
        gate_metrics: Dict[str, Any] = None,
    ) -> DeployTicket:
        """Create a deployment ticket"""
        ticket_id = f"deploy-{version}-{target_environment}-{ring}"

        # Generate rollback plan
        rollback_plan = self._generate_rollback_plan(version, target_environment)

        ticket = DeployTicket(
            id=ticket_id,
            version=version,
            artifact_id=artifact_id,
            strategy=strategy,
            target_environment=target_environment,
            ring=ring,
            canary_steps=canary_steps,
            gate_metrics=gate_metrics or {"success_rate": 95, "error_rate_max": 5},
            rollback_plan=rollback_plan,
            status="pending",
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        self.data["deploy_tickets"].append(ticket.to_dict())
        self._save()
        return ticket

    def update_deploy_status(self, ticket_id: str, status: str):
        """Update deployment ticket status"""
        for ticket in self.data["deploy_tickets"]:
            if ticket["id"] == ticket_id:
                ticket["status"] = status
                if status in ("completed", "failed", "rolled_back"):
                    ticket["completed_at"] = datetime.now(timezone.utc).isoformat()
                break
        self._save()

    def select_strategy(self, risk_level: str, product_type: str) -> str:
        """Select deployment strategy based on risk and product type"""
        strategy_map = {
            "critical": "blue-green",
            "high": "canary",
            "medium": "rolling",
            "low": "in-place",
        }
        if product_type in ("saas", "microservice"):
            return strategy_map.get(risk_level, "canary")
        elif product_type in ("desktop", "embedded"):
            return "in-place"
        elif product_type == "monolith":
            return strategy_map.get(risk_level, "rolling")
        return strategy_map.get(risk_level, "rolling")

    # ==================== PATCH MANAGEMENT ====================

    def create_patch_set(
        self,
        version: str,
        patches: List[Dict[str, Any]],
        priority: str = "medium",
        cve_references: List[str] = None,
        affected_components: List[str] = None,
    ) -> PatchSet:
        """Create a patch set for deployment"""
        patch_id = f"patch-{version}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        patch_set = PatchSet(
            id=patch_id,
            version=version,
            patches=patches,
            priority=priority,
            cve_references=cve_references or [],
            affected_components=affected_components or [],
        )

        self.data["patch_sets"].append(patch_set.to_dict())
        self._save()
        return patch_set

    def update_patch_status(self, patch_id: str, test_status: str = None, deployment_status: str = None):
        """Update patch set status"""
        for patch in self.data["patch_sets"]:
            if patch["id"] == patch_id:
                if test_status:
                    patch["test_status"] = test_status
                if deployment_status:
                    patch["deployment_status"] = deployment_status
                break
        self._save()

    # ==================== ROLLBACK ====================

    def create_backup(self, version: str, backup_type: str = "pre-upgrade") -> Dict[str, Any]:
        """Create backup before upgrade/patch"""
        backup_id = f"backup-{version}-{backup_type}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        backup_path = self.backups_dir / backup_id
        backup_path.mkdir(parents=True, exist_ok=True)

        # Copy current version info
        version_file = self.project_dir / "version.json"
        if version_file.exists():
            shutil.copy2(version_file, backup_path / "version.json")

        # Copy current state
        state_file = self.project_dir / "state.json"
        if state_file.exists():
            shutil.copy2(state_file, backup_path / "state.json")

        backup_info = {
            "id": backup_id,
            "version": version,
            "type": backup_type,
            "path": str(backup_path),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.data["rollbacks"].append(backup_info)
        self._save()
        return backup_info

    def rollback(self, backup_id: str) -> Dict[str, Any]:
        """Restore from backup"""
        for backup in self.data["rollbacks"]:
            if backup["id"] == backup_id:
                backup_path = Path(backup["path"])
                if backup_path.exists():
                    # Restore version.json
                    version_backup = backup_path / "version.json"
                    if version_backup.exists():
                        shutil.copy2(version_backup, self.project_dir / "version.json")

                    return {
                        "success": True,
                        "backup_id": backup_id,
                        "restored_version": backup.get("version"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                else:
                    return {"success": False, "error": "Backup path not found"}
        return {"success": False, "error": "Backup not found"}

    def _generate_rollback_plan(self, version: str, environment: str) -> Dict[str, Any]:
        """Generate rollback plan for a deployment"""
        # Find previous version
        current_version = self.data.get("metadata", {}).get("current_version", version)
        previous_version = None
        for release in reversed(self.data.get("artifacts", [])):
            if release.get("version") != version:
                previous_version = release.get("version")
                break

        return {
            "previous_version": previous_version,
            "backup_required": True,
            "rollback_type": "in-place",
            "estimated_time_minutes": 5,
            "steps": [
                "Stop current service",
                f"Restore from backup of version {previous_version}",
                "Verify version matches expected",
                "Start service",
                "Run health check",
            ],
        }

    # ==================== RESOURCE FOOTPRINT ====================

    def set_resource_footprint(self, footprint: ResourceFootprint):
        """Set resource footprint for the product"""
        self.data["resource_footprint"] = footprint.to_dict()
        self._save()

    def get_resource_footprint(self) -> ResourceFootprint:
        """Get resource footprint"""
        data = self.data.get("resource_footprint", {})
        if data:
            return ResourceFootprint.from_dict(data)
        return ResourceFootprint()

    def estimate_footprint(self, product_type: str, tech_stack: List[str]) -> ResourceFootprint:
        """Estimate resource footprint based on product type and tech stack"""
        base_footprints = {
            "web_app": ResourceFootprint(
                install_disk_mb=500, runtime_disk_mb=1000,
                min_ram_mb=512, recommended_ram_mb=2048,
                min_cpu_cores=1, recommended_cpu_cores=2,
                ports_required=[80, 443],
            ),
            "api_service": ResourceFootprint(
                install_disk_mb=200, runtime_disk_mb=500,
                min_ram_mb=256, recommended_ram_mb=1024,
                min_cpu_cores=1, recommended_cpu_cores=2,
                ports_required=[8080],
            ),
            "desktop_app": ResourceFootprint(
                install_disk_mb=100, runtime_disk_mb=300,
                min_ram_mb=256, recommended_ram_mb=512,
                min_cpu_cores=1, recommended_cpu_cores=1,
            ),
            "microservice": ResourceFootprint(
                install_disk_mb=100, runtime_disk_mb=256,
                min_ram_mb=128, recommended_ram_mb=512,
                min_cpu_cores=0.5, recommended_cpu_cores=1,
                ports_required=[8080],
            ),
        }

        footprint = base_footprints.get(product_type, ResourceFootprint())

        # Adjust for tech stack
        for tech in tech_stack:
            tech_lower = tech.lower()
            if "docker" in tech_lower or "kubernetes" in tech_lower:
                footprint.runtime_disk_mb *= 1.5
                footprint.min_ram_mb *= 1.5
            elif "database" in tech_lower or "postgres" in tech_lower or "mysql" in tech_lower:
                footprint.runtime_disk_mb *= 2
                footprint.min_ram_mb *= 2
                footprint.network_requirements.append("Database connection")
            elif "redis" in tech_lower or "cache" in tech_lower:
                footprint.min_ram_mb += 256
                footprint.network_requirements.append("Cache connection")

        return footprint

    # ==================== VERSION DETECTION ====================

    def detect_installed_version(self) -> Optional[str]:
        """Detect currently installed version"""
        version_file = self.project_dir / "version.json"
        if version_file.exists():
            with open(version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("version")
        return None

    def check_compatibility(self, target_version: str, current_version: str) -> Dict[str, Any]:
        """Check compatibility between versions"""
        from .version_manager import VersionManager
        current = VersionManager.parse_semver(current_version)
        target = VersionManager.parse_semver(target_version)

        is_upgrade = (
            target["major"] > current["major"]
            or (target["major"] == current["major"] and target["minor"] > current["minor"])
            or (target["major"] == current["major"] and target["minor"] == current["minor"] and target["patch"] > current["patch"])
        )
        is_downgrade = not is_upgrade

        breaking = target["major"] > current["major"]

        return {
            "current_version": current_version,
            "target_version": target_version,
            "is_upgrade": is_upgrade,
            "is_downgrade": is_downgrade,
            "breaking_change": breaking,
            "compatible": not is_downgrade,
            "recommendation": "Can proceed" if is_upgrade and not breaking else ("Caution: breaking changes" if breaking else "Downgrade not recommended"),
        }

    # ==================== HELPERS ====================

    @staticmethod
    def _calculate_checksum(file_path: str) -> str:
        """Calculate SHA256 checksum of a file"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _save(self):
        """Save release data to disk"""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        with open(self.release_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
