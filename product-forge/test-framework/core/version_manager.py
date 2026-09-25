"""
Version Manager - Semantic versioning and changelog management.

Phase 1.10 (CRITICAL): Semantic versioning for releases.
"""
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict, field


@dataclass
class VersionManifest:
    """Version manifest for a release."""
    version: str
    git_tag: str
    bump_type: str
    breaking: bool
    changelog: list
    timestamp: str
    previous_version: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class VersionManager:
    """Manages semantic versioning for a project."""
    
    VERSION_FILE = "version.json"
    INITIAL_VERSION = "0.1.0"
    
    def __init__(self, project: str, products_dir: str = "products"):
        self.project = project
        self.products_dir = Path(products_dir)
        self.version_file = self.products_dir / project / self.VERSION_FILE
        self.version_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.version_file.exists():
            self._initialize()
        
        self.data = self._load()
    
    def _initialize(self) -> None:
        """Initialize version file."""
        initial = {
            "version": self.INITIAL_VERSION,
            "git_tag": f"v{self.INITIAL_VERSION}",
            "changelog": [],
            "created_at": datetime.utcnow().isoformat(),
        }
        self.version_file.write_text(json.dumps(initial, indent=2))
    
    def _load(self) -> dict:
        """Load version data."""
        try:
            return json.loads(self.version_file.read_text())
        except (json.JSONDecodeError, OSError):
            self._initialize()
            return json.loads(self.version_file.read_text())
    
    def _save(self) -> None:
        """Save version data."""
        self.version_file.write_text(json.dumps(self.data, indent=2))
    
    def get_current_version(self) -> str:
        """Get the current version string."""
        return self.data["version"]
    
    def bump(self, bump_type: str) -> VersionManifest:
        """
        Bump the version.
        
        Args:
            bump_type: One of "major", "minor", "patch"
        
        Returns:
            Version manifest for the new version
        """
        major, minor, patch, pre_release = self.parse_semver(self.data["version"]).values()
        
        if bump_type == "major":
            major += 1
            minor = 0
            patch = 0
            breaking = True
        elif bump_type == "minor":
            minor += 1
            patch = 0
            breaking = False
        elif bump_type == "patch":
            patch += 1
            breaking = False
        else:
            raise ValueError(f"Invalid bump type: {bump_type}")
        
        new_version = self.format_semver(major, minor, patch, pre_release or None)
        previous = self.data["version"]
        
        manifest = VersionManifest(
            version=new_version,
            git_tag=f"v{new_version}",
            bump_type=bump_type,
            breaking=breaking,
            changelog=list(self.data.get("changelog", [])),
            timestamp=datetime.utcnow().isoformat(),
            previous_version=previous,
        )
        
        # Update data
        self.data["version"] = new_version
        self.data["git_tag"] = manifest.git_tag
        self.data["last_bump"] = bump_type
        self.data["last_bump_at"] = manifest.timestamp
        # Don't clear changelog - it's the cumulative history
        
        self._save()
        
        return manifest
    
    @staticmethod
    def parse_semver(version: str) -> dict:
        """
        Parse a semantic version string.
        
        Example: "1.2.3-beta+build" -> {major: 1, minor: 2, patch: 3, pre_release: "beta", build_metadata: "build"}
        """
        pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.-]+))?(?:\+([a-zA-Z0-9.-]+))?$"
        match = re.match(pattern, version)
        
        if not match:
            # Try to handle missing parts gracefully
            parts = version.split(".")
            while len(parts) < 3:
                parts.append("0")
            
            return {
                "major": int(parts[0]) if parts[0].isdigit() else 0,
                "minor": int(parts[1]) if parts[1].isdigit() else 0,
                "patch": int(parts[2].split("-")[0]) if parts[2].split("-")[0].isdigit() else 0,
                "pre_release": None,
                "build_metadata": None,
            }
        
        return {
            "major": int(match.group(1)),
            "minor": int(match.group(2)),
            "patch": int(match.group(3)),
            "pre_release": match.group(4),
            "build_metadata": match.group(5),
        }
    
    @staticmethod
    def format_semver(major: int, minor: int, patch: int, pre_release: Optional[str] = None) -> str:
        """Format a semantic version string."""
        version = f"{major}.{minor}.{patch}"
        if pre_release:
            version += f"-{pre_release}"
        return version
    
    def add_changelog_entry(self, change_type: str, description: str, scope: Optional[str] = None) -> dict:
        """
        Add an entry to the changelog.
        
        Args:
            change_type: Type of change (feat, fix, docs, etc.)
            description: Description of the change
            scope: Optional scope (component name)
        
        Returns:
            The changelog entry
        """
        entry = {
            "type": change_type,
            "description": description,
            "scope": scope,
            "timestamp": datetime.utcnow().isoformat(),
            "version": self.data["version"],
        }
        
        if "changelog" not in self.data:
            self.data["changelog"] = []
        
        self.data["changelog"].append(entry)
        self._save()
        
        return entry
    
    def generate_changelog(self, version: Optional[str] = None) -> str:
        """
        Generate a Markdown changelog.
        
        Args:
            version: Specific version to generate for (default: current)
        
        Returns:
            Markdown formatted changelog
        """
        target_version = version or self.data["version"]
        entries = [e for e in self.data.get("changelog", []) if e.get("version") == target_version]
        
        md = f"# Changelog - v{target_version}\n\n"
        
        if not entries:
            md += "_No changes recorded_\n"
            return md
        
        # Group by type
        by_type: dict[str, list] = {}
        for entry in entries:
            change_type = entry.get("type", "other")
            by_type.setdefault(change_type, []).append(entry)
        
        type_order = ["feat", "fix", "perf", "refactor", "docs", "test", "chore"]
        for t in type_order:
            if t in by_type:
                md += f"## {t.upper()}\n\n"
                for entry in by_type[t]:
                    scope = f"**{entry.get('scope')}**: " if entry.get("scope") else ""
                    md += f"- {scope}{entry.get('description', '')}\n"
                md += "\n"
        
        return md
    
    def get_version_info(self) -> dict:
        """Get full version info."""
        return {
            "version": self.data["version"],
            "git_tag": self.data.get("git_tag", f"v{self.data['version']}"),
            "last_bump": self.data.get("last_bump"),
            "last_bump_at": self.data.get("last_bump_at"),
            "changelog_entries": len(self.data.get("changelog", [])),
        }
