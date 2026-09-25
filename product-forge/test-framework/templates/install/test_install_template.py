"""
Install/Uninstall Test Template
Reusable template for install, upgrade, and uninstall tests
"""

import pytest
import subprocess
import os
import shutil
from pathlib import Path

pytestmark = [pytest.mark.install, pytest.mark.{{feature_id}}]

class Test{{feature_name}}Install:
    """Install/uninstall tests for {{feature_name}}"""
    
    @pytest.fixture
    def project_path(self):
        return Path("../products/{{feature_id}}")
    
    @pytest.fixture
    def backup_path(self, project_path):
        backup = project_path.parent / f"{project_path.name}_backup"
        return backup
    
    def test_{{feature_id}}_install(self, project_path):
        """Test {{feature_id}} installation"""
        assert project_path.exists(), f"Project path does not exist: {project_path}"
        
        # Check for install script
        install_script = project_path / "install.sh"
        if install_script.exists():
            result = subprocess.run(
                ["bash", str(install_script)],
                capture_output=True,
                text=True
            )
            assert result.returncode == 0, f"Install failed: {result.stderr}"
    
    def test_{{feature_id}}_dependencies(self, project_path):
        """Test {{feature_id}} dependencies are installed"""
        # Check for package.json or requirements.txt
        package_json = project_path / "package.json"
        requirements_txt = project_path / "requirements.txt"
        
        if package_json.exists():
            node_modules = project_path / "node_modules"
            assert node_modules.exists(), "node_modules not found - run npm install"
        
        if requirements_txt.exists():
            venv = project_path / "venv" or project_path / ".venv"
            # Check if virtual environment exists
            assert venv.exists() or (project_path / "site-packages").exists(), \
                "Virtual environment not found"
    
    def test_{{feature_id}}_start_stop(self, project_path):
        """Test {{feature_id}} start and stop"""
        # This is a placeholder - actual implementation depends on product
        pass
    
    def test_{{feature_id}}_upgrade(self, project_path, backup_path):
        """Test {{feature_id}} upgrade process"""
        # Backup current installation
        if project_path.exists():
            shutil.copytree(project_path, backup_path)
        
        try:
            # Simulate upgrade
            # This would be product-specific
            pass
        finally:
            # Restore backup
            if backup_path.exists():
                shutil.rmtree(project_path)
                shutil.move(backup_path, project_path)
    
    def test_{{feature_id}}_uninstall(self, project_path):
        """Test {{feature_id}} uninstall"""
        # Check for uninstall script
        uninstall_script = project_path / "uninstall.sh"
        if uninstall_script.exists():
            result = subprocess.run(
                ["bash", str(uninstall_script)],
                capture_output=True,
                text=True
            )
            assert result.returncode == 0, f"Uninstall failed: {result.stderr}"
    
    def test_{{feature_id}}_cleanup(self, project_path):
        """Test {{feature_id}} cleanup after uninstall"""
        # Check that temporary files are removed
        temp_dirs = [".cache", "tmp", ".tmp"]
        for temp_dir in temp_dirs:
            temp_path = project_path / temp_dir
            if temp_path.exists():
                # This is informational - not all products clean up
                print(f"Temp directory still exists: {temp_dir}")
