"""
Build Utility - Generates deployable builds after implementation.

Called by implement agent after each phase to generate:
- Docker image
- Web bundle
- Mobile builds (iOS/Android)

Builds are saved to builds/<project>/<phase>/ directory.
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class BuildResult:
    """Result of a build operation."""
    project: str
    phase: str
    build_type: str  # docker, web, ios, android
    success: bool
    output_path: str = ""
    error: str = ""
    duration_seconds: float = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class BuildUtility:
    """Generates deployable builds."""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.builds_dir = self.project_dir / "builds"

    def build_all(self, phase: str, build_types: List[str] = None) -> List[BuildResult]:
        """Build all types for a phase."""
        if build_types is None:
            build_types = ["docker", "web"]

        results = []
        for build_type in build_types:
            if build_type == "docker":
                results.append(self.build_docker(phase))
            elif build_type == "web":
                results.append(self.build_web(phase))
            elif build_type == "ios":
                results.append(self.build_ios(phase))
            elif build_type == "android":
                results.append(self.build_android(phase))
            else:
                results.append(BuildResult(
                    project=self.project_dir.name,
                    phase=phase,
                    build_type=build_type,
                    success=False,
                    error=f"Unknown build type: {build_type}"
                ))

        # Save build manifest
        self._save_manifest(phase, results)

        return results

    def build_docker(self, phase: str) -> BuildResult:
        """Build Docker image."""
        start_time = datetime.now()
        project_name = self.project_dir.name
        tag = f"{project_name}:phase{phase}"

        try:
            # Check if Dockerfile exists
            dockerfile = self.project_dir / "Dockerfile"
            if not dockerfile.exists():
                return BuildResult(
                    project=project_name,
                    phase=phase,
                    build_type="docker",
                    success=False,
                    error="No Dockerfile found"
                )

            # Build Docker image
            result = subprocess.run(
                ["docker", "build", "-t", tag, "."],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(self.project_dir)
            )

            duration = (datetime.now() - start_time).total_seconds()

            if result.returncode == 0:
                # Save image to tar
                output_dir = self.builds_dir / phase / "docker"
                output_dir.mkdir(parents=True, exist_ok=True)
                tar_path = output_dir / f"{project_name}_phase{phase}.tar"

                save_result = subprocess.run(
                    ["docker", "save", "-o", str(tar_path), tag],
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                if save_result.returncode == 0:
                    return BuildResult(
                        project=project_name,
                        phase=phase,
                        build_type="docker",
                        success=True,
                        output_path=str(tar_path),
                        duration_seconds=duration
                    )
                else:
                    return BuildResult(
                        project=project_name,
                        phase=phase,
                        build_type="docker",
                        success=False,
                        error=f"Failed to save image: {save_result.stderr}",
                        duration_seconds=duration
                    )
            else:
                return BuildResult(
                    project=project_name,
                    phase=phase,
                    build_type="docker",
                    success=False,
                    error=f"Build failed: {result.stderr}",
                    duration_seconds=duration
                )

        except subprocess.TimeoutExpired:
            return BuildResult(
                project=project_name,
                phase=phase,
                build_type="docker",
                success=False,
                error="Build timed out after 5 minutes"
            )
        except Exception as e:
            return BuildResult(
                project=project_name,
                phase=phase,
                build_type="docker",
                success=False,
                error=str(e)
            )

    def build_web(self, phase: str) -> BuildResult:
        """Build web frontend."""
        start_time = datetime.now()
        project_name = self.project_dir.name

        try:
            # Check for package.json
            package_json = self.project_dir / "package.json"
            if not package_json.exists():
                # Try apps/web directory
                web_dir = self.project_dir / "apps" / "web"
                if not web_dir.exists():
                    return BuildResult(
                        project=project_name,
                        phase=phase,
                        build_type="web",
                        success=False,
                        error="No package.json or apps/web directory found"
                    )
                build_dir = web_dir
            else:
                build_dir = self.project_dir

            # Run build command
            result = subprocess.run(
                ["pnpm", "build"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(build_dir)
            )

            duration = (datetime.now() - start_time).total_seconds()

            if result.returncode == 0:
                # Find build output
                dist_dir = build_dir / "dist"
                if not dist_dir.exists():
                    dist_dir = build_dir / "build"
                if not dist_dir.exists():
                    dist_dir = build_dir / ".next"

                if dist_dir.exists():
                    # Copy to builds directory
                    output_dir = self.builds_dir / phase / "web"
                    output_dir.mkdir(parents=True, exist_ok=True)

                    # Use robocopy on Windows, cp on others
                    if os.name == 'nt':
                        subprocess.run(
                            ["robocopy", str(dist_dir), str(output_dir), "/E", "/MIR"],
                            capture_output=True
                        )
                    else:
                        subprocess.run(
                            ["cp", "-r", str(dist_dir) + "/.", str(output_dir)],
                            capture_output=True
                        )

                    return BuildResult(
                        project=project_name,
                        phase=phase,
                        build_type="web",
                        success=True,
                        output_path=str(output_dir),
                        duration_seconds=duration
                    )
                else:
                    return BuildResult(
                        project=project_name,
                        phase=phase,
                        build_type="web",
                        success=False,
                        error="Build output directory not found",
                        duration_seconds=duration
                    )
            else:
                return BuildResult(
                    project=project_name,
                    phase=phase,
                    build_type="web",
                    success=False,
                    error=f"Build failed: {result.stderr}",
                    duration_seconds=duration
                )

        except subprocess.TimeoutExpired:
            return BuildResult(
                project=project_name,
                phase=phase,
                build_type="web",
                success=False,
                error="Build timed out after 2 minutes"
            )
        except Exception as e:
            return BuildResult(
                project=project_name,
                phase=phase,
                build_type="web",
                success=False,
                error=str(e)
            )

    def build_ios(self, phase: str) -> BuildResult:
        """Build iOS app."""
        start_time = datetime.now()
        project_name = self.project_dir.name

        try:
            # Check for iOS project
            ios_dir = self.project_dir / "apps" / "mobile" / "ios"
            if not ios_dir.exists():
                ios_dir = self.project_dir / "ios"
            if not ios_dir.exists():
                return BuildResult(
                    project=project_name,
                    phase=phase,
                    build_type="ios",
                    success=False,
                    error="No iOS project found"
                )

            # Build iOS app
            result = subprocess.run(
                ["xcodebuild", "-workspace", f"{project_name}.xcworkspace",
                 "-scheme", project_name, "-configuration", "Release",
                 "-derivedDataPath", "build"],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(ios_dir)
            )

            duration = (datetime.now() - start_time).total_seconds()

            if result.returncode == 0:
                # Find .app file
                app_path = None
                for app_file in (ios_dir / "build").rglob("*.app"):
                    app_path = app_file
                    break

                if app_path and app_path.exists():
                    output_dir = self.builds_dir / phase / "ios"
                    output_dir.mkdir(parents=True, exist_ok=True)

                    # Copy .app
                    import shutil
                    shutil.copytree(str(app_path), str(output_dir / app_path.name))

                    return BuildResult(
                        project=project_name,
                        phase=phase,
                        build_type="ios",
                        success=True,
                        output_path=str(output_dir / app_path.name),
                        duration_seconds=duration
                    )
                else:
                    return BuildResult(
                        project=project_name,
                        phase=phase,
                        build_type="ios",
                        success=False,
                        error="Build succeeded but .app not found",
                        duration_seconds=duration
                    )
            else:
                return BuildResult(
                    project=project_name,
                    phase=phase,
                    build_type="ios",
                    success=False,
                    error=f"Build failed: {result.stderr}",
                    duration_seconds=duration
                )

        except subprocess.TimeoutExpired:
            return BuildResult(
                project=project_name,
                phase=phase,
                build_type="ios",
                success=False,
                error="Build timed out after 10 minutes"
            )
        except Exception as e:
            return BuildResult(
                project=project_name,
                phase=phase,
                build_type="ios",
                success=False,
                error=str(e)
            )

    def build_android(self, phase: str) -> BuildResult:
        """Build Android app."""
        start_time = datetime.now()
        project_name = self.project_dir.name

        try:
            # Check for Android project
            android_dir = self.project_dir / "apps" / "mobile" / "android"
            if not android_dir.exists():
                android_dir = self.project_dir / "android"
            if not android_dir.exists():
                return BuildResult(
                    project=project_name,
                    phase=phase,
                    build_type="android",
                    success=False,
                    error="No Android project found"
                )

            # Build Android APK
            result = subprocess.run(
                ["./gradlew", "assembleRelease"],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(android_dir)
            )

            duration = (datetime.now() - start_time).total_seconds()

            if result.returncode == 0:
                # Find APK
                apk_path = None
                for apk in (android_dir / "app" / "build" / "outputs" / "apk").rglob("*.apk"):
                    apk_path = apk
                    break

                if apk_path and apk_path.exists():
                    output_dir = self.builds_dir / phase / "android"
                    output_dir.mkdir(parents=True, exist_ok=True)

                    import shutil
                    shutil.copy(str(apk_path), str(output_dir / apk_path.name))

                    return BuildResult(
                        project=project_name,
                        phase=phase,
                        build_type="android",
                        success=True,
                        output_path=str(output_dir / apk_path.name),
                        duration_seconds=duration
                    )
                else:
                    return BuildResult(
                        project=project_name,
                        phase=phase,
                        build_type="android",
                        success=False,
                        error="Build succeeded but APK not found",
                        duration_seconds=duration
                    )
            else:
                return BuildResult(
                    project=project_name,
                    phase=phase,
                    build_type="android",
                    success=False,
                    error=f"Build failed: {result.stderr}",
                    duration_seconds=duration
                )

        except subprocess.TimeoutExpired:
            return BuildResult(
                project=project_name,
                phase=phase,
                build_type="android",
                success=False,
                error="Build timed out after 10 minutes"
            )
        except Exception as e:
            return BuildResult(
                project=project_name,
                phase=phase,
                build_type="android",
                success=False,
                error=str(e)
            )

    def _save_manifest(self, phase: str, results: List[BuildResult]):
        """Save build manifest."""
        manifest_dir = self.builds_dir / phase
        manifest_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "project": self.project_dir.name,
            "phase": phase,
            "timestamp": datetime.now().isoformat(),
            "builds": []
        }

        for result in results:
            manifest["builds"].append({
                "type": result.build_type,
                "success": result.success,
                "output_path": result.output_path,
                "error": result.error,
                "duration_seconds": result.duration_seconds
            })

        manifest_path = manifest_dir / "build-manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        print(f"Build manifest saved: {manifest_path}")

    def get_build_info(self, phase: str) -> Optional[Dict[str, Any]]:
        """Get build info for a phase."""
        manifest_path = self.builds_dir / phase / "build-manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                return json.load(f)
        return None


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python build_utility.py <project_dir> <phase> [build_types...]")
        print("Example: python build_utility.py products/<project> 4a docker web")
        sys.exit(1)

    project_dir = sys.argv[1]
    phase = sys.argv[2]
    build_types = sys.argv[3:] if len(sys.argv) > 3 else ["docker", "web"]

    builder = BuildUtility(project_dir)
    results = builder.build_all(phase, build_types)

    print("\nBUILD RESULTS")
    print("=" * 50)
    for result in results:
        status = "✓" if result.success else "✗"
        print(f"  {status} {result.build_type}: {result.output_path or result.error}")
