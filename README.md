# Branch Cleaner

A powerful tool for managing Git branches based on their GitHub PR status. Includes both a CLI tool and a modern web interface for safely cleaning up merged or closed branches.

## Overview

Branch Cleaner helps you:
- Identify local branches whose PRs have been merged
- Verify that merged content matches your local branch
- Safely delete branches that are no longer needed
- Review differences before deletion
- Handle branches with closed (unmerged) PRs

## Components

### 1. CLI Tool (`cleanup-branches`)

A bash script that analyzes your local branches and their associated GitHub PRs.

**Features:**
- Dry-run mode by default (use `--apply` to actually delete)
- Verifies merged PR content matches local branch
- Shows branches that differ from what was merged
- Handles closed PRs with `--include-closed` flag
- Diff viewing with `--diff branch-name`

**Usage:**
```bash
# Show what would be deleted (dry run)
./cleanup-branches

# Actually delete branches
./cleanup-branches --apply

# Include closed PRs
./cleanup-branches --apply --include-closed

# View diff for a specific branch
./cleanup-branches --diff feature-branch
```

### 2. Web UI

A modern web interface that provides visual branch management.

**Features:**
- Real-time branch analysis with progress tracking
- Visual diff viewer for comparing branches
- Batch operations for multiple branches
- Direct GitHub PR integration
- Dark mode support

**Quick Start:**
```bash
cd web
./start.sh
```

Then open http://localhost:3000 in your browser.

## Requirements

- Git
- [GitHub CLI (`gh`)](https://cli.github.com/) - must be authenticated
- For Web UI:
  - Python 3.8+
  - Node.js 16+

## Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd branch-cleaner
   ```

2. Install GitHub CLI and authenticate:
   ```bash
   # See https://cli.github.com/ for installation
   gh auth login
   ```

3. Make the CLI script executable:
   ```bash
   chmod +x cleanup-branches
   ```

## How It Works

1. **Branch Discovery**: Finds all local branches (excluding main/master)
2. **PR Analysis**: Uses GitHub API to check PR status for each branch
3. **Content Verification**: For merged PRs, compares the merged diff with your local changes
4. **Safe Deletion**: Only deletes branches whose content exactly matches what was merged
5. **Review**: Shows branches with differences for manual review

## Safety Features

- **Dry-run by default**: Won't delete anything without explicit `--apply` flag
- **Content verification**: Ensures merged PR matches local branch
- **Confirmation dialogs**: Web UI asks for confirmation before deletion
- **Preserves different branches**: Branches with uncommitted changes are never deleted
- **No PR = No deletion**: Branches without PRs are preserved

## Branch Categories

Branches are organized into these categories:

- **Safe to Delete**: Merged PRs with identical content
- **Review Required**: Merged PRs but branch has differences
- **Closed PRs**: Unmerged PRs that were closed
- **Active**: Branches with open PRs
- **No PR**: Branches without associated PRs

## Examples

### CLI Examples

```bash
# Basic usage - see what would be deleted
./cleanup-branches

# Delete merged branches
./cleanup-branches --apply

# Include closed PRs in deletion
./cleanup-branches --apply --include-closed

# Check diff for a specific branch
./cleanup-branches --diff my-feature-branch
```

### Web UI Workflow

1. Start the web server: `cd web && ./start.sh`
2. Open http://localhost:3000
3. Wait for branch analysis to complete
4. Review branches in each category
5. Click eye icon to view diffs for branches with changes
6. Select branches to delete
7. Confirm deletion (optionally including remote branches)

## Troubleshooting

### "GitHub CLI (gh) is not installed"
Install from https://cli.github.com/

### "Not authenticated with GitHub"
Run `gh auth login`

### "Could not find merge commit"
The PR might have been rebased or the main branch might have been force-pushed.

### Web UI won't start
- Check that ports 3000 and 8000 are available
- Ensure you're in a git repository
- Verify Python and Node.js are installed

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is provided as-is. Use at your own risk. Always verify branches before deletion.