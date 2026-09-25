"""
Version Manager
Semantic Versioning (SemVer 2.0.0) + Conventional Commits + Release Management.

Single source of truth for product versions. Emits Version Manifest consumed by
Build, Packaging, and Deploy agents.

Industry Standard: SemVer + Conventional Commits + commit-and-tag-version
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


@dataclass
class VersionManifest:
    """Version manifest - single source of truth for a release"""
    version: str
    previous_version: str
    git_tag: str
    git_sha: Optional[str] = None
    build_date: Optional[str] = None
    changelog_url: Optional[str] = None
    breaking: bool = False
    pre_release: Optional[str] = None
    build_metadata: Optional[str] = None
    bump_type: str = "patch"  # major, minor, patch
    modules_changed: List[str] = field(default_factory=list)
    features_added: List[str] = field(default_factory=list)
    features_fixed: List[str] = field(default_factory=list)
    features_removed: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VersionManifest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ChangeEntry:
    """Single changelog entry following Keep a Changelog format"""
    type: str  # feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert
    scope: Optional[str]
    description: str
    breaking: bool = False
    reference: Optional[str] = None
    timestamp: Optional[str] = None
    agent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChangeEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class VersionManager:
    """
    Manages semantic versioning, changelogs, and release management.

    Single source of truth: products/<name>/version.json
    Changelog: products/<name>/CHANGELOG.md
    """

    def __init__(self, project: str, products_dir: str = "products"):
        self.project = project
        self.products_dir = Path(products_dir)
        self.project_dir = self.products_dir / project
        self.version_file = self.project_dir / "version.json"
        self.changelog_file = self.project_dir / "CHANGELOG.md"
        self._load_or_create()

    def _load_or_create(self):
        """Load existing version or create new one"""
        if self.version_file.exists():
            with open(self.version_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = self._create_empty()

    def _create_empty(self) -> Dict[str, Any]:
        """Create empty version structure"""
        return {
            "$schema": "version-v1",
            "version": "0.1.0",
            "previous_version": "0.0.0",
            "git_tag": "v0.1.0",
            "git_sha": None,
            "build_date": None,
            "breaking": False,
            "bump_type": "patch",
            "changelog": [],
            "releases": [],
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "version_manager",
                "schema_version": "1.0.0",
            },
        }

    @staticmethod
    def parse_semver(version: str) -> Dict[str, int]:
        """Parse semantic version string into components"""
        match = re.match(
            r"^v?(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.]+))?(?:\+([a-zA-Z0-9.]+))?$",
            version,
        )
        if not match:
            raise ValueError(f"Invalid semver: {version}")
        return {
            "major": int(match.group(1)),
            "minor": int(match.group(2)),
            "patch": int(match.group(3)),
            "pre_release": match.group(4),
            "build_metadata": match.group(5),
        }

    @staticmethod
    def format_semver(major: int, minor: int, patch: int, pre_release: str = None, build_metadata: str = None) -> str:
        """Format version components into semver string"""
        version = f"{major}.{minor}.{patch}"
        if pre_release:
            version += f"-{pre_release}"
        if build_metadata:
            version += f"+{build_metadata}"
        return version

    def bump(self, bump_type: str, pre_release: str = None, build_metadata: str = None) -> VersionManifest:
        """
        Bump version according to semver rules.

        Args:
            bump_type: 'major', 'minor', or 'patch'
            pre_release: Optional pre-release identifier
            build_metadata: Optional build metadata

        Returns:
            VersionManifest with new version info
        """
        current = self.parse_semver(self.data["version"])
        major, minor, patch = current["major"], current["minor"], current["patch"]

        if bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif bump_type == "minor":
            minor += 1
            patch = 0
        elif bump_type == "patch":
            patch += 1
        else:
            raise ValueError(f"Invalid bump type: {bump_type}")

        new_version = self.format_semver(major, minor, patch, pre_release, build_metadata)
        previous = self.data["version"]

        manifest = VersionManifest(
            version=new_version,
            previous_version=previous,
            git_tag=f"v{new_version}",
            build_date=datetime.now(timezone.utc).isoformat(),
            breaking=(bump_type == "major"),
            pre_release=pre_release,
            build_metadata=build_metadata,
            bump_type=bump_type,
        )

        # Update version file
        self.data["previous_version"] = previous
        self.data["version"] = new_version
        self.data["git_tag"] = manifest.git_tag
        self.data["build_date"] = manifest.build_date
        self.data["breaking"] = manifest.breaking
        self.data["bump_type"] = bump_type

        # Add to releases
        self.data["releases"].append({
            "version": new_version,
            "previous_version": previous,
            "git_tag": manifest.git_tag,
            "timestamp": manifest.build_date,
            "bump_type": bump_type,
            "breaking": manifest.breaking,
        })

        self._save()
        return manifest

    def bump_from_commits(self, commits: List[Dict[str, str]]) -> VersionManifest:
        """
        Determine bump type from conventional commits.

        Args:
            commits: List of dicts with 'type', 'scope', 'description', 'breaking'

        Returns:
            VersionManifest with appropriate bump
        """
        has_breaking = any(c.get("breaking", False) for c in commits)
        has_feat = any(c.get("type") == "feat" for c in commits)
        has_fix = any(c.get("type") == "fix" for c in commits)

        if has_breaking:
            bump_type = "major"
        elif has_feat:
            bump_type = "minor"
        elif has_fix:
            bump_type = "patch"
        else:
            bump_type = "patch"

        manifest = self.bump(bump_type)

        # Record changelog entries
        for commit in commits:
            self.add_changelog_entry(
                entry_type=commit.get("type", "chore"),
                scope=commit.get("scope"),
                description=commit.get("description", ""),
                breaking=commit.get("breaking", False),
            )

        manifest.modules_changed = [c.get("scope", "") for c in commits if c.get("scope")]
        manifest.features_added = [c["description"] for c in commits if c.get("type") == "feat"]
        manifest.features_fixed = [c["description"] for c in commits if c.get("type") == "fix"]
        manifest.features_removed = [c["description"] for c in commits if c.get("type") == "revert"]

        return manifest

    def add_changelog_entry(
        self,
        entry_type: str,
        description: str,
        scope: str = None,
        breaking: bool = False,
        reference: str = None,
        agent: str = None,
    ):
        """Add an entry to the changelog"""
        entry = ChangeEntry(
            type=entry_type,
            scope=scope,
            description=description,
            breaking=breaking,
            reference=reference,
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent=agent,
        )
        self.data["changelog"].append(entry.to_dict())
        self._save()

    def generate_changelog(self) -> str:
        """Generate CHANGELOG.md following Keep a Changelog format"""
        md = []
        md.append(f"# Changelog")
        md.append("")
        md.append(f"All notable changes to **{self.project}** will be documented in this file.")
        md.append("")
        md.append(f"The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),")
        md.append(f"and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).")
        md.append("")

        # Group by version
        releases = {}
        for entry in reversed(self.data.get("changelog", [])):
            # Find which release this belongs to
            version = entry.get("version", self.data["version"])
            if version not in releases:
                releases[version] = []
            releases[version].append(entry)

        # Group releases by type
        for release_data in reversed(self.data.get("releases", [])):
            version = release_data["version"]
            timestamp = release_data.get("timestamp", "")[:10]
            entries = releases.get(version, [])

            md.append(f"## [{version}] - {timestamp}")
            md.append("")

            # Group by type
            types_order = ["added", "changed", "deprecated", "removed", "fixed", "security"]
            type_groups = {}
            for entry in entries:
                entry_type = entry.get("type", "chore")
                if entry_type == "feat":
                    entry_type = "added"
                elif entry_type == "fix":
                    entry_type = "fixed"
                elif entry_type == "refactor":
                    entry_type = "changed"
                elif entry_type == "perf":
                    entry_type = "changed"
                elif entry_type == "revert":
                    entry_type = "removed"
                elif entry_type in ("docs", "style", "test", "build", "ci", "chore"):
                    entry_type = "changed"

                if entry_type not in type_groups:
                    type_groups[entry_type] = []
                type_groups[entry_type].append(entry)

            for t in types_order:
                if t in type_groups:
                    md.append(f"### {t.capitalize()}")
                    md.append("")
                    for entry in type_groups[t]:
                        scope = f"**{entry['scope']}:** " if entry.get("scope") else ""
                        breaking_marker = " ⚠️ BREAKING" if entry.get("breaking") else ""
                        md.append(f"- {scope}{entry['description']}{breaking_marker}")
                    md.append("")

        return "\n".join(md)

    def get_current_version(self) -> str:
        """Get current version string"""
        return self.data.get("version", "0.1.0")

    def get_version_info(self) -> Dict[str, Any]:
        """Get complete version information"""
        return {
            "version": self.data.get("version"),
            "previous_version": self.data.get("previous_version"),
            "git_tag": self.data.get("git_tag"),
            "build_date": self.data.get("build_date"),
            "breaking": self.data.get("breaking"),
            "bump_type": self.data.get("bump_type"),
            "changelog_count": len(self.data.get("changelog", [])),
            "releases_count": len(self.data.get("releases", [])),
        }

    def validate_consistency(self, manifest: VersionManifest) -> Dict[str, Any]:
        """
        Validate version consistency across all sources.

        Returns:
            Dict with is_consistent flag and details
        """
        current = self.parse_semver(manifest.version)
        tag_version = manifest.git_tag.lstrip("v")

        checks = {
            "version_format_valid": True,
            "tag_matches_version": manifest.version == tag_version,
            "manifest_version_matches": manifest.version == self.data.get("version"),
            "previous_version_set": bool(manifest.previous_version),
            "build_date_set": bool(manifest.build_date),
        }

        return {
            "is_consistent": all(checks.values()),
            "checks": checks,
            "version": manifest.version,
            "git_tag": manifest.git_tag,
        }

    def record_release(self, manifest: VersionManifest, artifacts: List[str] = None, notes: str = None):
        """Record a release with its artifacts"""
        release = {
            "version": manifest.version,
            "git_tag": manifest.git_tag,
            "git_sha": manifest.git_sha,
            "timestamp": manifest.build_date,
            "bump_type": manifest.bump_type,
            "breaking": manifest.breaking,
            "artifacts": artifacts or [],
            "notes": notes,
        }
        self.data["releases"].append(release)
        self._save()

    def save_changelog(self):
        """Save changelog markdown file"""
        md = self.generate_changelog()
        self.changelog_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.changelog_file, "w", encoding="utf-8") as f:
            f.write(md)

    def _save(self):
        """Save version data to disk"""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        with open(self.version_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
