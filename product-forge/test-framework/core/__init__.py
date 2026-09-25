"""
Test Automation Framework - Core Module
Multi-project, pipeline-level test framework for product QA
"""

__version__ = "1.0.0"
__author__ = "Pipeline Test Framework"

from .deployer import ProductDeployer
from .runner import TestRunner
from .suite_manager import SuiteManager
from .defect_tracker import DefectTracker
from .rcca import RCCAAnalyzer
from .agent_integration import AgentIntegration
from .test_generator import TestGenerator
from .reporter import TestReporter
from .test_selector import TestSelector
from .playwright_mcp import PlaywrightMCP

__all__ = [
    "ProductDeployer",
    "TestRunner",
    "SuiteManager",
    "DefectTracker",
    "RCCAAnalyzer",
    "AgentIntegration",
    "TestGenerator",
    "TestReporter",
    "TestSelector",
    "PlaywrightMCP"
]
