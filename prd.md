This was mostly generated from a brief description of what I wanted and referencing a previously generated branch cleanup bash script.  There was some manual editing to reduce the scope, simplify the design, and select which dependencies to use.

# Branch Cleaner Web UI - Product Requirements Document

## Overview

Branch Cleaner Web UI is a local web application that provides a visual interface for managing Git branches based on their associated GitHub PR status. It replaces the CLI-based `cleanup-branches` script with an intuitive web interface that makes it easy to see branch states, review differences, and safely clean up merged or closed branches.

## Problem Statement

The current CLI tool (`cleanup-branches`) effectively identifies and removes local Git branches whose PRs have been merged, but:
- It's difficult to visualize what has changed between the merged PR and the local branch
- The diff output in terminal is hard to read and navigate
- Users must run multiple commands to explore different branches
- The feedback loop for reviewing changes before deletion is cumbersome

## Goals

1. **Visual Clarity**: Provide a clear, visual representation of branch states and differences
2. **Safety**: Ensure users can easily review changes before deleting branches
3. **Efficiency**: Streamline the process of reviewing and cleaning up multiple branches
4. **Real-time Feedback**: Show progress as branches are being analyzed
5. **Accessibility**: Make branch management accessible to developers less comfortable with CLI tools

## User Stories

### As a developer, I want to:
1. See all my local branches and their PR states in one view
2. Easily visualize differences between my local branch and what was merged
3. Batch select branches for deletion after reviewing them
4. Filter branches by state (merged, closed, open, no PR)
5. See detailed PR information without leaving the interface
6. Have confidence that I won't accidentally delete important work

## Functional Requirements

### 1. Branch List View

#### 1.1 Real-time Loading
- Display a loading indicator when the page opens
- Stream branch analysis results as they complete
- Show progress indicator (e.g., "Analyzing 5 of 23 branches...")
- Prioritize displaying branches as soon as their status is determined

#### 1.2 Branch Information Display
Each branch should show:
- Branch name
- PR status (merged, closed, open, no PR found)
- PR number(s) with links to GitHub
- Last commit date and author
- Diff summary (lines added/removed) when different from merged version
- Visual indicator for branches safe to delete vs. those with differences

#### 1.3 Categorization
Branches grouped into sections:
- **Safe to Delete**: Merged PRs with identical content
- **Review Required**: Merged PRs with differences
- **Closed PRs**: Unmerged but closed PRs
- **Active**: Branches with open PRs
- **No PR**: Branches without associated PRs

### 2. Diff Viewer

#### 2.1 Side-by-Side Comparison
- Show merged PR changes on the left
- Show current branch changes on the right
- Highlight differences between the two
- Syntax highlighting for code
- Collapsible file sections

#### 2.2 Diff Summary
- File change overview (which files modified, added, deleted)
- Statistics (insertions, deletions, files changed)
- Quick navigation between changed files

#### 2.3 Diff Actions
- Toggle between unified and side-by-side view
- Expand/collapse unchanged sections
- Copy diff to clipboard
- Open in external diff tool

### 3. Branch Actions

#### 3.1 Individual Actions
- Delete single branch
- View detailed diff
- Open PR on GitHub
- Copy branch name
- Checkout branch (opens in terminal/IDE)

#### 3.2 Bulk Actions
- Select multiple branches
- Delete selected branches
- Select all in category
- Deselect all

#### 3.3 Safety Features
- Confirmation dialog before deletion
- Show exactly what will be deleted
- Undo recently deleted branches (within session)
- Dry run mode by default

### 4. Filtering and Search

#### 4.1 Filters
- By PR state (merged, closed, open, no PR)
- By diff status (identical, has differences)
- By date (last commit older than X days)
- By author

#### 4.2 Search
- Search by branch name
- Search by PR title
- Search by PR number

### 5. Settings and Configuration

#### 5.1 Preferences
- Default to dry run mode
- Include/exclude closed PRs
- Auto-refresh interval
- Theme (light/dark)

#### 5.2 Repository Settings
- Configure which branch is main/master
- Set custom merge base for comparison
- Ignore patterns for branches

## Technical Requirements

### 1. Architecture

#### 1.1 Backend
- Language: Python (Flask/FastAPI)
- Git operations using native `git` cli
- GitHub API access via `gh` cli

#### 1.2 Frontend
- Framework: React for reactive updates
- State management for branch data
- WebSocket client for streaming updates
- Diff visualization library  react-diff-viewer

### 2. API Endpoints

```
DELETE /branch
  - Deletes a local branch

DELETE /remote-branch
  - Deletes a remote branch

WebSocket /branches
  - Streams branches with all info - status, diff, etc
```

## UI/UX Requirements

### 1. Visual Design

#### 1.1 Layout

List of branches with folding.

### 2. Interactions

#### 2.1 Responsive Feedback
- Immediate visual feedback on actions
- Loading states for async operations
- Success/error notifications

#### 2.2 Keyboard Shortcuts
- `j/k` - Navigate between branches
- `space` or `x` - Toggle branch selection
- `enter` - View diff
- `d` - Delete selected. If the remote branch exists, prompt whether to delete it too
