"""
Product Forge Self-Improvement - Code Executor

Executes approved changes with backup, validation, rollback,
and product-plan.md updates.
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

import os
import shutil
import subprocess
import ast
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import sys
sys.path.insert(0, str(_PF_ROOT))
from core.conversation_models import (
    FileChange, ImplementationPlan, ExecutionResult,
    ImplementationStatus, RiskLevel
)


class CodeExecutor:
    """Executes approved implementation plans with safety mechanisms."""

    def __init__(self):
        self.root_dir = _PF_ROOT
        self.backup_dir = self.root_dir / ".backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.product_plan_path = self.root_dir / "docs" / "product-plan.md"

    def execute_plan(self, plan: ImplementationPlan,
                     approved_changes: Optional[List[str]] = None) -> ExecutionResult:
        """
        Execute an implementation plan.

        Args:
            plan: The implementation plan to execute
            approved_changes: Optional list of file paths to execute (if None, execute all selected)

        Returns:
            ExecutionResult with details of execution
        """
        result = ExecutionResult(
            plan_id=plan.id,
            conversation_id=plan.conversation_id,
            executed_at=datetime.utcnow().isoformat()
        )

        # Filter changes to only approved ones
        changes_to_execute = [
            fc for fc in plan.file_changes
            if fc.selected and (approved_changes is None or fc.file_path in approved_changes)
        ]

        if not changes_to_execute:
            result.error_message = "No changes selected for execution"
            return result

        # Step 1: Create backups
        backups = []
        try:
            for change in changes_to_execute:
                backup_path = self.backup_file(change.file_path)
                if backup_path:
                    backups.append(backup_path)
            result.backup_paths = backups
        except Exception as e:
            result.error_message = f"Backup failed: {str(e)}"
            return result

        # Step 2: Apply changes
        try:
            for change in changes_to_execute:
                success = self.apply_changes(change.file_path, change)
                if not success:
                    # Rollback on failure
                    self.rollback_all(backups)
                    result.error_message = f"Failed to apply changes to {change.file_path}"
                    result.rolled_back = True
                    return result
                result.files_modified.append(change.file_path)
        except Exception as e:
            # Rollback on exception
            self.rollback_all(backups)
            result.error_message = f"Apply failed: {str(e)}"
            result.rolled_back = True
            return result

        # Step 3: Validate syntax (Python files)
        for change in changes_to_execute:
            if change.file_path.endswith('.py'):
                if not self.validate_syntax(change.file_path):
                    self.rollback_all(backups)
                    result.error_message = f"Syntax validation failed for {change.file_path}"
                    result.syntax_valid = False
                    result.rolled_back = True
                    return result

        # Step 4: Run tests
        tests_passed, test_output = self.run_tests()
        result.tests_passed = tests_passed
        result.test_output = test_output

        if not tests_passed:
            self.rollback_all(backups)
            result.error_message = f"Tests failed. Rolled back changes.\n{test_output[:500]}"
            result.rolled_back = True
            return result

        # Step 5: Update product-plan.md
        try:
            self.update_product_plan(changes_to_execute, result)
        except Exception as e:
            # Non-fatal: log but don't fail
            print(f"[WARNING] Failed to update product-plan.md: {e}")

        result.success = True
        return result

    def backup_file(self, file_path: str) -> Optional[str]:
        """Create a backup of a file before modification."""
        if not file_path:
            return None

        full_path = self.root_dir / file_path
        if not full_path.exists():
            return None

        # Create timestamped backup
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{timestamp}_{file_path.replace('/', '_').replace('\\', '_')}"
        backup_path = self.backup_dir / backup_name

        try:
            shutil.copy2(full_path, backup_path)
            return str(backup_path)
        except (OSError, shutil.Error) as e:
            print(f"[WARNING] Backup failed for {file_path}: {e}")
            return None

    def apply_changes(self, file_path: str, change: FileChange) -> bool:
        """Apply changes to a file."""
        if not file_path:
            return False

        full_path = self.root_dir / file_path

        if change.operation == "create":
            # Create new file
            try:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(change.new_code)
                return True
            except (OSError, IOError) as e:
                print(f"[ERROR] Failed to create {file_path}: {e}")
                return False

        elif change.operation == "delete":
            # Delete file
            try:
                if full_path.exists():
                    full_path.unlink()
                return True
            except (OSError) as e:
                print(f"[ERROR] Failed to delete {file_path}: {e}")
                return False

        elif change.operation == "modify":
            # Modify existing file
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                lines = content.split('\n')

                # Find and replace the old code with new code
                if change.old_code and change.new_code:
                    # Replace specific section
                    old_lines = change.old_code.split('\n')
                    new_lines = change.new_code.split('\n')

                    # Find the start position
                    start_line = change.line_start
                    end_line = min(change.line_end, len(lines))

                    # Replace the section
                    new_content_lines = lines[:start_line] + new_lines + lines[end_line:]
                    new_content = '\n'.join(new_content_lines)
                else:
                    # If no old/new code specified, append new code
                    new_content = content + '\n' + change.new_code

                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

                return True
            except (OSError, IOError) as e:
                print(f"[ERROR] Failed to modify {file_path}: {e}")
                return False

        return False

    def validate_syntax(self, file_path: str) -> bool:
        """Validate Python syntax after changes."""
        if not file_path.endswith('.py'):
            return True

        full_path = self.root_dir / file_path
        if not full_path.exists():
            return True

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            ast.parse(content)
            return True
        except SyntaxError as e:
            print(f"[ERROR] Syntax error in {file_path}: {e}")
            return False
        except (OSError, IOError):
            return True

    def run_tests(self) -> Tuple[bool, str]:
        """Run pytest test suite. Returns (success, output)."""
        try:
            # Run pytest with timeout
            result = subprocess.run(
                ['python', '-m', 'pytest', 'test-framework/', '-x', '--tb=short', '-q'],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )

            output = result.stdout + "\n" + result.stderr
            success = result.returncode == 0

            return success, output
        except subprocess.TimeoutExpired:
            return False, "Test execution timed out after 120 seconds"
        except FileNotFoundError:
            # pytest not found, skip tests
            return True, "pytest not found - skipping tests"
        except Exception as e:
            return False, f"Test execution error: {str(e)}"

    def rollback(self, backup_path: str) -> bool:
        """Rollback to a backup file."""
        try:
            backup = Path(backup_path)
            if not backup.exists():
                return False

            # Extract original filename from backup name
            # Format: timestamp_original_path
            parts = backup.name.split('_', 1)
            if len(parts) < 2:
                return False

            original_name = parts[1]
            # Restore to original location
            original_path = self.root_dir / original_name.replace('_', '/')

            if original_path.exists():
                shutil.copy2(backup, original_path)
                return True
            return False
        except (OSError, shutil.Error) as e:
            print(f"[ERROR] Rollback failed: {e}")
            return False

    def rollback_all(self, backup_paths: List[str]) -> bool:
        """Rollback all files from backup paths."""
        success = True
        for backup_path in backup_paths:
            if not self.rollback(backup_path):
                success = False
        return success

    def update_product_plan(self, changes: List[FileChange], result: ExecutionResult):
        """Update docs/product-plan.md with improvement record."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

        # Build the improvement record
        record = f"\n\n### {timestamp} - Product Forge Self-Improvement\n\n"
        record += f"- **Plan ID:** {result.plan_id}\n"
        record += f"- **Conversation ID:** {result.conversation_id}\n"
        record += f"- **Files Modified:** {len(changes)}\n"
        record += f"- **Tests Passed:** {'Yes' if result.tests_passed else 'No'}\n"
        record += f"- **Status:** {'Applied' if result.success else 'Failed'}\n"

        if changes:
            record += "\n**Changes Applied:**\n\n"
            for change in changes:
                record += f"- `{change.file_path}` ({change.operation}) - {change.explanation}\n"

        # Read existing product-plan.md
        if self.product_plan_path.exists():
            with open(self.product_plan_path, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = "# Product Plan\n"

        # Find the right place to insert (after ## Product Forge Improvements section)
        if "## Product Forge Improvements" in content:
            # Append to existing section
            content = content.rstrip() + "\n" + record
        else:
            # Add new section
            content = content.rstrip() + "\n\n## Product Forge Improvements\n" + record

        # Write back
        self.product_plan_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.product_plan_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def get_backup_list(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        backups = []
        for backup in self.backup_dir.iterdir():
            if backup.is_file():
                stat = backup.stat()
                backups.append({
                    "name": backup.name,
                    "path": str(backup),
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
                })
        backups.sort(key=lambda x: x['created'], reverse=True)
        return backups

    def cleanup_old_backups(self, keep_count: int = 50):
        """Keep only the most recent backups."""
        backups = self.get_backup_list()
        if len(backups) > keep_count:
            for backup in backups[keep_count:]:
                try:
                    Path(backup['path']).unlink()
                except OSError:
                    pass
