"""
Agent Integration - Integrates test framework with pipeline agents
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from .rcca import RCCAAnalyzer, RCCAReport

class AgentIntegration:
    """Reads and writes agent .md files for prevention rules"""
    
    def __init__(self, agents_path: Optional[str] = None):
        self.agents_path = Path(agents_path or Path(__file__).parent.parent.parent / ".opencode" / "agent")
        self.rcca = RCCAAnalyzer()
        
    def read_agent(self, agent_name: str) -> Optional[str]:
        """Read agent .md file"""
        agent_file = self.agents_path / f"{agent_name}.md"
        if not agent_file.exists():
            return None
        
        with open(agent_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    def append_prevention_rule(self, agent_name: str, rule: str, defect_id: str) -> bool:
        """Append prevention rule to agent file"""
        agent_file = self.agents_path / f"{agent_name}.md"
        if not agent_file.exists():
            return False
        
        # Read current content
        with open(agent_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if rule already exists
        if f"RCCA-{defect_id}" in content:
            return True  # Already added
        
        # Format prevention rule
        prevention_rule = f"""

## Prevention Rule (RCCA-{defect_id})
**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Defect**: {defect_id}
**Rule**: {rule}
**Source**: RCCA Auto-Update System
"""
        
        # Append to file
        with open(agent_file, 'a', encoding='utf-8') as f:
            f.write(prevention_rule)
        
        return True
    
    def update_agent_from_rcca(self, defect_id: str, rcca_report: RCCAReport) -> Dict[str, Any]:
        """Update agent based on RCCA findings"""
        updates = []
        
        for agent_update in rcca_report.agent_updates:
            agent_name = agent_update["agent"]
            rule = agent_update["rule"]
            
            success = self.append_prevention_rule(agent_name, rule, defect_id)
            
            updates.append({
                "agent": agent_name,
                "success": success,
                "rule": rule
            })
        
        return {
            "defect_id": defect_id,
            "updates": updates,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_agent_prevention_history(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get history of prevention rules added to agent"""
        content = self.read_agent(agent_name)
        if not content:
            return []
        
        history = []
        lines = content.split('\n')
        
        in_prevention = False
        current_rule = {}
        
        for line in lines:
            if "## Prevention Rule (RCCA-" in line:
                in_prevention = True
                current_rule = {"rule_line": line}
            elif in_prevention:
                if line.startswith("**Date**:"):
                    current_rule["date"] = line.replace("**Date**:", "").strip()
                elif line.startswith("**Defect**:"):
                    current_rule["defect_id"] = line.replace("**Defect**:", "").strip()
                elif line.startswith("**Rule**:"):
                    current_rule["rule"] = line.replace("**Rule**:", "").strip()
                elif line.startswith("**Source**:"):
                    current_rule["source"] = line.replace("**Source**:", "").strip()
                    history.append(current_rule)
                    in_prevention = False
                    current_rule = {}
        
        return history
    
    def apply_rcca_updates(self, project: str) -> Dict[str, Any]:
        """Apply all RCCA updates for a project"""
        rcca_summary = self.rcca.get_rcca_summary()
        
        all_updates = []
        for report_file in self.rcca.rcca_path.glob("*.json"):
            with open(report_file) as f:
                data = json.load(f)
            
            defect_id = data.get("defect_id")
            agent_updates = data.get("agent_updates", [])
            
            for update in agent_updates:
                agent_name = update.get("agent")
                rule = update.get("rule")
                
                if agent_name and rule:
                    success = self.append_prevention_rule(agent_name, rule, defect_id)
                    all_updates.append({
                        "agent": agent_name,
                        "defect_id": defect_id,
                        "success": success
                    })
        
        return {
            "project": project,
            "total_updates": len(all_updates),
            "updates": all_updates,
            "timestamp": datetime.now().isoformat()
        }
