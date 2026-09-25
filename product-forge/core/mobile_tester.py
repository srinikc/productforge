"""
Mobile Tester — Simulator management and mobile test execution.

Handles:
- Detecting iOS Simulator / Android Emulator availability
- Booting simulators/emulators
- Building and installing React Native apps
- Running mobile tests (stowaway, vitest-mobile)
- Collecting test results
"""

try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class Platform(Enum):
    IOS = "ios"
    ANDROID = "android"


class TestFramework(Enum):
    STOWAWAY = "stowaway"
    VITEST_MOBILE = "vitest-mobile"
    MAESTRO = "maestro"


@dataclass
class SimulatorStatus:
    platform: Platform
    available: bool
    booted: bool
    name: str = ""
    udid: str = ""
    api_level: str = ""
    error: str = ""


@dataclass
class MobileTestResult:
    platform: Platform
    framework: TestFramework
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    duration_seconds: float = 0
    error: str = ""
    details: list = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class MobileTester:
    """Manages mobile simulators and runs tests."""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.test_framework_dir = self.project_dir.parent.parent / "test-framework"
        self.results_dir = self.test_framework_dir / "results" / "mobile"

    def check_platform_availability(self, platform: Platform) -> SimulatorStatus:
        """Check if a platform's simulator/emulator is available."""
        if platform == Platform.IOS:
            return self._check_ios()
        else:
            return self._check_android()

    def _check_ios(self) -> SimulatorStatus:
        """Check iOS Simulator availability."""
        try:
            result = subprocess.run(
                ["xcrun", "simctl", "list", "devices", "available"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return SimulatorStatus(
                    platform=Platform.IOS,
                    available=False, booted=False,
                    error=f"xcrun simctl not available: {result.stderr}"
                )

            # Parse available simulators
            lines = result.stdout.strip().split("\n")
            simulators = []
            for line in lines:
                if "iPhone" in line or "iPad" in line:
                    simulators.append(line.strip())

            if not simulators:
                return SimulatorStatus(
                    platform=Platform.IOS,
                    available=False, booted=False,
                    error="No iOS simulators found. Install Xcode."
                )

            # Check if any are booted
            booted_result = subprocess.run(
                ["xcrun", "simctl", "list", "devices", "booted"],
                capture_output=True, text=True, timeout=30
            )
            booted = "Booted" in booted_result.stdout

            return SimulatorStatus(
                platform=Platform.IOS,
                available=True,
                booted=booted,
                name=simulators[0] if simulators else ""
            )
        except FileNotFoundError:
            return SimulatorStatus(
                platform=Platform.IOS,
                available=False, booted=False,
                error="Xcode not installed"
            )
        except subprocess.TimeoutExpired:
            return SimulatorStatus(
                platform=Platform.IOS,
                available=False, booted=False,
                error="Timeout checking iOS simulator"
            )

    def _check_android(self) -> SimulatorStatus:
        """Check Android Emulator availability."""
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return SimulatorStatus(
                    platform=Platform.ANDROID,
                    available=False, booted=False,
                    error=f"adb not available: {result.stderr}"
                )

            # Check for emulators
            lines = result.stdout.strip().split("\n")
            devices = [l for l in lines[1:] if l.strip() and "offline" not in l]

            # Check for emulator specifically
            emulators = [d for d in devices if "emulator" in d]

            # Also check avdmanager for available AVDs
            avd_result = subprocess.run(
                ["avdmanager", "list", "avd"],
                capture_output=True, text=True, timeout=30
            )
            avds = []
            if avd_result.returncode == 0:
                for line in avd_result.stdout.split("\n"):
                    if "Name:" in line:
                        avds.append(line.split("Name:")[1].strip())

            if not avds and not emulators:
                return SimulatorStatus(
                    platform=Platform.ANDROID,
                    available=False, booted=False,
                    error="No Android emulators found. Install Android SDK."
                )

            booted = len(emulators) > 0
            return SimulatorStatus(
                platform=Platform.ANDROID,
                available=True,
                booted=booted,
                name=avds[0] if avds else "emulator"
            )
        except FileNotFoundError:
            return SimulatorStatus(
                platform=Platform.ANDROID,
                available=False, booted=False,
                error="Android SDK not installed"
            )
        except subprocess.TimeoutExpired:
            return SimulatorStatus(
                platform=Platform.ANDROID,
                available=False, booted=False,
                error="Timeout checking Android emulator"
            )

    def boot_simulator(self, platform: Platform, device_name: str = "") -> bool:
        """Boot a simulator/emulator."""
        if platform == Platform.IOS:
            return self._boot_ios(device_name)
        else:
            return self._boot_android(device_name)

    def _boot_ios(self, device_name: str) -> bool:
        """Boot iOS Simulator."""
        try:
            if not device_name:
                # Find first available iPhone
                result = subprocess.run(
                    ["xcrun", "simctl", "list", "devices", "available"],
                    capture_output=True, text=True, timeout=30
                )
                for line in result.stdout.split("\n"):
                    if "iPhone" in line and "unavailable" not in line.lower():
                        # Extract device name
                        device_name = line.split("(")[0].strip()
                        break

            if not device_name:
                print("No iOS device found to boot")
                return False

            # Boot the device
            result = subprocess.run(
                ["xcrun", "simctl", "boot", device_name],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                print(f"Booted iOS simulator: {device_name}")
                return True
            else:
                print(f"Failed to boot iOS simulator: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error booting iOS simulator: {e}")
            return False

    def _boot_android(self, avd_name: str) -> bool:
        """Boot Android Emulator."""
        try:
            if not avd_name:
                avd_name = "Pixel_7_API_34"  # Default AVD

            # Start emulator in background
            subprocess.Popen(
                ["emulator", "-avd", avd_name, "-no-window", "-no-audio"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"Starting Android emulator: {avd_name}")
            print("Waiting for emulator to boot...")
            import time
            time.sleep(30)  # Wait for boot

            # Verify it's running
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True, text=True, timeout=30
            )
            if "emulator" in result.stdout:
                print(f"Android emulator booted: {avd_name}")
                return True
            else:
                print("Android emulator failed to boot")
                return False
        except Exception as e:
            print(f"Error booting Android emulator: {e}")
            return False

    def install_app(self, platform: Platform, app_path: str) -> bool:
        """Install app on simulator/emulator."""
        if platform == Platform.IOS:
            return self._install_ios(app_path)
        else:
            return self._install_android(app_path)

    def _install_ios(self, app_path: str) -> bool:
        """Install .app on iOS Simulator."""
        try:
            result = subprocess.run(
                ["xcrun", "simctl", "install", "booted", app_path],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                print(f"Installed iOS app: {app_path}")
                return True
            else:
                print(f"Failed to install iOS app: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error installing iOS app: {e}")
            return False

    def _install_android(self, apk_path: str) -> bool:
        """Install .apk on Android Emulator."""
        try:
            result = subprocess.run(
                ["adb", "install", "-r", apk_path],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                print(f"Installed Android app: {apk_path}")
                return True
            else:
                print(f"Failed to install Android app: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error installing Android app: {e}")
            return False

    def launch_app(self, platform: Platform, bundle_id: str) -> bool:
        """Launch app on simulator/emulator."""
        if platform == Platform.IOS:
            return self._launch_ios(bundle_id)
        else:
            return self._launch_android(bundle_id)

    def _launch_ios(self, bundle_id: str) -> bool:
        """Launch app on iOS Simulator."""
        try:
            result = subprocess.run(
                ["xcrun", "simctl", "launch", "booted", bundle_id],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                print(f"Launched iOS app: {bundle_id}")
                return True
            else:
                print(f"Failed to launch iOS app: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error launching iOS app: {e}")
            return False

    def _launch_android(self, package_name: str) -> bool:
        """Launch app on Android Emulator."""
        try:
            # Get launch activity
            result = subprocess.run(
                ["adb", "shell", "cmd", "package", "resolve-activity",
                 "--brief", "-a", "android.intent.action.MAIN",
                 "-c", "android.intent.category.LAUNCHER", package_name],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                activity = result.stdout.strip().split("\n")[-1]
                subprocess.run(
                    ["adb", "shell", "am", "start", "-n", activity],
                    capture_output=True, text=True, timeout=30
                )
                print(f"Launched Android app: {package_name}")
                return True
            else:
                print(f"Failed to launch Android app: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error launching Android app: {e}")
            return False

    def run_tests(
        self,
        platform: Platform,
        framework: TestFramework = TestFramework.VITEST_MOBILE,
        test_dir: str = ""
    ) -> MobileTestResult:
        """Run mobile tests on simulator/emulator."""
        start_time = datetime.now()

        if framework == TestFramework.VITEST_MOBILE:
            return self._run_vitest_mobile(platform, test_dir, start_time)
        elif framework == TestFramework.STOWAWAY:
            return self._run_stowaway(platform, test_dir, start_time)
        elif framework == TestFramework.MAESTRO:
            return self._run_maestro(platform, test_dir, start_time)
        else:
            return MobileTestResult(
                platform=platform,
                framework=framework,
                error=f"Unknown framework: {framework}"
            )

    def _run_vitest_mobile(
        self, platform: Platform, test_dir: str, start_time: datetime
    ) -> MobileTestResult:
        """Run vitest-mobile tests."""
        try:
            # Check if vitest-mobile is installed
            check = subprocess.run(
                ["npx", "vitest-mobile", "--version"],
                capture_output=True, text=True, timeout=30
            )
            if check.returncode != 0:
                return MobileTestResult(
                    platform=platform,
                    framework=TestFramework.VITEST_MOBILE,
                    error="vitest-mobile not installed. Run: npm install vitest-mobile"
                )

            # Bootstrap if needed
            bootstrap = subprocess.run(
                ["npx", "vitest-mobile", "bootstrap", "--platform", platform.value],
                capture_output=True, text=True, timeout=300,
                cwd=str(self.project_dir)
            )
            if bootstrap.returncode != 0:
                return MobileTestResult(
                    platform=platform,
                    framework=TestFramework.VITEST_MOBILE,
                    error=f"Bootstrap failed: {bootstrap.stderr}"
                )

            # Run tests
            result = subprocess.run(
                ["npx", "vitest", "run", "--project", platform.value],
                capture_output=True, text=True, timeout=600,
                cwd=str(self.project_dir)
            )

            duration = (datetime.now() - start_time).total_seconds()

            # Parse results
            tests_run = result.stdout.count("✓") + result.stdout.count("✗")
            tests_passed = result.stdout.count("✓")
            tests_failed = result.stdout.count("✗")

            return MobileTestResult(
                platform=platform,
                framework=TestFramework.VITEST_MOBILE,
                tests_run=tests_run,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                duration_seconds=duration,
                details=[result.stdout] if result.stdout else []
            )
        except subprocess.TimeoutExpired:
            return MobileTestResult(
                platform=platform,
                framework=TestFramework.VITEST_MOBILE,
                error="Tests timed out after 10 minutes"
            )
        except Exception as e:
            return MobileTestResult(
                platform=platform,
                framework=TestFramework.VITEST_MOBILE,
                error=str(e)
            )

    def _run_stowaway(
        self, platform: Platform, test_dir: str, start_time: datetime
    ) -> MobileTestResult:
        """Run stowaway tests."""
        try:
            # Check if stowaway is installed
            check = subprocess.run(
                ["npx", "stowaway", "--version"],
                capture_output=True, text=True, timeout=30
            )
            if check.returncode != 0:
                return MobileTestResult(
                    platform=platform,
                    framework=TestFramework.STOWAWAY,
                    error="stowaway not installed. Run: npm install stowaway"
                )

            # Run tests
            result = subprocess.run(
                ["npx", "stowaway", "run", "--platform", platform.value],
                capture_output=True, text=True, timeout=600,
                cwd=str(self.project_dir)
            )

            duration = (datetime.now() - start_time).total_seconds()

            # Parse results
            tests_run = result.stdout.count("✓") + result.stdout.count("✗")
            tests_passed = result.stdout.count("✓")
            tests_failed = result.stdout.count("✗")

            return MobileTestResult(
                platform=platform,
                framework=TestFramework.STOWAWAY,
                tests_run=tests_run,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                duration_seconds=duration,
                details=[result.stdout] if result.stdout else []
            )
        except subprocess.TimeoutExpired:
            return MobileTestResult(
                platform=platform,
                framework=TestFramework.STOWAWAY,
                error="Tests timed out after 10 minutes"
            )
        except Exception as e:
            return MobileTestResult(
                platform=platform,
                framework=TestFramework.STOWAWAY,
                error=str(e)
            )

    def _run_maestro(
        self, platform: Platform, test_dir: str, start_time: datetime
    ) -> MobileTestResult:
        """Run Maestro tests."""
        try:
            # Check if maestro is installed
            check = subprocess.run(
                ["maestro", "--version"],
                capture_output=True, text=True, timeout=30
            )
            if check.returncode != 0:
                return MobileTestResult(
                    platform=platform,
                    framework=TestFramework.MAESTRO,
                    error="Maestro not installed. Install from: https://maestro.mobile.dev"
                )

            # Run tests
            result = subprocess.run(
                ["maestro", "test", test_dir or "."],
                capture_output=True, text=True, timeout=600,
                cwd=str(self.project_dir)
            )

            duration = (datetime.now() - start_time).total_seconds()

            # Parse results
            tests_run = result.stdout.count("✓") + result.stdout.count("✗")
            tests_passed = result.stdout.count("✓")
            tests_failed = result.stdout.count("✗")

            return MobileTestResult(
                platform=platform,
                framework=TestFramework.MAESTRO,
                tests_run=tests_run,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                duration_seconds=duration,
                details=[result.stdout] if result.stdout else []
            )
        except subprocess.TimeoutExpired:
            return MobileTestResult(
                platform=platform,
                framework=TestFramework.MAESTRO,
                error="Tests timed out after 10 minutes"
            )
        except Exception as e:
            return MobileTestResult(
                platform=platform,
                framework=TestFramework.MAESTRO,
                error=str(e)
            )

    def save_result(self, result: MobileTestResult, phase: str = ""):
        """Save test result to both local results and test framework."""
        self.results_dir.mkdir(parents=True, exist_ok=True)

        filename = f"mobile_{result.platform.value}_{result.framework.value}"
        if phase:
            filename += f"_{phase}"
        filename += ".json"

        filepath = self.results_dir / filename

        result_data = {
            "platform": result.platform.value,
            "framework": result.framework.value,
            "tests_run": result.tests_run,
            "tests_passed": result.tests_passed,
            "tests_failed": result.tests_failed,
            "duration_seconds": result.duration_seconds,
            "error": result.error,
            "details": result.details,
            "timestamp": result.timestamp,
            "phase": phase
        }

        with open(filepath, "w") as f:
            json.dump(result_data, f, indent=2)

        print(f"Saved mobile test result: {filepath}")

        # Also save to test framework
        self._save_to_test_framework(result_data, phase)

    def _save_to_test_framework(self, result_data: dict, phase: str):
        """Save mobile test results to the test framework."""
        try:
            # Determine project name from directory
            project_name = self.project_dir.name

            # Create test framework mobile results directory
            tf_mobile_dir = self.test_framework_dir / "results" / "mobile" / project_name
            tf_mobile_dir.mkdir(parents=True, exist_ok=True)

            # Save detailed result
            filename = f"mobile_{result_data['platform']}_{result_data['framework']}"
            if phase:
                filename += f"_{phase}"
            filename += ".json"

            tf_filepath = tf_mobile_dir / filename
            with open(tf_filepath, "w") as f:
                json.dump(result_data, f, indent=2)

            # Update test cycle summary
            self._update_test_cycle(project_name, result_data, phase)

            print(f"Saved to test framework: {tf_filepath}")
        except Exception as e:
            print(f"Warning: Could not save to test framework: {e}")

    def _update_test_cycle(self, project: str, result_data: dict, phase: str):
        """Update test cycle summary in test framework."""
        cycle_file = self.test_framework_dir / "results" / "mobile" / project / "test-cycle.json"

        # Load existing cycle or create new
        if cycle_file.exists():
            with open(cycle_file) as f:
                cycle = json.load(f)
        else:
            cycle = {
                "project": project,
                "test_cycles": [],
                "summary": {
                    "ios": {"total": 0, "passed": 0, "failed": 0},
                    "android": {"total": 0, "passed": 0, "failed": 0}
                }
            }

        # Find or create cycle for this phase
        phase_cycle = None
        for c in cycle["test_cycles"]:
            if c.get("phase") == phase:
                phase_cycle = c
                break

        if not phase_cycle:
            phase_cycle = {
                "phase": phase,
                "started_at": result_data["timestamp"],
                "ios": {"tests_run": 0, "tests_passed": 0, "tests_failed": 0, "frameworks": []},
                "android": {"tests_run": 0, "tests_passed": 0, "tests_failed": 0, "frameworks": []}
            }
            cycle["test_cycles"].append(phase_cycle)

        # Update phase cycle
        platform = result_data["platform"]
        if platform in phase_cycle:
            phase_cycle[platform]["tests_run"] += result_data["tests_run"]
            phase_cycle[platform]["tests_passed"] += result_data["tests_passed"]
            phase_cycle[platform]["tests_failed"] += result_data["tests_failed"]

            # Add framework entry if not exists
            framework = result_data["framework"]
            if framework not in phase_cycle[platform]["frameworks"]:
                phase_cycle[platform]["frameworks"].append(framework)

        phase_cycle["completed_at"] = result_data["timestamp"]

        # Update summary
        if platform in cycle["summary"]:
            cycle["summary"][platform]["total"] += result_data["tests_run"]
            cycle["summary"][platform]["passed"] += result_data["tests_passed"]
            cycle["summary"][platform]["failed"] += result_data["tests_failed"]

        # Save updated cycle
        with open(cycle_file, "w") as f:
            json.dump(cycle, f, indent=2)

    def get_results_summary(self) -> dict:
        """Get summary of all mobile test results."""
        summary = {
            "ios": {"total": 0, "passed": 0, "failed": 0},
            "android": {"total": 0, "passed": 0, "failed": 0}
        }

        if not self.results_dir.exists():
            return summary

        for result_file in self.results_dir.glob("*.json"):
            with open(result_file) as f:
                data = json.load(f)

            platform = data.get("platform", "")
            if platform in summary:
                summary[platform]["total"] += data.get("tests_run", 0)
                summary[platform]["passed"] += data.get("tests_passed", 0)
                summary[platform]["failed"] += data.get("tests_failed", 0)

        return summary


def get_mobile_tester(project: str = None) -> Optional[MobileTester]:
    """Get a MobileTester instance for a project."""
    try:
        from pipeline_helpers import resolve_project
        project_name = resolve_project(project)
        if not project_name:
            return None

        products_dir = _PF_ROOT / "products"
        project_dir = products_dir / project_name
        return MobileTester(str(project_dir))
    except ImportError:
        return None


if __name__ == "__main__":
    # CLI interface
    if len(sys.argv) < 2:
        print("Usage: python mobile_tester.py <command> [args]")
        print("Commands:")
        print("  check [ios|android]         Check platform availability")
        print("  boot [ios|android]          Boot simulator/emulator")
        print("  test [ios|android]          Run mobile tests")
        print("  summary                     Show test results summary")
        sys.exit(1)

    command = sys.argv[1]
    platform_str = sys.argv[2] if len(sys.argv) > 2 else "ios"
    platform = Platform.IOS if platform_str == "ios" else Platform.ANDROID

    tester = get_mobile_tester()
    if not tester:
        print("No project found")
        sys.exit(1)

    if command == "check":
        status = tester.check_platform_availability(platform)
        print(f"\n{platform.value.upper()} STATUS")
        print(f"Available: {status.available}")
        print(f"Booted: {status.booted}")
        if status.name:
            print(f"Device: {status.name}")
        if status.error:
            print(f"Error: {status.error}")

    elif command == "boot":
        success = tester.boot_simulator(platform)
        print(f"\nBoot {'successful' if success else 'failed'}")

    elif command == "test":
        result = tester.run_tests(platform)
        print(f"\n{platform.value.upper()} TEST RESULTS")
        print(f"Run: {result.tests_run}")
        print(f"Passed: {result.tests_passed}")
        print(f"Failed: {result.tests_failed}")
        if result.error:
            print(f"Error: {result.error}")

    elif command == "summary":
        summary = tester.get_results_summary()
        print("\nMOBILE TEST SUMMARY")
        for platform, stats in summary.items():
            print(f"\n{platform.upper()}:")
            print(f"  Total: {stats['total']}")
            print(f"  Passed: {stats['passed']}")
            print(f"  Failed: {stats['failed']}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
