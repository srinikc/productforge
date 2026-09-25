"""
Git Manager
Git worktree isolation for concurrent multi-project execution
"""

import subprocess
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class GitBranch:
    """Git branch information"""
    name: str
    current: bool
    remote: Optional[str]
    last_commit: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GitStatus:
    """Git status information"""
    clean: bool
    branch: str
    ahead: int
    behind: int
    modified_files: int
    untracked_files: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GitManager:
    """
    Git worktree manager for concurrent multi-project execution.
    
    Features:
    - Per-project branch isolation
    - Worktree management
    - Safe concurrent commits
    - Branch naming conventions
    """
    
    def __init__(self, workspace_dir: str = "."):
        """
        Initialize git manager.
        
        Args:
            workspace_dir: Path to workspace root
        """
        self.workspace_dir = Path(workspace_dir)
    
    def _run_git(self, args: List[str], check: bool = True) -> Tuple[str, str]:
        """
        Run git command.
        
        Args:
            args: Git command arguments
            check: Whether to check return code
            
        Returns:
            Tuple of (stdout, stderr)
        """
        cmd = ["git"] + args
        result = subprocess.run(
            cmd,
            cwd=self.workspace_dir,
            capture_output=True,
            text=True,
            check=check
        )
        return result.stdout.strip(), result.stderr.strip()
    
    def is_git_repo(self) -> bool:
        """
        Check if workspace is a git repository.
        
        Returns:
            True if git repo
        """
        try:
            self._run_git(["rev-parse", "--git-dir"])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_current_branch(self) -> Optional[str]:
        """
        Get current git branch.
        
        Returns:
            Current branch name or None
        """
        try:
            stdout, _ = self._run_git(["branch", "--show-current"])
            return stdout
        except subprocess.CalledProcessError:
            return None
    
    def get_status(self) -> GitStatus:
        """
        Get git status.
        
        Returns:
            GitStatus
        """
        try:
            # Get branch
            branch = self.get_current_branch() or "unknown"
            
            # Get ahead/behind
            try:
                stdout, _ = self._run_git(["rev-list", "--left-right", "--count", f"HEAD...@{{upstream}}"])
                parts = stdout.split()
                ahead = int(parts[0]) if len(parts) > 0 else 0
                behind = int(parts[1]) if len(parts) > 1 else 0
            except:
                ahead = 0
                behind = 0
            
            # Get file counts
            stdout, _ = self._run_git(["status", "--porcelain"])
            lines = [l for l in stdout.split('\n') if l.strip()]
            modified = sum(1 for l in lines if l.startswith(' M') or l.startswith('M'))
            untracked = sum(1 for l in lines if l.startswith('??'))
            
            return GitStatus(
                clean=len(lines) == 0,
                branch=branch,
                ahead=ahead,
                behind=behind,
                modified_files=modified,
                untracked_files=untracked
            )
        except Exception as e:
            return GitStatus(
                clean=False,
                branch="unknown",
                ahead=0,
                behind=0,
                modified_files=0,
                untracked_files=0
            )
    
    def create_branch(self, branch_name: str, start_point: Optional[str] = None) -> bool:
        """
        Create a new branch.
        
        Args:
            branch_name: Branch name
            start_point: Optional start point (commit/branch)
            
        Returns:
            True if successful
        """
        try:
            args = ["branch", branch_name]
            if start_point:
                args.append(start_point)
            self._run_git(args)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def checkout(self, branch_name: str, create: bool = False) -> bool:
        """
        Checkout a branch.
        
        Args:
            branch_name: Branch name
            create: Create branch if it doesn't exist
            
        Returns:
            True if successful
        """
        try:
            args = ["checkout"]
            if create:
                args.append("-b")
            args.append(branch_name)
            self._run_git(args)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def create_project_branch(self, project: str, stage: Optional[str] = None) -> str:
        """
        Create a project-specific branch.
        
        Args:
            project: Project name
            stage: Optional stage identifier
            
        Returns:
            Created branch name
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        parts = ["pipeline", project]
        if stage:
            parts.append(stage)
        parts.append(timestamp)
        
        branch_name = "/".join(parts)
        self.create_branch(branch_name, create=True)
        return branch_name
    
    def commit(self, message: str, files: Optional[List[str]] = None) -> bool:
        """
        Create a commit.
        
        Args:
            message: Commit message
            files: Optional list of files to stage
            
        Returns:
            True if successful
        """
        try:
            # Stage files
            if files:
                for file in files:
                    self._run_git(["add", file])
            else:
                self._run_git(["add", "-A"])
            
            # Create commit
            self._run_git(["commit", "-m", message])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def safe_commit(self, project: str, message: str, files: Optional[List[str]] = None) -> bool:
        """
        Safely commit with project-scoped branch.
        
        Args:
            project: Project name
            message: Commit message
            files: Optional list of files to stage
            
        Returns:
            True if successful
        """
        # Get current branch
        original_branch = self.get_current_branch()
        
        try:
            # Create project branch if on main/master
            if original_branch in ['main', 'master', None]:
                branch = self.create_project_branch(project)
                self.checkout(branch, create=True)
            
            # Commit
            success = self.commit(message, files)
            
            return success
        except Exception as e:
            return False
        finally:
            # Return to original branch
            if original_branch and original_branch in ['main', 'master']:
                self.checkout(original_branch)
    
    def list_branches(self, pattern: Optional[str] = None) -> List[GitBranch]:
        """
        List git branches.
        
        Args:
            pattern: Optional branch pattern
            
        Returns:
            List of GitBranch
        """
        try:
            args = ["branch", "-a"]
            if pattern:
                args.extend(["--list", pattern])
            
            stdout, _ = self._run_git(args)
            branches = []
            
            for line in stdout.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                current = line.startswith('*')
                name = line.lstrip('* ').strip()
                remote = None
                
                if name.startswith('remotes/'):
                    remote = name
                    name = name.replace('remotes/', '', 1)
                
                # Get last commit
                try:
                    commit_stdout, _ = self._run_git(["log", "-1", "--format=%h", name])
                    last_commit = commit_stdout
                except:
                    last_commit = "unknown"
                
                branches.append(GitBranch(
                    name=name,
                    current=current,
                    remote=remote,
                    last_commit=last_commit
                ))
            
            return branches
        except subprocess.CalledProcessError:
            return []
    
    def create_worktree(self, project: str, branch: Optional[str] = None) -> Optional[Path]:
        """
        Create a git worktree for a project.
        
        Args:
            project: Project name
            branch: Optional branch name
            
        Returns:
            Worktree path if successful
        """
        worktree_dir = self.workspace_dir / "worktrees" / project
        branch = branch or f"pipeline/{project}"
        
        try:
            # Create branch if it doesn't exist
            self.create_branch(branch, create=True)
            
            # Create worktree
            self._run_git(["worktree", "add", str(worktree_dir), branch])
            return worktree_dir
        except subprocess.CalledProcessError:
            return None
    
    def remove_worktree(self, project: str) -> bool:
        """
        Remove a git worktree.
        
        Args:
            project: Project name
            
        Returns:
            True if successful
        """
        worktree_dir = self.workspace_dir / "worktrees" / project
        
        try:
            self._run_git(["worktree", "remove", str(worktree_dir), "--force"])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def list_worktrees(self) -> List[Dict[str, Any]]:
        """
        List git worktrees.
        
        Returns:
            List of worktree information
        """
        try:
            stdout, _ = self._run_git(["worktree", "list", "--porcelain"])
            worktrees = []
            current = {}
            
            for line in stdout.split('\n'):
                line = line.strip()
                if not line:
                    if current:
                        worktrees.append(current)
                        current = {}
                    continue
                
                if line.startswith('worktree '):
                    current['path'] = line.replace('worktree ', '')
                elif line.startswith('HEAD '):
                    current['head'] = line.replace('HEAD ', '')
                elif line.startswith('branch '):
                    current['branch'] = line.replace('branch ', '')
            
            if current:
                worktrees.append(current)
            
            return worktrees
        except subprocess.CalledProcessError:
            return []
    
    def stash(self, message: Optional[str] = None) -> bool:
        """
        Stash current changes.
        
        Args:
            message: Optional stash message
            
        Returns:
            True if successful
        """
        try:
            args = ["stash"]
            if message:
                args.extend(["push", "-m", message])
            self._run_git(args)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def stash_pop(self) -> bool:
        """
        Pop the latest stash.
        
        Returns:
            True if successful
        """
        try:
            self._run_git(["stash", "pop"])
            return True
        except subprocess.CalledProcessError:
            return False
