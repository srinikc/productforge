"""
Product Forge Self-Improvement - Code Analyzer

Analyzes improvement content, scans codebase for affected files,
generates file-level diffs, and creates implementation plans.
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
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

import sys
sys.path.insert(0, str(_PF_ROOT))
from core.conversation_models import (
    FileChange, ImplementationPlan, RiskLevel, ImplementationStatus
)


class CodeAnalyzer:
    """Analyzes Product Forge improvements and generates implementation plans."""

    def __init__(self):
        self.root_dir = _PF_ROOT
        self.codebase_index: Dict[str, Dict[str, Any]] = {}
        self._index_codebase()

    def _index_codebase(self):
        """Index all relevant files in the codebase."""
        skip_dirs = {
            '__pycache__', 'node_modules', '.git', '.backups',
            'products', '.product_forge_improvements', '.conversations',
            'test-framework', 'venv', '.venv', 'env'
        }
        skip_extensions = {'.pyc', '.pyo', '.class', '.exe', '.dll', '.so', '.dylib'}

        for root, dirs, files in os.walk(self.root_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in skip_extensions:
                    continue

                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, self.root_dir)

                try:
                    stat = os.stat(fpath)
                    self.codebase_index[rel_path] = {
                        'path': fpath,
                        'rel_path': rel_path,
                        'size': stat.st_size,
                        'extension': ext,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    }
                except (OSError, PermissionError):
                    pass

    def analyze_improvement(self, content: str, ideas: list, requirements: list,
                           conv_id: str = "") -> ImplementationPlan:
        """
        Analyze improvement content and generate an implementation plan.

        Args:
            content: The full improvement content (markdown/text)
            ideas: List of extracted ideas
            requirements: List of extracted requirements
            conv_id: Conversation ID

        Returns:
            ImplementationPlan with file changes
        """
        file_changes = []

        # Determine improvement type from content
        improvement_type = self._classify_improvement(content, ideas)

        # Find affected files based on improvement type
        affected_files = self._find_affected_files(improvement_type, content, ideas)

        # Generate specific changes for each affected file
        for file_info in affected_files:
            changes = self._generate_file_changes(file_info, content, ideas, requirements)
            file_changes.extend(changes)

        # Assess overall risk
        risk_level = self._assess_risk(file_changes)

        # Create implementation plan
        plan = ImplementationPlan(
            conversation_id=conv_id,
            file_changes=file_changes,
            risk_level=risk_level,
            requires_tests=risk_level != RiskLevel.LOW.value,
            rollback_available=True,
            status=ImplementationStatus.ANALYZED.value
        )

        return plan

    def _classify_improvement(self, content: str, ideas: list) -> str:
        """Classify the improvement type based on content and ideas."""
        content_lower = content.lower()

        # Check for specific improvement types
        if any(kw in content_lower for kw in ['dashboard', 'ui', 'interface', 'frontend', 'css', 'html']):
            return 'dashboard'
        if any(kw in content_lower for kw in ['api', 'endpoint', 'route', 'handler', 'server']):
            return 'api'
        if any(kw in content_lower for kw in ['pipeline', 'orchestrator', 'stage', 'agent']):
            return 'pipeline'
        if any(kw in content_lower for kw in ['core', 'model', 'data', 'schema', 'database']):
            return 'core'
        if any(kw in content_lower for kw in ['adapter', 'chatgpt', 'gemini', 'claude', 'integration']):
            return 'adapter'
        if any(kw in content_lower for kw in ['test', 'testing', 'qa', 'quality']):
            return 'testing'
        if any(kw in content_lower for kw in ['doc', 'documentation', 'readme', 'guide']):
            return 'documentation'

        # Check ideas for clues
        for idea in ideas:
            idea_text = f"{idea.get('title', '')} {idea.get('description', '')}".lower()
            if 'dashboard' in idea_text or 'ui' in idea_text:
                return 'dashboard'
            if 'api' in idea_text or 'endpoint' in idea_text:
                return 'api'

        return 'general'

    def _find_affected_files(self, improvement_type: str, content: str,
                            ideas: list) -> List[Dict[str, Any]]:
        """Find files that might be affected by this improvement."""
        affected = []

        # Map improvement types to likely file patterns
        type_patterns = {
        'dashboard': ['dashboard/static/', 'dashboard/api/'],
        'api': ['dashboard/api/app.py', 'dashboard/server.py'],
            'pipeline': ['core/pipeline_executor.py', 'pipeline-definition.json', 'core/intent_router.py'],
            'core': ['core/conversation_models.py', 'core/conversation_compiler.py'],
            'adapter': ['adapters/chatgpt/', 'adapters/gemini/', 'adapters/claude/'],
            'testing': ['test-framework/', 'core/test_'],
            'documentation': ['docs/', 'README.md', 'adapters/chatgpt/instructions.md'],
            'general': []
        }

        patterns = type_patterns.get(improvement_type, [])

        # Also scan content for file path mentions
        mentioned_files = self._extract_file_mentions(content)
        patterns.extend(mentioned_files)

        # Find matching files
        for rel_path, info in self.codebase_index.items():
            for pattern in patterns:
                if pattern in rel_path or rel_path.startswith(pattern):
                    affected.append(info)
                    break

        # If no specific files found, include key files based on content keywords
        if not affected:
            affected = self._find_files_by_keywords(content, ideas)

        # Limit to most relevant files (max 10)
        return affected[:10]

    def _extract_file_mentions(self, content: str) -> List[str]:
        """Extract file path mentions from content."""
        mentions = []

        # Look for common file path patterns
        patterns = [
            r'(?:in|at|from|to|file|path)\s+[`"\']?([a-zA-Z_/]+\.(?:py|md|html|json|yaml|yml|js|ts))[`"\']?',
            r'`([a-zA-Z_/]+\.(?:py|md|html|json|yaml|yml|js|ts))`',
            r'"([a-zA-Z_/]+\.(?:py|md|html|json|yaml|yml|js|ts))"',
            r"'([a-zA-Z_/]+\.(?:py|md|html|json|yaml|yml|js|ts))'",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            mentions.extend(matches)

        # Deduplicate and filter
        seen = set()
        result = []
        for m in mentions:
            if m not in seen and not m.startswith('http'):
                seen.add(m)
                result.append(m)

        return result

    def _find_files_by_keywords(self, content: str, ideas: list) -> List[Dict[str, Any]]:
        """Find files based on content keywords."""
        keywords = set()

        # Extract keywords from content
        words = re.findall(r'\b[a-zA-Z_]{4,}\b', content.lower())
        keyword_counts = {}
        for w in words:
            if w not in {'this', 'that', 'with', 'from', 'have', 'will', 'should', 'could', 'would'}:
                keyword_counts[w] = keyword_counts.get(w, 0) + 1

        # Get top keywords
        top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        keywords = {k for k, v in top_keywords}

        # Find files containing these keywords
        affected = []
        for rel_path, info in self.codebase_index.items():
            if info['extension'] not in {'.py', '.html', '.md', '.json', '.yaml'}:
                continue

            try:
                with open(info['path'], 'r', encoding='utf-8', errors='ignore') as f:
                    file_content = f.read().lower()

                # Check if file contains multiple keywords
                matches = sum(1 for kw in keywords if kw in file_content)
                if matches >= 3:
                    affected.append(info)
            except (OSError, PermissionError):
                pass

        # Sort by relevance (number of keyword matches)
        return affected[:10]

    def _generate_file_changes(self, file_info: Dict[str, Any], content: str,
                              ideas: list, requirements: list) -> List[FileChange]:
        """Generate specific file changes for an affected file."""
        changes = []

        fpath = file_info['path']
        rel_path = file_info['rel_path']

        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                file_content = f.read()
        except (OSError, PermissionError):
            return changes

        # Generate changes based on the improvement content
        # This is a simplified version - in production, use LLM to generate specific diffs

        # For HTML files: look for UI-related improvements
        if rel_path.endswith('.html'):
            html_changes = self._generate_html_changes(file_content, content, ideas)
            changes.extend(html_changes)

        # For Python files: look for code improvements
        elif rel_path.endswith('.py'):
            py_changes = self._generate_python_changes(file_content, content, ideas)
            changes.extend(py_changes)

        # For JSON files: look for config improvements
        elif rel_path.endswith('.json'):
            json_changes = self._generate_json_changes(file_content, content, ideas)
            changes.extend(json_changes)

        # For Markdown files: look for documentation improvements
        elif rel_path.endswith('.md'):
            md_changes = self._generate_markdown_changes(file_content, content, ideas)
            changes.extend(md_changes)

        return changes

    def _generate_html_changes(self, file_content: str, improvement: str,
                              ideas: list) -> List[FileChange]:
        """Generate HTML file changes."""
        changes = []

        # Look for common improvement patterns in the improvement content
        improvement_lower = improvement.lower()

        # Dark mode toggle
        if 'dark mode' in improvement_lower or 'dark-mode' in improvement_lower:
            # Find where to add dark mode toggle
            lines = file_content.split('\n')
            for i, line in enumerate(lines):
                if 'settings' in line.lower() or 'control-bar' in line.lower():
                    changes.append(FileChange(
                        file_path="",
                        operation="modify",
                        line_start=max(0, i - 2),
                        line_end=min(len(lines), i + 5),
                        old_code='\n'.join(lines[max(0, i-2):min(len(lines), i+5)]),
                        new_code=self._generate_dark_mode_toggle(),
                        explanation="Add dark mode toggle to settings area",
                        risk_level=RiskLevel.LOW.value
                    ))
                    break

        # If no specific changes found, create a general improvement change
        if not changes and ideas:
            changes.append(FileChange(
                file_path="",
                operation="modify",
                line_start=0,
                line_end=min(20, len(file_content.split('\n'))),
                old_code='\n'.join(file_content.split('\n')[:20]),
                new_code=self._generate_general_improvement_html(file_content, ideas),
                explanation="Apply general improvements based on extracted ideas",
                risk_level=RiskLevel.MEDIUM.value
            ))

        return changes

    def _generate_python_changes(self, file_content: str, improvement: str,
                                ideas: list) -> List[FileChange]:
        """Generate Python file changes."""
        changes = []
        lines = file_content.split('\n')

        # Look for function/class improvements
        improvement_lower = improvement.lower()

        # Find relevant functions or classes to modify
        for i, line in enumerate(lines):
            if line.strip().startswith('def ') or line.strip().startswith('class '):
                func_name = line.strip().split('(')[0].replace('def ', '').replace('class ', '')

                # Check if improvement mentions this function
                if func_name.lower() in improvement_lower or any(func_name.lower() in str(idea.get('title', '')).lower() for idea in ideas):
                    # Get the function body
                    end_idx = min(len(lines), i + 20)
                    changes.append(FileChange(
                        file_path="",
                        operation="modify",
                        line_start=i,
                        line_end=end_idx,
                        old_code='\n'.join(lines[i:end_idx]),
                        new_code=self._generate_improved_function(lines[i:end_idx], improvement, ideas),
                        explanation=f"Improve {func_name} based on improvement requirements",
                        risk_level=RiskLevel.MEDIUM.value
                    ))

        return changes

    def _generate_json_changes(self, file_content: str, improvement: str,
                              ideas: list) -> List[FileChange]:
        """Generate JSON file changes."""
        changes = []

        try:
            import json
            data = json.loads(file_content)
            # Generate improved JSON
            improved = self._improve_json_config(data, improvement, ideas)
            if improved != data:
                changes.append(FileChange(
                    file_path="",
                    operation="modify",
                    line_start=0,
                    line_end=len(file_content.split('\n')),
                    old_code=file_content,
                    new_code=json.dumps(improved, indent=2, ensure_ascii=False),
                    explanation="Update configuration based on improvement requirements",
                    risk_level=RiskLevel.LOW.value
                ))
        except (json.JSONDecodeError, ValueError):
            pass

        return changes

    def _generate_markdown_changes(self, file_content: str, improvement: str,
                                  ideas: list) -> List[FileChange]:
        """Generate Markdown file changes."""
        changes = []

        # Add new section based on improvement
        new_section = self._generate_documentation_section(improvement, ideas)

        if new_section:
            changes.append(FileChange(
                file_path="",
                operation="modify",
                line_start=len(file_content.split('\n')),
                line_end=len(file_content.split('\n')),
                old_code="",
                new_code=new_section,
                explanation="Add documentation section for new improvement",
                risk_level=RiskLevel.LOW.value
            ))

        return changes

    def _generate_dark_mode_toggle(self) -> str:
        """Generate dark mode toggle HTML."""
        return '''<div class="form-group">
            <label class="form-label">Appearance</label>
            <div style="display:flex;gap:8px;align-items:center">
                <button class="btn btn-sm" onclick="toggleDarkMode()">&#9789; Toggle Dark Mode</button>
                <span style="font-size:11px;color:var(--muted)">Current: <span id="theme-mode">Dark</span></span>
            </div>
        </div>'''

    def _generate_general_improvement_html(self, content: str, ideas: list) -> str:
        """Generate general HTML improvement."""
        # This is simplified - in production, use LLM to generate specific changes
        lines = content.split('\n')
        return '\n'.join(lines[:50])  # Return first 50 lines as placeholder

    def _generate_improved_function(self, lines: list, improvement: str, ideas: list) -> str:
        """Generate improved function code."""
        # This is simplified - in production, use LLM to generate specific code
        return '\n'.join(lines)  # Return original as placeholder

    def _improve_json_config(self, data: dict, improvement: str, ideas: list) -> dict:
        """Improve JSON configuration."""
        # This is simplified - in production, use LLM to generate specific config
        return data

    def _generate_documentation_section(self, improvement: str, ideas: list) -> str:
        """Generate documentation section for improvement."""
        section = "\n\n## Recent Improvements\n\n"
        for idea in ideas[:3]:
            title = idea.get('title', 'Untitled')
            desc = idea.get('description', '')
            section += f"### {title}\n\n{desc}\n\n"
        return section

    def _assess_risk(self, changes: List[FileChange]) -> str:
        """Assess overall risk level based on changes."""
        if not changes:
            return RiskLevel.LOW.value

        high_risk_files = {'router.py', 'pipeline_executor.py', 'intent_router.py'}
        medium_risk_files = {'conversation_models.py', 'conversation_compiler.py', 'dashboard.html'}

        high_count = 0
        medium_count = 0

        for change in changes:
            fname = os.path.basename(change.file_path) if change.file_path else ""
            if fname in high_risk_files:
                high_count += 1
            elif fname in medium_risk_files:
                medium_count += 1

        if high_count > 0:
            return RiskLevel.HIGH.value
        elif medium_count > 2 or len(changes) > 5:
            return RiskLevel.MEDIUM.value
        else:
            return RiskLevel.LOW.value

    def create_diff_preview(self, file_path: str, changes: List[FileChange]) -> str:
        """Generate a unified diff preview for a file."""
        if not changes:
            return "No changes"

        lines = []
        for change in changes:
            lines.append(f"--- a/{change.file_path or file_path}")
            lines.append(f"+++ b/{change.file_path or file_path}")
            lines.append(f"@@ -{change.line_start + 1},{change.line_end - change.line_start} +{change.line_start + 1},{change.line_end - change.line_start} @@")

            # Old code (removed lines)
            if change.old_code:
                for line in change.old_code.split('\n'):
                    lines.append(f"-{line}")

            # New code (added lines)
            if change.new_code:
                for line in change.new_code.split('\n'):
                    lines.append(f"+{line}")

        return '\n'.join(lines)

    def get_codebase_summary(self) -> Dict[str, Any]:
        """Get a summary of the indexed codebase."""
        ext_counts = {}
        total_size = 0

        for rel_path, info in self.codebase_index.items():
            ext = info['extension'] or 'other'
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
            total_size += info['size']

        return {
            "total_files": len(self.codebase_index),
            "total_size_bytes": total_size,
            "extensions": ext_counts,
            "key_files": [p for p in self.codebase_index.keys()
                         if any(k in p for k in ['router.py', 'dashboard.html', 'intent_router.py', 'conversation_models.py'])]
        }
