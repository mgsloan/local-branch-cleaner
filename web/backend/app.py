#!/usr/bin/env python3
"""
Branch Cleaner Web API - Backend server for managing Git branches based on PR status
"""

import asyncio
import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn


class PRState(str, Enum):
    MERGED = "merged"
    CLOSED = "closed"
    OPEN = "open"
    NO_PR = "no_pr"


class BranchStatus(str, Enum):
    SAFE_TO_DELETE = "safe_to_delete"
    REVIEW_REQUIRED = "review_required"
    CLOSED_PR = "closed_pr"
    ACTIVE = "active"
    NO_PR = "no_pr"


class DiffStats(BaseModel):
    additions: int
    deletions: int
    files_changed: int


class PRInfo(BaseModel):
    number: int
    state: str
    title: str
    url: Optional[str] = None
    merge_commit: Optional[str] = None


class BranchInfo(BaseModel):
    name: str
    pr_state: PRState
    status: BranchStatus
    prs: List[PRInfo] = []
    last_commit_date: Optional[datetime] = None
    last_commit_author: Optional[str] = None
    diff_stats: Optional[DiffStats] = None
    has_differences: bool = False
    error: Optional[str] = None


class DeleteBranchRequest(BaseModel):
    branch_name: str
    delete_remote: bool = False


class BranchAnalyzer:
    """Analyzes Git branches and their PR status"""

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)
        self.main_branch = self._get_main_branch()

    def _get_main_branch(self) -> str:
        """Detect the main branch (main or master)"""
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            # Extract branch name from refs/remotes/origin/main
            return result.stdout.strip().split('/')[-1]

        # Fallback: check if main or master exists
        for branch in ["main", "master"]:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", f"origin/{branch}"],
                cwd=self.repo_path,
                capture_output=True
            )
            if result.returncode == 0:
                return branch

        return "main"  # Default fallback

    def _run_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Run a command and return the result"""
        return subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)

    def _get_pr_info(self, branch: str) -> List[PRInfo]:
        """Get PR information for a branch using gh CLI"""
        result = self._run_command([
            "gh", "pr", "list",
            "--head", branch,
            "--state", "all",
            "--json", "number,state,mergeCommit,title,url,headRefName"
        ])

        if result.returncode != 0:
            return []

        try:
            pr_data = json.loads(result.stdout)
            return [
                PRInfo(
                    number=pr["number"],
                    state=pr["state"],
                    title=pr["title"],
                    url=pr.get("url"),
                    merge_commit=pr.get("mergeCommit")
                )
                for pr in pr_data
            ]
        except (json.JSONDecodeError, KeyError):
            return []

    def _get_branch_last_commit_info(self, branch: str) -> tuple[Optional[datetime], Optional[str]]:
        """Get last commit date and author for a branch"""
        result = self._run_command([
            "git", "log", "-1",
            "--format=%at|%an",
            branch
        ])

        if result.returncode != 0:
            return None, None

        try:
            parts = result.stdout.strip().split('|', 1)
            if len(parts) == 2:
                timestamp = int(parts[0])
                author = parts[1]
                return datetime.fromtimestamp(timestamp), author
        except (ValueError, IndexError):
            pass

        return None, None

    def _analyze_pr_state(self, prs: List[PRInfo]) -> PRState:
        """Analyze the overall PR state from a list of PRs"""
        if not prs:
            return PRState.NO_PR

        # If any PR is open, the branch is active
        if any(pr.state == "OPEN" for pr in prs):
            return PRState.OPEN

        # If any PR is merged, consider it merged
        if any(pr.state == "MERGED" for pr in prs):
            return PRState.MERGED

        # All PRs must be closed
        return PRState.CLOSED

    def _get_merge_commit_for_pr(self, pr_number: int) -> Optional[str]:
        """Find the merge commit for a PR in the main branch"""
        result = self._run_command([
            "git", "log", self.main_branch,
            f"--grep=(#{pr_number})",
            "-n", "1",
            "--format=%H"
        ])

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None

    def _compare_branch_with_merged_pr(self, branch: str, pr_number: int) -> tuple[bool, Optional[DiffStats]]:
        """Compare branch content with what was merged in the PR"""
        merge_commit = self._get_merge_commit_for_pr(pr_number)
        if not merge_commit:
            return False, None

        # Get merge base
        merge_base_result = self._run_command(["git", "merge-base", branch, self.main_branch])
        if merge_base_result.returncode != 0:
            return False, None

        merge_base = merge_base_result.stdout.strip()

        # Create temp files for diffs
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f1, \
             tempfile.NamedTemporaryFile(mode='w', delete=False) as f2:

            # Get branch diff
            branch_diff = self._run_command(["git", "diff", merge_base, branch])
            f1.write(branch_diff.stdout)
            f1.flush()

            # Get PR diff
            pr_diff = self._run_command(["git", "diff", f"{merge_commit}^1", merge_commit])
            f2.write(pr_diff.stdout)
            f2.flush()

            # Compare diffs
            diff_result = subprocess.run(
                ["diff", "-Bw", f1.name, f2.name],
                capture_output=True
            )

            # Get diff stats if there are differences
            stats = None
            if diff_result.returncode != 0:
                # Get stats for the branch
                stats_result = self._run_command([
                    "git", "diff", "--numstat", merge_base, branch
                ])
                if stats_result.returncode == 0:
                    lines = stats_result.stdout.strip().split('\n')
                    additions = 0
                    deletions = 0
                    files_changed = 0
                    for line in lines:
                        if line:
                            parts = line.split('\t')
                            if len(parts) >= 2:
                                try:
                                    additions += int(parts[0])
                                    deletions += int(parts[1])
                                    files_changed += 1
                                except ValueError:
                                    pass

                    stats = DiffStats(
                        additions=additions,
                        deletions=deletions,
                        files_changed=files_changed
                    )

            # Clean up temp files
            os.unlink(f1.name)
            os.unlink(f2.name)

            return diff_result.returncode == 0, stats

    async def analyze_branch(self, branch: str) -> BranchInfo:
        """Analyze a single branch"""
        try:
            # Get PR info
            prs = self._get_pr_info(branch)
            pr_state = self._analyze_pr_state(prs)

            # Get commit info
            last_commit_date, last_commit_author = self._get_branch_last_commit_info(branch)

            # Determine status and check for differences
            status = BranchStatus.NO_PR
            has_differences = False
            diff_stats = None

            if pr_state == PRState.NO_PR:
                status = BranchStatus.NO_PR
            elif pr_state == PRState.OPEN:
                status = BranchStatus.ACTIVE
            elif pr_state == PRState.CLOSED:
                status = BranchStatus.CLOSED_PR
            elif pr_state == PRState.MERGED:
                # Find the first merged PR
                merged_pr = next((pr for pr in prs if pr.state == "MERGED"), None)
                if merged_pr:
                    identical, stats = self._compare_branch_with_merged_pr(branch, merged_pr.number)
                    has_differences = not identical
                    diff_stats = stats
                    status = BranchStatus.REVIEW_REQUIRED if has_differences else BranchStatus.SAFE_TO_DELETE

            return BranchInfo(
                name=branch,
                pr_state=pr_state,
                status=status,
                prs=prs,
                last_commit_date=last_commit_date,
                last_commit_author=last_commit_author,
                diff_stats=diff_stats,
                has_differences=has_differences
            )
        except Exception as e:
            return BranchInfo(
                name=branch,
                pr_state=PRState.NO_PR,
                status=BranchStatus.NO_PR,
                error=str(e)
            )

    def get_local_branches(self) -> List[str]:
        """Get list of local branches"""
        result = self._run_command(["git", "branch", "--format=%(refname:short)"])
        if result.returncode != 0:
            return []

        branches = []
        for branch in result.stdout.strip().split('\n'):
            branch = branch.strip()
            if branch and branch not in [self.main_branch, "master", "main"]:
                branches.append(branch)

        return branches

    def delete_branch(self, branch: str, delete_remote: bool = False) -> bool:
        """Delete a local branch and optionally the remote branch"""
        # Delete local branch
        result = self._run_command(["git", "branch", "-D", branch])
        if result.returncode != 0:
            raise Exception(f"Failed to delete local branch: {result.stderr}")

        # Delete remote branch if requested
        if delete_remote:
            # Check if remote branch exists
            remote_result = self._run_command(["git", "ls-remote", "--heads", "origin", branch])
            if remote_result.returncode == 0 and remote_result.stdout.strip():
                # Delete remote branch
                push_result = self._run_command(["git", "push", "origin", "--delete", branch])
                if push_result.returncode != 0:
                    raise Exception(f"Failed to delete remote branch: {push_result.stderr}")

        return True

    def get_branch_diff(self, branch: str, pr_number: int) -> Dict[str, Any]:
        """Get detailed diff information for a branch compared to its merged PR"""
        merge_commit = self._get_merge_commit_for_pr(pr_number)
        if not merge_commit:
            raise Exception(f"Could not find merge commit for PR #{pr_number}")

        # Get merge base
        merge_base_result = self._run_command(["git", "merge-base", branch, self.main_branch])
        if merge_base_result.returncode != 0:
            raise Exception("Failed to find merge base")

        merge_base = merge_base_result.stdout.strip()

        # Get the diffs
        branch_diff_result = self._run_command([
            "git", "diff", "--no-color", merge_base, branch
        ])

        pr_diff_result = self._run_command([
            "git", "diff", "--no-color", f"{merge_commit}^1", merge_commit
        ])

        # Get file lists
        branch_files = self._run_command([
            "git", "diff", "--name-status", merge_base, branch
        ])

        pr_files = self._run_command([
            "git", "diff", "--name-status", f"{merge_commit}^1", merge_commit
        ])

        return {
            "branch_diff": branch_diff_result.stdout,
            "pr_diff": pr_diff_result.stdout,
            "branch_files": self._parse_file_status(branch_files.stdout),
            "pr_files": self._parse_file_status(pr_files.stdout)
        }

    def _parse_file_status(self, output: str) -> List[Dict[str, str]]:
        """Parse git diff --name-status output"""
        files = []
        for line in output.strip().split('\n'):
            if line:
                parts = line.split('\t', 1)
                if len(parts) == 2:
                    status, filename = parts
                    files.append({
                        "status": status,
                        "filename": filename
                    })
        return files


# FastAPI app
app = FastAPI(title="Branch Cleaner API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global analyzer instance
analyzer = BranchAnalyzer()


@app.websocket("/ws/branches")
async def websocket_branches(websocket: WebSocket):
    """Stream branch analysis results via WebSocket"""
    await websocket.accept()

    try:
        # Fetch branches first
        await websocket.send_json({
            "type": "status",
            "message": "Fetching latest changes from remote..."
        })

        analyzer._run_command(["git", "fetch", "origin"])

        # Get all local branches
        branches = analyzer.get_local_branches()
        total = len(branches)

        await websocket.send_json({
            "type": "status",
            "message": f"Found {total} local branches to analyze"
        })

        # Analyze branches and stream results
        for i, branch in enumerate(branches):
            await websocket.send_json({
                "type": "progress",
                "current": i + 1,
                "total": total,
                "branch": branch
            })

            # Analyze branch
            branch_info = await analyzer.analyze_branch(branch)

            # Send branch data
            await websocket.send_json({
                "type": "branch",
                "data": branch_info.dict()
            })

            # Small delay to prevent overwhelming the client
            await asyncio.sleep(0.1)

        # Send completion
        await websocket.send_json({
            "type": "complete",
            "total": total
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
        await websocket.close()


@app.delete("/api/branch")
async def delete_branch(request: DeleteBranchRequest):
    """Delete a local branch and optionally the remote branch"""
    try:
        analyzer.delete_branch(request.branch_name, request.delete_remote)
        return {"success": True, "message": f"Branch {request.branch_name} deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/branch/{branch_name}/diff/{pr_number}")
async def get_branch_diff(branch_name: str, pr_number: int):
    """Get diff information for a branch compared to its merged PR"""
    try:
        diff_data = analyzer.get_branch_diff(branch_name, pr_number)
        return diff_data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "main_branch": analyzer.main_branch}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
