"""
Product Deployer - Handles Docker and local deployment of products
"""

import os
import subprocess
import time
import json
import requests
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

class DeploymentMethod(Enum):
    DOCKER = "docker"
    LOCAL = "local"

class DeploymentStatus(Enum):
    NOT_DEPLOYED = "not_deployed"
    DEPLOYING = "deploying"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"

@dataclass
class DeploymentResult:
    success: bool
    method: str
    status: DeploymentStatus
    message: str
    url: Optional[str] = None
    container_id: Optional[str] = None
    process_id: Optional[int] = None

class ProductDeployer:
    """Handles product deployment for testing"""
    
    def __init__(self, project_config: Dict[str, Any]):
        self.config = project_config
        self.project_name = project_config.get("name", "unknown")
        self.project_path = Path(project_config.get("path", "."))
        self.deployment_config = project_config.get("deployment", {})
        self.method = DeploymentMethod(self.deployment_config.get("method", "local"))
        self.status = DeploymentStatus.NOT_DEPLOYED
        self.process_id = None
        self.container_id = None
        
    def is_running(self) -> bool:
        """Check if product is already running"""
        health_check = self.deployment_config.get("health_check")
        if not health_check:
            return False
        
        try:
            response = requests.get(health_check, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def deploy(self) -> DeploymentResult:
        """Deploy the product using configured method"""
        if self.is_running():
            self.status = DeploymentStatus.RUNNING
            return DeploymentResult(
                success=True,
                method=self.method.value,
                status=self.status,
                message="Product already running",
                url=self.deployment_config.get("health_check")
            )
        
        self.status = DeploymentStatus.DEPLOYING
        
        if self.method == DeploymentMethod.DOCKER:
            return self._deploy_docker()
        else:
            return self._deploy_local()
    
    def _deploy_docker(self) -> DeploymentResult:
        """Deploy using Docker"""
        try:
            # Check if Dockerfile exists
            dockerfile = self.project_path / "Dockerfile"
            if not dockerfile.exists():
                return DeploymentResult(
                    success=False,
                    method="docker",
                    status=DeploymentStatus.FAILED,
                    message="Dockerfile not found"
                )
            
            # Build Docker image
            image_name = f"{self.project_name}:latest"
            build_cmd = ["docker", "build", "-t", image_name, "."]
            result = subprocess.run(
                build_cmd,
                cwd=str(self.project_path),
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return DeploymentResult(
                    success=False,
                    method="docker",
                    status=DeploymentStatus.FAILED,
                    message=f"Docker build failed: {result.stderr}"
                )
            
            # Run Docker container
            run_cmd = [
                "docker", "run", "-d",
                "--name", f"{self.project_name}-test",
                "-p", "3000:3000",
                image_name
            ]
            result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return DeploymentResult(
                    success=False,
                    method="docker",
                    status=DeploymentStatus.FAILED,
                    message=f"Docker run failed: {result.stderr}"
                )
            
            self.container_id = result.stdout.strip()
            self.status = DeploymentStatus.RUNNING
            
            # Wait for health check
            if self._wait_for_health_check():
                return DeploymentResult(
                    success=True,
                    method="docker",
                    status=self.status,
                    message="Docker container started successfully",
                    url=self.deployment_config.get("health_check"),
                    container_id=self.container_id
                )
            else:
                return DeploymentResult(
                    success=False,
                    method="docker",
                    status=DeploymentStatus.FAILED,
                    message="Health check failed after Docker deployment"
                )
                
        except Exception as e:
            return DeploymentResult(
                success=False,
                method="docker",
                status=DeploymentStatus.FAILED,
                message=f"Docker deployment error: {str(e)}"
            )
    
    def _deploy_local(self) -> DeploymentResult:
        """Deploy locally using npm/pip/etc."""
        try:
            # Install dependencies
            install_cmd = self.deployment_config.get("install")
            if install_cmd:
                result = subprocess.run(
                    install_cmd.split(),
                    cwd=str(self.project_path),
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    return DeploymentResult(
                        success=False,
                        method="local",
                        status=DeploymentStatus.FAILED,
                        message=f"Installation failed: {result.stderr}"
                    )
            
            # Start the application
            start_cmd = self.deployment_config.get("start")
            if not start_cmd:
                return DeploymentResult(
                    success=False,
                    method="local",
                    status=DeploymentStatus.FAILED,
                    message="No start command configured"
                )
            
            # Start process in background
            process = subprocess.Popen(
                start_cmd.split(),
                cwd=str(self.project_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.process_id = process.pid
            self.status = DeploymentStatus.RUNNING
            
            # Wait for health check
            if self._wait_for_health_check():
                return DeploymentResult(
                    success=True,
                    method="local",
                    status=self.status,
                    message="Local deployment started successfully",
                    url=self.deployment_config.get("health_check"),
                    process_id=self.process_id
                )
            else:
                return DeploymentResult(
                    success=False,
                    method="local",
                    status=DeploymentStatus.FAILED,
                    message="Health check failed after local deployment"
                )
                
        except Exception as e:
            return DeploymentResult(
                success=False,
                method="local",
                status=DeploymentStatus.FAILED,
                message=f"Local deployment error: {str(e)}"
            )
    
    def _wait_for_health_check(self) -> bool:
        """Wait for product to pass health check"""
        health_check = self.deployment_config.get("health_check")
        if not health_check:
            return True
        
        timeout = self.deployment_config.get("health_check_timeout", 60)
        interval = self.deployment_config.get("health_check_interval", 5)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(health_check, timeout=5)
                if response.status_code == 200:
                    return True
            except:
                pass
            time.sleep(interval)
        
        return False
    
    def stop(self) -> bool:
        """Stop the deployed product"""
        try:
            if self.method == DeploymentMethod.DOCKER and self.container_id:
                subprocess.run(
                    ["docker", "stop", self.container_id],
                    capture_output=True
                )
                subprocess.run(
                    ["docker", "rm", self.container_id],
                    capture_output=True
                )
            elif self.method == DeploymentMethod.LOCAL and self.process_id:
                stop_cmd = self.deployment_config.get("stop")
                if stop_cmd:
                    subprocess.run(stop_cmd.split(), capture_output=True)
                else:
                    os.kill(self.process_id, 9)
            
            self.status = DeploymentStatus.STOPPED
            return True
        except:
            return False
    
    def uninstall(self) -> bool:
        """Uninstall the product (optional)"""
        if not self.deployment_config.get("auto_uninstall", False):
            return True
        
        try:
            if self.method == DeploymentMethod.DOCKER:
                subprocess.run(
                    ["docker", "rmi", f"{self.project_name}:latest"],
                    capture_output=True
                )
            elif self.method == DeploymentMethod.LOCAL:
                # Remove node_modules, .venv, etc.
                import shutil
                node_modules = self.project_path / "node_modules"
                if node_modules.exists():
                    shutil.rmtree(node_modules)
            
            self.status = DeploymentStatus.NOT_DEPLOYED
            return True
        except:
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current deployment status"""
        return {
            "project": self.project_name,
            "method": self.method.value,
            "status": self.status.value,
            "url": self.deployment_config.get("health_check"),
            "is_running": self.is_running(),
            "process_id": self.process_id,
            "container_id": self.container_id
        }
