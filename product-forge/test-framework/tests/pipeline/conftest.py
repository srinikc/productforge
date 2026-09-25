"""
Pipeline Test Configuration
Fixtures for multi-agent, multi-project pipeline tests
"""

import pytest
import json
import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime


@pytest.fixture
def temp_products_dir():
    """Create temporary products directory for testing"""
    temp_dir = tempfile.mkdtemp()
    products_dir = Path(temp_dir) / "products"
    products_dir.mkdir()
    
    # Create index.json
    index_path = products_dir / "index.json"
    with open(index_path, 'w') as f:
        json.dump({"products": []}, f)
    
    yield products_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_project(temp_products_dir):
    """Create a sample project for testing"""
    project_name = "test-project"
    project_dir = temp_products_dir / project_name
    project_dir.mkdir()
    
    # Create subdirectories
    for subdir in ["docs", "reports", "checkpoints", "dlq", "selective_runs", "security"]:
        (project_dir / subdir).mkdir(exist_ok=True)
    
    # Create pipeline.json
    pipeline_config = {
        "current_stage": 0,
        "model_tier": "recommended",
        "quality_tier": "standard",
        "product_type": "prototype",
        "product_domain": "general",
        "agents": {},
        "stages": {},
        "circuit_breakers": {},
        "fallback_chains": {},
        "git": {
            "auto_commit": True,
            "branch_prefix": "pipeline/",
            "commit_format": "conventional"
        },
        "created_at": datetime.now().isoformat(),
        "last_activity": datetime.now().isoformat()
    }
    
    with open(project_dir / "pipeline.json", 'w') as f:
        json.dump(pipeline_config, f, indent=2)
    
    # Create project-config.json
    project_config = {
        "product_type": "prototype",
        "product_domain": "general",
        "quality_tier": "standard",
        "tech_stack": {
            "language": "python",
            "framework": "fastapi"
        }
    }
    
    with open(project_dir / "project-config.json", 'w') as f:
        json.dump(project_config, f, indent=2)
    
    # Update index
    index_path = temp_products_dir / "index.json"
    with open(index_path, 'r') as f:
        index = json.load(f)
    index["products"].append(project_name)
    with open(index_path, 'w') as f:
        json.dump(index, f, indent=2)
    
    return project_name


@pytest.fixture
def multiple_projects(temp_products_dir):
    """Create multiple projects for concurrent testing"""
    projects = ["project-alpha", "project-beta", "project-gamma"]
    
    for project_name in projects:
        project_dir = temp_products_dir / project_name
        project_dir.mkdir()
        
        # Create subdirectories
        for subdir in ["docs", "reports", "checkpoints", "dlq", "selective_runs", "security"]:
            (project_dir / subdir).mkdir(exist_ok=True)
        
        # Create pipeline.json
        pipeline_config = {
            "current_stage": 0,
            "model_tier": "recommended",
            "quality_tier": "standard",
            "product_type": "prototype",
            "product_domain": "general",
            "agents": {},
            "stages": {},
            "circuit_breakers": {},
            "fallback_chains": {},
            "git": {
                "auto_commit": True,
                "branch_prefix": "pipeline/",
                "commit_format": "conventional"
            },
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat()
        }
        
        with open(project_dir / "pipeline.json", 'w') as f:
            json.dump(pipeline_config, f, indent=2)
    
    # Update index
    index_path = temp_products_dir / "index.json"
    with open(index_path, 'r') as f:
        index = json.load(f)
    index["products"] = projects
    with open(index_path, 'w') as f:
        json.dump(index, f, indent=2)
    
    return projects


@pytest.fixture
def security_config_dir():
    """Create temporary security config directory"""
    temp_dir = tempfile.mkdtemp()
    security_dir = Path(temp_dir) / "security"
    security_dir.mkdir()
    
    # Create config directory
    config_dir = security_dir / "config"
    config_dir.mkdir()
    
    # Create tools.yaml
    tools_config = {
        "tools": {
            "bandit": {
                "version": "1.9.4",
                "install_command": "pip install bandit==1.9.4",
                "purpose": "Python security linter",
                "languages": ["python"],
                "owasp_mapping": ["A05", "A04", "A10"],
                "auto_install": True,
                "enabled": True
            },
            "trivy": {
                "version": "0.71.2",
                "install_command": "choco install trivy",
                "purpose": "Dependency + Container + IaC scanning",
                "languages": ["*"],
                "owasp_mapping": ["A02", "A03", "A08"],
                "auto_install": True,
                "enabled": True
            }
        }
    }
    
    with open(config_dir / "tools.yaml", 'w') as f:
        import yaml
        yaml.dump(tools_config, f)
    
    # Create compliance.yaml
    compliance_config = {
        "domains": {
            "finance": {
                "regulations": [
                    {"name": "PCI-DSS", "requirements": ["encryption", "access_control", "logging"]},
                    {"name": "SOX", "requirements": ["audit_trail", "data_integrity"]}
                ]
            },
            "healthcare": {
                "regulations": [
                    {"name": "HIPAA", "requirements": ["encryption", "access_control", "audit_trail"]}
                ]
            },
            "ecommerce": {
                "regulations": [
                    {"name": "GDPR", "requirements": ["data_protection", "consent", "right_to_erasure"]}
                ]
            }
        }
    }
    
    with open(config_dir / "compliance.yaml", 'w') as f:
        import yaml
        yaml.dump(compliance_config, f)
    
    yield security_dir
    
    shutil.rmtree(temp_dir)
