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
GET /api/branches
  - Returns list of all local branches with basic info
  - Supports streaming responses

GET /api/branches/:branchName
  - Detailed information about a specific branch
  - Includes PR data and diff summary

GET /api/branches/:branchName/diff
  - Full diff comparison between branch and merged PR

POST /api/branches/:branchName/delete
  - Delete a single branch
  - Returns confirmation or error

POST /api/branches/bulk-delete
  - Delete multiple branches
  - Body: { branches: string[], dryRun: boolean }

GET /api/settings
  - Get current settings

PUT /api/settings
  - Update settings

WebSocket /ws
  - Real-time updates during branch analysis
```

## UI/UX Requirements

### 1. Visual Design

#### 1.1 Layout
- Fixed header with search and filters
- Sidebar with branch categories and counts
- Main content area with branch list
- Modal overlay for diff viewer

#### 1.2 Visual Elements
- Color coding for branch states:
  - Green: Safe to delete
  - Yellow: Review required
  - Red: Active/Open PR
  - Gray: No PR
- Icons for quick status recognition
- Progress bars for loading states

### 2. Interactions

#### 2.1 Responsive Feedback
- Immediate visual feedback on actions
- Loading states for async operations
- Success/error notifications
- Smooth transitions and animations

#### 2.2 Keyboard Shortcuts
- `j/k` - Navigate between branches
- `space` - Toggle branch selection
- `enter` - View diff
- `d` - Delete selected
- `?` - Show keyboard shortcuts

### 3. Accessibility

- ARIA labels for screen readers
- Keyboard navigation support
- High contrast mode
- Proper focus management

## Implementation Phases

### Phase 1: MVP (Week 1-2)
- Basic web server setup
- Branch list with PR status
- Simple diff viewer
- Single branch deletion
- Streaming updates

### Phase 2: Enhanced Diff Viewer (Week 3)
- Side-by-side diff comparison
- Syntax highlighting
- Diff navigation
- File tree view

### Phase 3: Bulk Operations (Week 4)
- Multi-select functionality
- Bulk delete with confirmation
- Undo capability
- Export branch list

### Phase 4: Polish (Week 5)
- Search and filtering
- Settings persistence
- Keyboard shortcuts
- Performance optimizations

## Success Metrics

1. **Time to Review**: Reduce time to review all branches by 70%
2. **Error Rate**: Zero accidental deletions of branches with uncommitted work
3. **User Satisfaction**: 90% of users prefer web UI over CLI
4. **Performance**: Load and analyze 50 branches in under 5 seconds

## Out of Scope

- Remote branch management
- Creating or merging PRs
- Commit history visualization
- Multi-repository support (v1)
- Branch creation or renaming

## Dependencies

- Git CLI available on system
- GitHub CLI (`gh`) authenticated
- Modern web browser with WebSocket support
- Local filesystem access for Git operations

## Risks and Mitigation

1. **Risk**: Performance with large numbers of branches
   - **Mitigation**: Implement pagination and virtual scrolling

2. **Risk**: Concurrent Git operations causing conflicts
   - **Mitigation**: Queue operations and show clear status

3. **Risk**: GitHub API rate limits
   - **Mitigation**: Cache PR data, implement exponential backoff

4. **Risk**: Complex merge conflicts in diff view
   - **Mitigation**: Provide fallback to external diff tools

## Future Enhancements

- Integration with popular IDEs (VSCode, IntelliJ)
- Support for other Git providers (GitLab, Bitbucket)
- Branch analytics and insights
- Automated cleanup scheduling
- Team-wide branch policies
