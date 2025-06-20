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
        logger.debug(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
        if result.returncode != 0:
            logger.debug(f"Command failed with code {result.returncode}: {result.stderr}")
        return result

    def _get_pr_info(self, branch: str) -> List[PRInfo]:
        """Get PR information for a branch using gh CLI"""
        logger.debug(f"Getting PR info for branch: {branch}")
        result = self._run_command([
            "gh", "pr", "list",
            "--head", branch,
            "--state", "all",
            "--json", "number,state,mergeCommit,title,url,headRefName"
        ])

        if result.returncode != 0:
            logger.warning(f"Failed to get PR info for branch {branch}: {result.stderr}")
            return []

        try:
            pr_data = json.loads(result.stdout)
            logger.debug(f"Found {len(pr_data)} PRs for branch {branch}")
            return [
                PRInfo(
                    number=pr["number"],
                    state=pr["state"],
                    title=pr["title"],
                    url=pr.get("url"),
                    merge_commit=pr.get("mergeCommit", {}).get("oid") if isinstance(pr.get("mergeCommit"), dict) else pr.get("mergeCommit")
                )
                for pr in pr_data
            ]
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse PR data for branch {branch}: {e}")
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
        logger.info(f"Searching for merge commit for PR #{pr_number} in branch '{self.main_branch}'")

        # First, let's see what merge commits exist
        debug_result = self._run_command([
            "git", "log", self.main_branch,
            "--grep=#",
            "-n", "10",
            "--format=%H %s"
        ])
        if debug_result.returncode == 0:
            logger.debug(f"Recent commits with PR numbers:\n{debug_result.stdout}")

        # Try different grep patterns that GitHub uses
        patterns = [
            f"(#{pr_number})",
            f"#{pr_number}",
            f"Merge pull request #{pr_number}",
            f"Merge PR #{pr_number}",
        ]

        for pattern in patterns:
            result = self._run_command([
                "git", "log", self.main_branch,
                f"--grep={pattern}",
                "-n", "1",
                "--format=%H"
            ])

            if result.returncode == 0 and result.stdout.strip():
                commit = result.stdout.strip()
                logger.info(f"Found merge commit {commit} for PR #{pr_number} using pattern '{pattern}'")

                # Get the commit message to verify
                msg_result = self._run_command(["git", "log", "-1", "--format=%s", commit])
                if msg_result.returncode == 0:
                    logger.debug(f"Commit message: {msg_result.stdout.strip()}")

                return commit

        logger.warning(f"Could not find merge commit for PR #{pr_number} in {self.main_branch}")
        logger.warning(f"Tried patterns: {patterns}")
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

    def _compare_branch_with_merged_pr(self, branch: str, pr_number: int) -> tuple[bool, Optional[DiffStats]]:
        """Compare branch content with what was merged in the PR"""
        merge_commit = self._get_merge_commit_for_pr(pr_number)
        if not merge_commit:
            logger.warning(f"Cannot compare branch {branch} - merge commit not found for PR #{pr_number}")
            return False, None

        # Get merge base
        merge_base_result = self._run_command(["git", "merge-base", branch, self.main_branch])
        if merge_base_result.returncode != 0:
            return False, None

        merge_base = merge_base_result.stdout.strip()

        # Get the merge base between the branch and the PR's parent
        pr_parent = f"{merge_commit}^1"
        pr_merge_base_result = self._run_command(["git", "merge-base", pr_parent, self.main_branch])
        if pr_merge_base_result.returncode != 0:
            pr_merge_base = pr_parent  # Fallback to parent if merge-base fails
        else:
            pr_merge_base = pr_merge_base_result.stdout.strip()

        # Use patch-id to compare the actual patch content
        branch_patch_id = self._get_patch_id(merge_base, branch)
        pr_patch_id = self._get_patch_id(pr_merge_base, merge_commit)

        # If we couldn't get patch IDs, fall back to direct diff
        if not branch_patch_id or not pr_patch_id:
            logger.warning(f"Could not get patch IDs for branch {branch}, falling back to diff comparison")
            # Use git's own diff comparison
            branch_diff = self._run_command(["git", "diff", "--no-index", "--no-prefix", "-w", merge_base, branch])
            pr_diff = self._run_command(["git", "diff", "--no-index", "--no-prefix", "-w", f"{merge_commit}^1", merge_commit])
            diffs_match = branch_diff.stdout == pr_diff.stdout
        else:
            # Compare patch IDs
            diffs_match = branch_patch_id == pr_patch_id

        # Get diff stats if there are differences
        stats = None
        if not diffs_match:
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

        return diffs_match, stats

    def analyze_branch(self, branch: str) -> BranchInfo:
        """Analyze a single branch (synchronous version)"""
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
        logger.debug(f"All branches: {all_branches}")
        logger.debug(f"Branches to analyze: {branches}")
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

    def check_remote_branch_exists(self, branch: str) -> bool:
        """Check if a remote branch exists"""
        result = self._run_command(["git", "ls-remote", "--heads", "origin", branch])
        return result.returncode == 0 and bool(result.stdout.strip())

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

    def get_branch_diff(self, branch: str, pr_number: int) -> Dict[str, Any]:
        """Get detailed diff information for a branch compared to its merged PR"""
        logger.info(f"Getting diff for branch {branch} vs PR #{pr_number}")
        merge_commit = self._get_merge_commit_for_pr(pr_number)
        if not merge_commit:
            error_msg = f"Could not find merge commit for PR #{pr_number}. This might happen if:\n" \
                       f"1. The PR was merged with a different message format\n" \
                       f"2. The PR was rebased/squashed without the PR number in the commit message\n" \
                       f"3. The branch '{self.main_branch}' doesn't contain the merge"
            logger.error(error_msg)
            raise Exception(error_msg)

        # Get merge base
        merge_base_result = self._run_command(["git", "merge-base", branch, self.main_branch])
        if merge_base_result.returncode != 0:
            raise Exception("Failed to find merge base")

        merge_base = merge_base_result.stdout.strip()

        # Get the merge base for the PR
        pr_parent = f"{merge_commit}^1"
        pr_merge_base_result = self._run_command(["git", "merge-base", pr_parent, self.main_branch])
        if pr_merge_base_result.returncode != 0:
            pr_merge_base = pr_parent
        else:
            pr_merge_base = pr_merge_base_result.stdout.strip()

        # Get the diffs relative to their respective merge bases
        branch_diff_result = self._run_command([
            "git", "diff", "--no-color", merge_base, branch
        ])

        pr_diff_result = self._run_command([
            "git", "diff", "--no-color", pr_merge_base, merge_commit
        ])

        # Normalize diffs for display
        normalized_branch_diff = self._normalize_diff_for_display(branch_diff_result.stdout)
        normalized_pr_diff = self._normalize_diff_for_display(pr_diff_result.stdout)

        # Get file lists
        branch_files = self._run_command([
            "git", "diff", "--name-status", merge_base, branch
        ])

        pr_files = self._run_command([
            "git", "diff", "--name-status", pr_merge_base, merge_commit
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

        for filename in all_files:
            # Get the diff for this file from both sides
            branch_file_diff = self._get_file_diff(normalized_branch_diff, filename)
            pr_file_diff = self._get_file_diff(normalized_pr_diff, filename)

            # Only include if they're different
            if branch_file_diff != pr_file_diff:
                # Add to filtered lists
                for f in branch_files_parsed:
                    if f['filename'] == filename:
                        filtered_branch_files.append(f)
                        break
                for f in pr_files_parsed:
                    if f['filename'] == filename:
                        filtered_pr_files.append(f)
                        break

        return {
            "branch_diff": normalized_branch_diff,
            "pr_diff": normalized_pr_diff,
            "branch_files": filtered_branch_files,
            "pr_files": filtered_pr_files,
            "git_commands": {
                "branch_merge_base": merge_base,
                "pr_merge_base": pr_merge_base,
                "merge_commit": merge_commit
            }
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
    is_paused = False
    analyzed_branches = set()
    message_queue = asyncio.Queue()

    async def receive_messages():
        """Receive messages from client and put them in the queue"""
        try:
            while True:
                message = await websocket.receive_json()
                logger.info(f"Received message from client: {message}")
                await message_queue.put(message)
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected in receive_messages")
            await message_queue.put({"type": "disconnect"})
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            await message_queue.put({"type": "error", "error": str(e)})

    # Start message receiver
    receive_task = asyncio.create_task(receive_messages())

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

        fetch_result = analyzer._run_command(["git", "fetch", "origin"])
        if fetch_result.returncode != 0:
            logger.warning(f"Git fetch failed: {fetch_result.stderr}")

        # Get all local branches
        branches = analyzer.get_local_branches()
        total = len(branches)

        await websocket.send_json({
            "type": "status",
            "message": f"Found {total} local branches to analyze"
        })

        async def check_messages_and_pause():
            """Check message queue and handle pause state"""
            nonlocal is_paused

            # Process any pending messages
            while not message_queue.empty():
                try:
                    message = message_queue.get_nowait()
                    logger.debug(f"Processing message from queue: {message}")
                    if message.get("type") == "pause":
                        is_paused = True
                        logger.info(f"Analysis paused by client")
                    elif message.get("type") == "resume":
                        is_paused = False
                        logger.info(f"Analysis resumed by client")
                    elif message.get("type") == "disconnect":
                        logger.info("Client disconnected")
                        return False
                    elif message.get("type") == "error":
                        logger.error(f"Error in message queue: {message.get('error')}")
                        return False
                except asyncio.QueueEmpty:
                    break

            # Handle pause state
            if is_paused:
                logger.info(f"In pause state")
                await websocket.send_json({
                    "type": "paused",
                    "current": len(analyzed_branches),
                    "total": total
                })

                # Wait while paused
                while is_paused:
                    try:
                        message = await asyncio.wait_for(message_queue.get(), timeout=0.5)
                        if message.get("type") == "resume":
                            is_paused = False
                            logger.info(f"Resuming from pause")
                            break
                        elif message.get("type") == "disconnect":
                            logger.info("Client disconnected during pause")
                            return False
                    except asyncio.TimeoutError:
                        await websocket.send_json({
                            "type": "paused",
                            "current": len(analyzed_branches),
                            "total": total
                        })

            return True

        # Analyze branches and stream results
        for i, branch in enumerate(branches):
            # Check messages and handle pause before each branch
            if not await check_messages_and_pause():
                return

            # Skip already analyzed branches (for resume)
            if branch in analyzed_branches:
                logger.debug(f"Skipping already analyzed branch: {branch}")
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

            # Check for pause immediately after analysis completes
            if not await check_messages_and_pause():
                return

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
        # Cancel the receive task
        receive_task.cancel()
        try:
            await receive_task
        except asyncio.CancelledError:
            pass

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


@app.get("/api/branch/{branch_name}/remote-exists")
async def check_remote_branch(branch_name: str):
    """Check if a remote branch exists"""
    try:
        analyzer = get_analyzer()
        exists = analyzer.check_remote_branch_exists(branch_name)
        return {"exists": exists, "branch": branch_name}
    except Exception as e:
        logger.error(f"Failed to check remote branch {branch_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
