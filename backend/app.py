#!/usr/bin/env python3
"""
Branch Cleaner Web API - Backend server for managing Git branches based on PR status
"""

import asyncio
import json
import logging
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    base_ref: Optional[str] = None


class BranchInfo(BaseModel):
    name: str
    pr_state: PRState
    status: BranchStatus
    prs: List[PRInfo] = []
    last_commit_date: Optional[datetime] = None
    last_commit_author: Optional[str] = None
    diff_stats: Optional[DiffStats] = None
    has_differences: bool = False
    unpushed_commits: int = 0
    unpulled_commits: int = 0
    tracking_branch: Optional[str] = None
    has_remote_branch: bool = False
    error: Optional[str] = None


class DeleteBranchRequest(BaseModel):
    branch_name: str
    delete_remote: bool = False


class RepoInfo(BaseModel):
    """Repository information"""
    path: str
    remote_url: Optional[str] = None
    main_branch: str
    total_branches: int = 0


class BranchAnalyzer:
    """Analyzes Git branches and their PR status"""

    def __init__(self, repo_path: str = None):
        if repo_path is None:
            repo_path = os.environ.get('GIT_REPO_PATH', '.')
        self.repo_path = Path(repo_path).resolve()
        logger.info(f"Initializing BranchAnalyzer with repo path: {self.repo_path}")

        # Verify it's a git repository
        if not (self.repo_path / '.git').exists():
            raise ValueError(f"Not a git repository: {self.repo_path}")

        self.main_branch = self._get_main_branch()
        self.remote_url = self._get_remote_url()

    def _get_main_branch(self) -> str:
        """Detect the main branch (main or master)"""
        logger.info("Detecting main branch...")
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            # Extract branch name from refs/remotes/origin/main
            main_branch = result.stdout.strip().split('/')[-1]
            logger.info(f"Main branch detected from HEAD: {main_branch}")
            return main_branch

        # Fallback: check if main or master exists
        for branch in ["main", "master"]:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", f"origin/{branch}"],
                cwd=self.repo_path,
                capture_output=True
            )
            if result.returncode == 0:
                logger.info(f"Main branch detected by checking: {branch}")
                return branch

        logger.warning("Could not detect main branch, defaulting to 'main'")
        return "main"  # Default fallback

    def _get_remote_url(self) -> Optional[str]:
        """Get the remote repository URL"""
        result = self._run_command(["git", "remote", "get-url", "origin"])
        if result.returncode == 0:
            return result.stdout.strip()
        return None

    def _run_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Run a command and return the result"""
        logger.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
        if result.returncode != 0:
            logger.info(f"Command failed with code {result.returncode}: {result.stderr}")
        return result

    def _get_pr_info(self, branch: str) -> List[PRInfo]:
        """Get PR information for a branch using gh CLI"""
        logger.info(f"Getting PR info for branch: {branch}")
        result = self._run_command([
            "gh", "pr", "list",
            "--head", branch,
            "--state", "all",
            "--json", "number,state,mergeCommit,title,url,headRefName,baseRefName,mergedAt"
        ])

        if result.returncode != 0:
            logger.error(f"Failed to get PR info for branch {branch}: {result.stderr}")
            return []

        try:
            pr_data = json.loads(result.stdout)
            logger.info(f"Found {len(pr_data)} PRs for branch {branch}")
            prs = []
            for pr in pr_data:
                # For merged PRs, get the full PR details to get the merge commit SHA
                if pr.get("state") == "MERGED" and pr.get("number"):
                    pr_details = self._get_pr_details(pr["number"])
                    if pr_details:
                        pr.update(pr_details)

                prs.append(PRInfo(
                    number=pr["number"],
                    state=pr["state"],
                    title=pr["title"],
                    url=pr.get("url"),
                    merge_commit=pr.get("mergeCommit", {}).get("oid") if isinstance(pr.get("mergeCommit"), dict) else pr.get("mergeCommit"),
                    base_ref=pr.get("baseRefName")
                ))
            return prs
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse PR data for branch {branch}: {e}")
            return []

    def _get_pr_details(self, pr_number: int) -> Optional[Dict[str, Any]]:
        """Get detailed PR information including merge commit SHA"""
        logger.info(f"Getting detailed info for PR #{pr_number}")
        result = self._run_command([
            "gh", "pr", "view", str(pr_number),
            "--json", "number,state,mergeCommit,baseRefName,mergedAt"
        ])

        if result.returncode != 0:
            # Try API directly for merge_commit_sha
            api_result = self._run_command([
                "gh", "api", f"repos/:owner/:repo/pulls/{pr_number}"
            ])
            if api_result.returncode == 0:
                try:
                    data = json.loads(api_result.stdout)
                    return {
                        "mergeCommit": {"oid": data.get("merge_commit_sha")} if data.get("merge_commit_sha") else None,
                        "baseRefName": data.get("base", {}).get("ref")
                    }
                except:
                    pass
            return None

        try:
            return json.loads(result.stdout)
        except:
            return None

    def _get_tracking_branch_info(self, branch: str) -> tuple[Optional[str], int, int, bool]:
        """Get tracking branch and count of unpushed/unpulled commits, and whether remote branch exists"""
        # Use origin/branch-name as the tracking branch
        tracking_branch = f"origin/{branch}"
        logger.info(f"Checking tracking branch {tracking_branch} for {branch}")

        # Check if the remote branch exists using ls-remote
        check_remote = self._run_command([
            "git", "ls-remote", "--heads", "origin", branch
        ])

        has_remote_branch = check_remote.returncode == 0 and bool(check_remote.stdout.strip())

        if not has_remote_branch:
            # Try alternative method - check if ref exists locally
            alt_check = self._run_command([
                "git", "rev-parse", "--verify", "--quiet", tracking_branch
            ])
            if alt_check.returncode != 0:
                # Remote branch doesn't exist
                logger.info(f"Remote branch {tracking_branch} does not exist")
                return None, 0, 0, False

        # Count unpushed commits (in local but not in remote)
        unpushed_cmd = ["git", "rev-list", "--count", f"{tracking_branch}..{branch}"]
        logger.info(f"Running unpushed check: {' '.join(unpushed_cmd)}")
        unpushed_result = self._run_command(unpushed_cmd)
        unpushed = 0
        if unpushed_result.returncode == 0 and unpushed_result.stdout.strip():
            try:
                unpushed = int(unpushed_result.stdout.strip())
                if unpushed > 0:
                    logger.info(f"Branch {branch} has {unpushed} unpushed commits")
            except ValueError:
                logger.error(f"Could not parse unpushed count for {branch}: {unpushed_result.stdout}")

        # Count unpulled commits (in remote but not in local)
        unpulled_cmd = ["git", "rev-list", "--count", f"{branch}..{tracking_branch}"]
        logger.info(f"Running unpulled check: {' '.join(unpulled_cmd)}")
        unpulled_result = self._run_command(unpulled_cmd)
        unpulled = 0
        if unpulled_result.returncode == 0 and unpulled_result.stdout.strip():
            try:
                unpulled = int(unpulled_result.stdout.strip())
                if unpulled > 0:
                    logger.info(f"Branch {branch} has {unpulled} unpulled commits")
            except ValueError:
                logger.error(f"Could not parse unpulled count for {branch}: {unpulled_result.stdout}")

        if unpushed > 0 or unpulled > 0:
            logger.info(f"Branch {branch}: {unpushed} unpushed, {unpulled} unpulled (tracking {tracking_branch})")

        return tracking_branch, unpushed, unpulled, has_remote_branch

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

    def _get_merge_commit_for_pr_info(self, pr: PRInfo) -> Optional[str]:
        """Get the merge commit for a PR using the PR info"""
        # Try the merge_commit from the PR info
        if pr.merge_commit:
            logger.debug(f"Using merge_commit from PR info for PR #{pr.number}: {pr.merge_commit}")
            return pr.merge_commit

        # If we don't have direct merge info, fall back to searching
        return self._get_merge_commit_for_pr(pr.number, pr.base_ref or self.main_branch)

    def _get_merge_commit_for_pr(self, pr_number: int, target_branch: Optional[str] = None) -> Optional[str]:
        """Find the merge commit for a PR in the target branch"""
        if not target_branch:
            target_branch = self.main_branch

        logger.info(f"Searching for merge commit for PR #{pr_number} in branch '{target_branch}'")

        # Try different grep patterns that GitHub uses
        patterns = [
            f"(#{pr_number})",
            f"#{pr_number}",
            f"Merge pull request #{pr_number}",
            f"Merge PR #{pr_number}",
        ]

        for pattern in patterns:
            result = self._run_command([
                "git", "log", target_branch,
                f"--grep={pattern}",
                "-n", "1",
                "--format=%H"
            ])

            if result.returncode == 0 and result.stdout.strip():
                commit = result.stdout.strip()
                logger.info(f"Found merge commit {commit} for PR #{pr_number} using pattern '{pattern}'")
                return commit

        logger.error(f"Could not find merge commit for PR #{pr_number} in {target_branch}")
        return None

    def _get_patch_id(self, base: str, branch: str) -> Optional[str]:
        """Get a patch ID for a diff, which is stable across rebase/cherry-pick"""
        # Use git patch-id to get a stable identifier for the patch content
        diff_result = self._run_command(["git", "diff", base, branch])
        if diff_result.returncode != 0:
            return None

        # Pipe the diff through git patch-id
        patch_id_result = subprocess.run(
            ["git", "patch-id", "--stable"],
            input=diff_result.stdout,
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )

        if patch_id_result.returncode == 0 and patch_id_result.stdout:
            # patch-id returns "patch-id commit-id", we just want the patch-id
            return patch_id_result.stdout.split()[0]
        return None


    def _extract_changed_lines(self, diff_text: str) -> str:
        """Extract only lines that start with + or - (actual changes)"""
        lines = []
        for line in diff_text.split('\n'):
            if line.startswith('+') or line.startswith('-'):
                # Skip the +++ and --- file headers
                if not line.startswith('+++') and not line.startswith('---'):
                    lines.append(line)
        # Sort to ensure consistent comparison
        lines.sort()
        return '\n'.join(lines)

    def _compare_branch_with_merged_pr(self, branch: str, pr: PRInfo) -> tuple[bool, Optional[DiffStats]]:
        """Compare branch content with what was merged in the PR"""
        merge_commit = self._get_merge_commit_for_pr_info(pr)
        if not merge_commit:
            logger.error(f"Cannot compare branch {branch} - merge commit not found for PR #{pr.number}")
            return False, None

        # Use the PR's target branch if available, otherwise use main
        target_branch = pr.base_ref or self.main_branch

        # Get the actual diffs using three-dot notation
        branch_diff_result = self._run_command(["git", "diff", f"{target_branch}...{branch}"])

        # For the PR, we need to get the diff from the merge commit's first parent
        pr_parent = f"{merge_commit}^1"
        pr_diff_result = self._run_command(["git", "diff", f"{pr_parent}...{merge_commit}"])

        if branch_diff_result.returncode != 0 or pr_diff_result.returncode != 0:
            logger.error(f"Could not get diffs for branch {branch}")
            return False, None

        # Extract only the actual changed lines (+ and -) for comparison
        branch_changes = self._extract_changed_lines(branch_diff_result.stdout)
        pr_changes = self._extract_changed_lines(pr_diff_result.stdout)

        # Compare only the actual changes
        diffs_match = branch_changes == pr_changes

        if not diffs_match:
            logger.info(f"Branch {branch} has different changes than merged PR")

        # Get diff stats if there are differences
        stats = None
        if not diffs_match:
            # Get stats for the branch
            stats_result = self._run_command([
                "git", "diff", "--numstat", f"{target_branch}...{branch}"
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

        return diffs_match, stats

    def analyze_branch(self, branch: str) -> BranchInfo:
        """Analyze a single branch (synchronous version)"""
        try:
            # Get PR info
            prs = self._get_pr_info(branch)
            pr_state = self._analyze_pr_state(prs)

            # Get commit info
            last_commit_date, last_commit_author = self._get_branch_last_commit_info(branch)

            # Get tracking branch info and remote branch existence
            tracking_branch, unpushed, unpulled, has_remote = self._get_tracking_branch_info(branch)

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
                    identical, stats = self._compare_branch_with_merged_pr(branch, merged_pr)
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
                has_differences=has_differences,
                tracking_branch=tracking_branch,
                unpushed_commits=unpushed,
                unpulled_commits=unpulled,
                has_remote_branch=has_remote
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
        logger.info("Getting local branches...")
        result = self._run_command(["git", "branch", "--format=%(refname:short)"])
        if result.returncode != 0:
            logger.error(f"Failed to get branches: {result.stderr}")
            return []

        all_branches = []
        branches = []
        for branch in result.stdout.strip().split('\n'):
            branch = branch.strip()
            if branch:
                all_branches.append(branch)
                if branch not in [self.main_branch, "master", "main"]:
                    branches.append(branch)

        logger.info(f"Found {len(all_branches)} total branches, {len(branches)} to analyze (excluding {self.main_branch})")
        logger.info(f"All branches: {all_branches}")
        logger.info(f"Branches to analyze: {branches}")
        return branches

    def get_repo_info(self) -> RepoInfo:
        """Get repository information"""
        branches = self.get_local_branches()
        return RepoInfo(
            path=str(self.repo_path),
            remote_url=self.remote_url,
            main_branch=self.main_branch,
            total_branches=len(branches)
        )

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

    def checkout_branch(self, branch: str) -> bool:
        """Checkout a local branch"""
        result = self._run_command(["git", "checkout", branch])
        if result.returncode != 0:
            raise Exception(f"Failed to checkout branch: {result.stderr}")
        return True

    def _normalize_diff_for_display(self, diff_text: str) -> str:
        """Normalize a diff for display by removing index lines but keeping line numbers intact"""
        lines = diff_text.split('\n')
        normalized = []

        for line in lines:
            # Skip index lines
            if line.startswith('index '):
                continue
            # Skip mode lines
            if line.startswith('old mode') or line.startswith('new mode'):
                continue
            # Skip similarity index
            if line.startswith('similarity index'):
                continue
            # Skip rename lines
            if line.startswith('rename from') or line.startswith('rename to'):
                continue
            # Keep everything else including @@ lines
            normalized.append(line)

        return '\n'.join(normalized)

    def _get_file_diff(self, full_diff: str, filename: str) -> Optional[str]:
        """Extract the diff for a specific file from a full diff"""
        lines = full_diff.split('\n')
        file_diff_lines = []
        in_file = False

        for i, line in enumerate(lines):
            if line.startswith('diff --git'):
                # Check if this is our file
                if f' b/{filename}' in line:
                    in_file = True
                    file_diff_lines.append(line)
                else:
                    in_file = False
            elif in_file:
                # Stop at the next file
                if i + 1 < len(lines) and lines[i + 1].startswith('diff --git'):
                    break
                file_diff_lines.append(line)

        return '\n'.join(file_diff_lines) if file_diff_lines else None

    def _get_file_content_at_ref(self, ref: str, filename: str) -> str:
        """Get the content of a file at a specific git ref"""
        result = self._run_command(["git", "show", f"{ref}:{filename}"])
        if result.returncode != 0:
            return ""
        return result.stdout

    def _generate_file_contents_for_diff(self, base_ref: str, target_ref: str, files: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        """Generate file contents for each file in the diff"""
        file_contents = {}

        for file_info in files:
            filename = file_info['filename']
            status = file_info['status']

            if status == 'D':  # Deleted file
                file_contents[filename] = {
                    'old': self._get_file_content_at_ref(base_ref, filename),
                    'new': ''
                }
            elif status == 'A':  # Added file
                file_contents[filename] = {
                    'old': '',
                    'new': self._get_file_content_at_ref(target_ref, filename)
                }
            else:  # Modified or renamed
                file_contents[filename] = {
                    'old': self._get_file_content_at_ref(base_ref, filename),
                    'new': self._get_file_content_at_ref(target_ref, filename)
                }

        return file_contents

    def get_branch_diff(self, branch: str, pr_number: int) -> Dict[str, Any]:
        """Get detailed diff information for a branch compared to its merged PR"""
        logger.info(f"Getting diff for branch {branch} vs PR #{pr_number}")

        # Special case: if pr_number is 0, just show diff with main branch
        if pr_number == 0:
            # Get merge base
            merge_base_result = self._run_command(["git", "merge-base", self.main_branch, branch])
            merge_base = merge_base_result.stdout.strip() if merge_base_result.returncode == 0 else self.main_branch

            # Get the diff using three-dot notation
            branch_diff_result = self._run_command([
                "git", "diff", "--no-color", f"{self.main_branch}...{branch}"
            ])

            # Get file list
            branch_files = self._run_command([
                "git", "diff", "--name-status", f"{self.main_branch}...{branch}"
            ])

            branch_files_parsed = self._parse_file_status(branch_files.stdout)

            # Generate file contents for proper diff display
            file_contents = self._generate_file_contents_for_diff(merge_base, branch, branch_files_parsed)

            return {
                "branch_diff": branch_diff_result.stdout,
                "pr_diff": "",  # Empty PR diff
                "branch_files": branch_files_parsed,
                "pr_files": [],
                "file_contents": file_contents,
                "git_commands": {
                    "branch": branch,
                    "base": self.main_branch,
                    "merge_commit": "HEAD"
                },
                "is_merge_base_diff": True
            }

        # Get the PR info to find target branch
        prs = self._get_pr_info(branch)
        pr = next((p for p in prs if p.number == pr_number), None)

        if not pr:
            # Try to get PR info directly
            pr_details = self._get_pr_details(pr_number)
            if pr_details:
                pr = PRInfo(
                    number=pr_number,
                    state="MERGED",
                    title="",
                    base_ref=pr_details.get("baseRefName"),
                    merge_commit=pr_details.get("mergeCommit", {}).get("oid") if isinstance(pr_details.get("mergeCommit"), dict) else pr_details.get("mergeCommit")
                )

        merge_commit = self._get_merge_commit_for_pr_info(pr) if pr else self._get_merge_commit_for_pr(pr_number)
        if not merge_commit:
            error_msg = f"Could not find merge commit for PR #{pr_number}. This might happen if:\n" \
                       f"1. The PR was merged with a different message format\n" \
                       f"2. The PR was rebased/squashed without the PR number in the commit message\n" \
                       f"3. The target branch doesn't contain the merge"
            logger.error(error_msg)
            raise Exception(error_msg)

        # Use the PR's target branch if available
        target_branch = pr.base_ref if pr and pr.base_ref else self.main_branch

        # Get the diffs using three-dot notation
        branch_diff_result = self._run_command([
            "git", "diff", "--no-color", f"{target_branch}...{branch}"
        ])

        # For the PR, get the diff from its first parent
        pr_parent = f"{merge_commit}^1"
        pr_diff_result = self._run_command([
            "git", "diff", "--no-color", f"{pr_parent}...{merge_commit}"
        ])

        # Normalize diffs for display
        normalized_branch_diff = self._normalize_diff_for_display(branch_diff_result.stdout)
        normalized_pr_diff = self._normalize_diff_for_display(pr_diff_result.stdout)

        # Get file lists
        branch_files = self._run_command([
            "git", "diff", "--name-status", f"{target_branch}...{branch}"
        ])

        pr_parent = f"{merge_commit}^1"
        pr_files = self._run_command([
            "git", "diff", "--name-status", f"{pr_parent}...{merge_commit}"
        ])

        branch_files_parsed = self._parse_file_status(branch_files.stdout)
        pr_files_parsed = self._parse_file_status(pr_files.stdout)

        # Filter out files that are identical between branch and PR
        filtered_branch_files = []
        filtered_pr_files = []

        # Create a map of filenames to check
        all_files = set()
        for f in branch_files_parsed:
            all_files.add(f['filename'])
        for f in pr_files_parsed:
            all_files.add(f['filename'])

        has_differences = False
        for filename in all_files:
            # Get the diff for this file from both sides
            branch_file_diff = self._get_file_diff(normalized_branch_diff, filename)
            pr_file_diff = self._get_file_diff(normalized_pr_diff, filename)

            # Only include if they're different
            if branch_file_diff != pr_file_diff:
                has_differences = True
                # Add to filtered lists
                for f in branch_files_parsed:
                    if f['filename'] == filename:
                        filtered_branch_files.append(f)
                        break
                for f in pr_files_parsed:
                    if f['filename'] == filename:
                        filtered_pr_files.append(f)
                        break

        # If no differences, return the merge base diff instead
        if not has_differences:
            return {
                "branch_diff": branch_diff_result.stdout,
                "pr_diff": "",  # Empty PR diff
                "branch_files": branch_files_parsed,
                "pr_files": [],
                "git_commands": {
                    "branch": branch,
                    "base": target_branch,
                    "merge_commit": "HEAD"
                },
                "is_merge_base_diff": True,
                "file_contents": {}
            }

        return {
            "branch_diff": normalized_branch_diff,
            "pr_diff": normalized_pr_diff,
            "branch_files": filtered_branch_files,
            "pr_files": filtered_pr_files,
            "git_commands": {
                "branch": branch,
                "base": target_branch,
                "pr_parent": pr_parent,
                "merge_commit": merge_commit
            },
            "file_contents": {}
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

# Global analyzer instance (will be initialized on first request)
analyzer = None

def get_analyzer():
    """Get or create the analyzer instance"""
    global analyzer
    if analyzer is None:
        try:
            repo_path = os.environ.get('GIT_REPO_PATH', '.')
            analyzer = BranchAnalyzer(repo_path)
            logger.info(f"BranchAnalyzer initialized successfully with path: {repo_path}")
        except Exception as e:
            logger.error(f"Failed to initialize BranchAnalyzer: {e}")
            raise
    return analyzer


@app.websocket("/ws/branches")
async def websocket_branches(websocket: WebSocket):
    """Stream branch analysis results via WebSocket"""
    await websocket.accept()
    logger.info("WebSocket connection established")

    # State variables
    analyzed_branches = set()

    try:
        # Get analyzer
        analyzer = get_analyzer()

        # Send repository info first
        repo_info = analyzer.get_repo_info()
        await websocket.send_json({
            "type": "repo_info",
            "data": repo_info.model_dump()
        })

        # Fetch branches first
        await websocket.send_json({
            "type": "status",
            "message": "Fetching latest changes from remote..."
        })

        fetch_result = analyzer._run_command(["git", "fetch", "--all"])
        if fetch_result.returncode != 0:
            logger.error(f"Git fetch failed: {fetch_result.stderr}")

        # Get all local branches
        branches = analyzer.get_local_branches()
        total = len(branches)

        await websocket.send_json({
            "type": "status",
            "message": f"Found {total} local branches to analyze"
        })

        # Analyze branches and stream results
        for i, branch in enumerate(branches):

            # Skip already analyzed branches (for resume)
            if branch in analyzed_branches:
                logger.info(f"Skipping already analyzed branch: {branch}")
                continue

            await websocket.send_json({
                "type": "progress",
                "current": len(analyzed_branches) + 1,
                "total": total,
                "branch": branch
            })

            # Run analysis in a separate thread to make it interruptible
            # Run the synchronous analyze_branch in a thread pool
            loop = asyncio.get_event_loop()
            branch_info = await loop.run_in_executor(None, analyzer.analyze_branch, branch)

            analyzed_branches.add(branch)

            # Send branch data
            # Convert datetime to ISO format string for JSON serialization
            branch_data = branch_info.model_dump()
            if branch_data.get('last_commit_date'):
                branch_data['last_commit_date'] = branch_data['last_commit_date'].isoformat()

            await websocket.send_json({
                "type": "branch",
                "data": branch_data
            })

            # Small delay to prevent overwhelming the client
            await asyncio.sleep(0.1)

        # Send completion when all branches are analyzed
        await websocket.send_json({
            "type": "complete",
            "total": total
        })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        # Ensure websocket is closed
        if websocket.client_state.value == 1:  # CONNECTED
            await websocket.close()


@app.delete("/api/branch")
async def delete_branch(request: DeleteBranchRequest):
    """Delete a local branch and optionally the remote branch"""
    try:
        analyzer = get_analyzer()
        analyzer.delete_branch(request.branch_name, request.delete_remote)
        return {"success": True, "message": f"Branch {request.branch_name} deleted"}
    except Exception as e:
        logger.error(f"Failed to delete branch {request.branch_name}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/branch/{branch_name}/diff/{pr_number}")
async def get_branch_diff(branch_name: str, pr_number: int):
    """Get diff information for a branch compared to its merged PR"""
    try:
        analyzer = get_analyzer()
        diff_data = analyzer.get_branch_diff(branch_name, pr_number)
        return diff_data
    except Exception as e:
        logger.error(f"Failed to get diff for branch {branch_name}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/branch/{branch_name:path}/checkout")
async def checkout_branch(branch_name: str):
    """Checkout a local branch"""
    try:
        analyzer = get_analyzer()
        analyzer.checkout_branch(branch_name)
        return {"success": True, "message": f"Checked out branch {branch_name}"}
    except Exception as e:
        logger.error(f"Failed to checkout branch {branch_name}: {e}")
        raise HTTPException(status_code=400, detail=str(e))





@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        analyzer = get_analyzer()
        return {"status": "healthy", "main_branch": analyzer.main_branch}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

@app.get("/api/repo-info")
async def get_repo_info():
    """Get repository information"""
    try:
        analyzer = get_analyzer()
        return analyzer.get_repo_info()
    except Exception as e:
        logger.error(f"Failed to get repo info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    logger.info("Starting Branch Cleaner API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
