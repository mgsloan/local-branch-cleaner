# Branch Cleaner Web UI

A modern web interface for managing Git branches based on their GitHub PR status. This tool helps you visualize and safely clean up local branches that have been merged or closed.

## Features

- **Real-time Branch Analysis**: Streams branch analysis results as they're processed
- **Visual Diff Viewer**: Side-by-side comparison of branch changes vs merged PR
- **Batch Operations**: Select and delete multiple branches at once
- **Safety First**: Review changes before deletion, with confirmation dialogs
- **PR Integration**: Direct links to GitHub PRs with status indicators
- **Dark Mode Support**: Automatic theme based on system preferences

## Prerequisites

- Python 3.8+
- Node.js 16+
- Git
- [GitHub CLI (`gh`)](https://cli.github.com/) - authenticated with your GitHub account

## Installation

1. Clone this repository or copy the `web` directory to your project

2. Install GitHub CLI and authenticate:
   ```bash
   # Install gh (see https://cli.github.com/ for platform-specific instructions)
   # Then authenticate:
   gh auth login
   ```

## Usage

### Quick Start

From within any Git repository:

```bash
/path/to/branch-cleaner/web/start.sh
```

This will:
1. Start the backend API server on http://localhost:8000
2. Start the frontend development server on http://localhost:3000
3. Open your browser to the Branch Cleaner UI

### Manual Setup

If you prefer to run the services separately:

**Backend:**
```bash
cd web/backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

**Frontend:**
```bash
cd web/frontend
npm install
npm run dev
```

## User Interface

### Branch Categories

Branches are automatically categorized into:

- **Safe to Delete**: Merged PRs with identical content
- **Review Required**: Merged PRs with differences
- **Closed PRs**: Unmerged but closed PRs
- **Active**: Branches with open PRs
- **No PR**: Branches without associated PRs

### Key Features

1. **Batch Selection**: Select multiple branches for deletion
2. **Diff Viewer**: Click the eye icon to see differences between your branch and what was merged
3. **Remote Branch Deletion**: Option to delete both local and remote branches
4. **Search & Filter**: Find branches by name or PR title
5. **Real-time Updates**: See progress as branches are analyzed

### Keyboard Shortcuts

- `Ctrl+C` (in terminal): Stop all services

## Architecture

- **Backend**: FastAPI with WebSocket support for streaming updates
- **Frontend**: React with Tailwind CSS for styling
- **Communication**: RESTful API + WebSockets for real-time updates

## API Endpoints

- `GET /api/health` - Health check
- `WebSocket /ws/branches` - Stream branch analysis
- `DELETE /api/branch` - Delete a branch (local and optionally remote)
- `GET /api/branch/{name}/diff/{pr}` - Get diff data for visualization

## Configuration

The tool automatically detects your repository's main branch (`main` or `master`). No additional configuration is required.

## Troubleshooting

### "Not in a git repository"
Make sure you're running the tool from within a Git repository.

### "GitHub CLI (gh) is not installed"
Install the GitHub CLI from https://cli.github.com/

### "Not authenticated with GitHub"
Run `gh auth login` to authenticate with your GitHub account.

### Port conflicts
If ports 3000 or 8000 are already in use, you'll need to modify the port numbers in:
- `backend/app.py` (change the uvicorn port)
- `frontend/vite.config.js` (change the dev server port)
- `frontend/src/App.jsx` (update the WebSocket URL)

## Development

### Backend Development
The backend uses FastAPI with async support. To add new endpoints, edit `backend/app.py`.

### Frontend Development
The frontend uses React with Vite for fast development. Components are in `frontend/src/components/`.

### Adding Features
1. Add backend functionality in `backend/app.py`
2. Update frontend components as needed
3. Follow the existing patterns for WebSocket communication

## License

This project is provided as-is for use with the branch-cleaner tool.