import React, { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { formatDistanceToNow } from "date-fns";
import {
  GitBranch,
  GitMerge,
  GitPullRequest,
  Trash2,
  Check,
  X,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Search,
  Filter,
  RefreshCw,
  Eye,
  Loader2,
  CheckCircle2,
  XCircle,
  GitCommit,
  ExternalLink,
} from "lucide-react";
import DiffViewer from "./components/DiffViewer";
import BranchCard from "./components/BranchCard";
import ConfirmDialog from "./components/ConfirmDialog";

const API_BASE_URL = "/api";
const WS_URL = "ws://localhost:8000/ws/branches";

const BRANCH_CATEGORIES = {
  safe_to_delete: {
    title: "Safe to Delete",
    description: "Branches with merged PRs and no differences",
    icon: CheckCircle2,
    color: "text-green-600",
    bgColor: "bg-green-50",
    borderColor: "border-green-200",
  },
  review_required: {
    title: "Review Required",
    description: "Branches with merged PRs but have differences",
    icon: AlertCircle,
    color: "text-yellow-600",
    bgColor: "bg-yellow-50",
    borderColor: "border-yellow-200",
  },
  closed_pr: {
    title: "Closed PRs",
    description: "Branches with closed (unmerged) PRs",
    icon: XCircle,
    color: "text-red-600",
    bgColor: "bg-red-50",
    borderColor: "border-red-200",
  },
  active: {
    title: "Active",
    description: "Branches with open PRs",
    icon: GitPullRequest,
    color: "text-blue-600",
    bgColor: "bg-blue-50",
    borderColor: "border-blue-200",
  },
  no_pr: {
    title: "No PR",
    description: "Branches without associated PRs",
    icon: GitBranch,
    color: "text-gray-600",
    bgColor: "bg-gray-50",
    borderColor: "border-gray-200",
  },
};

function App() {
  const [branches, setBranches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [selectedBranches, setSelectedBranches] = useState(new Set());
  const [expandedCategories, setExpandedCategories] = useState(
    new Set(Object.keys(BRANCH_CATEGORIES)),
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [filterState, setFilterState] = useState("all");
  const [showDiffViewer, setShowDiffViewer] = useState(false);
  const [diffViewerData, setDiffViewerData] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState({
    open: false,
    branches: [],
    includeRemote: false,
  });
  const [statusMessage, setStatusMessage] = useState("");
  const [repoInfo, setRepoInfo] = useState(null);

  // WebSocket connection for streaming branch data
  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        console.log("WebSocket connected");
        setBranches([]);
        setLoading(true);
        setProgress({ current: 0, total: 0 });
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case "repo_info":
            setRepoInfo(data.data);
            break;

          case "status":
            setStatusMessage(data.message);
            break;

          case "progress":
            setProgress({ current: data.current, total: data.total });
            break;

          case "branch":
            setBranches((prev) => [...prev, data.data]);
            break;

          case "complete":
            setLoading(false);
            setStatusMessage("");
            break;

          case "error":
            console.error("WebSocket error:", data.message);
            setLoading(false);
            setStatusMessage(`Error: ${data.message}`);
            break;
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setLoading(false);
        setStatusMessage("Connection error");
      };

      ws.onclose = () => {
        console.log("WebSocket disconnected");
        setLoading(false);
      };

      return ws;
    };

    const ws = connectWebSocket();
    return () => ws.close();
  }, []);

  // Group branches by category
  const categorizedBranches = useMemo(() => {
    const filtered = branches.filter((branch) => {
      const matchesSearch =
        branch.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        branch.prs?.some((pr) =>
          pr.title?.toLowerCase().includes(searchQuery.toLowerCase()),
        );

      if (filterState === "all") return matchesSearch;
      return matchesSearch && branch.status === filterState;
    });

    return filtered.reduce((acc, branch) => {
      const category = branch.status || "no_pr";
      if (!acc[category]) acc[category] = [];
      acc[category].push(branch);
      return acc;
    }, {});
  }, [branches, searchQuery, filterState]);

  const toggleCategory = (category) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  const toggleBranchSelection = (branchName) => {
    setSelectedBranches((prev) => {
      const next = new Set(prev);
      if (next.has(branchName)) {
        next.delete(branchName);
      } else {
        next.add(branchName);
      }
      return next;
    });
  };

  const selectAllInCategory = (category) => {
    const branchNames = categorizedBranches[category]?.map((b) => b.name) || [];
    setSelectedBranches((prev) => {
      const next = new Set(prev);
      branchNames.forEach((name) => next.add(name));
      return next;
    });
  };

  const deselectAllInCategory = (category) => {
    const branchNames = categorizedBranches[category]?.map((b) => b.name) || [];
    setSelectedBranches((prev) => {
      const next = new Set(prev);
      branchNames.forEach((name) => next.delete(name));
      return next;
    });
  };

  const handleDelete = (branchNames, includeRemote = false) => {
    const branchesToDelete = Array.isArray(branchNames)
      ? branchNames
      : [branchNames];
    setConfirmDialog({
      open: true,
      branches: branchesToDelete,
      includeRemote,
    });
  };

  const confirmDelete = async () => {
    const { branches: branchesToDelete, includeRemote } = confirmDialog;

    for (const branchName of branchesToDelete) {
      try {
        await axios.delete(`${API_BASE_URL}/branch`, {
          data: { branch_name: branchName, delete_remote: includeRemote },
        });

        // Remove from state
        setBranches((prev) => prev.filter((b) => b.name !== branchName));
        setSelectedBranches((prev) => {
          const next = new Set(prev);
          next.delete(branchName);
          return next;
        });
      } catch (error) {
        console.error(`Failed to delete branch ${branchName}:`, error);
        alert(
          `Failed to delete branch ${branchName}: ${error.response?.data?.detail || error.message}`,
        );
      }
    }

    setConfirmDialog({ open: false, branches: [], includeRemote: false });
  };

  const viewDiff = async (branch, prNumber) => {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/branch/${branch.name}/diff/${prNumber}`,
      );
      setDiffViewerData({
        branch,
        prNumber,
        ...response.data,
      });
      setShowDiffViewer(true);
    } catch (error) {
      console.error("Failed to load diff:", error);
      alert(
        `Failed to load diff: ${error.response?.data?.detail || error.message}`,
      );
    }
  };

  const refresh = () => {
    window.location.reload();
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <GitBranch className="h-8 w-8 text-blue-600" />
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                Branch Cleaner
              </h1>
            </div>
            {repoInfo && (
              <div className="flex items-center space-x-4 text-sm text-gray-600 dark:text-gray-400">
                <div className="flex items-center space-x-1">
                  <span className="font-medium">Repo:</span>
                  <span className="font-mono">{repoInfo.path}</span>
                </div>
                {repoInfo.remote_url && (
                  <div className="flex items-center space-x-1">
                    <span className="font-medium">Remote:</span>
                    <span className="font-mono truncate max-w-xs">
                      {repoInfo.remote_url}
                    </span>
                  </div>
                )}
                <div className="flex items-center space-x-1">
                  <span className="font-medium">Main:</span>
                  <span className="font-mono">{repoInfo.main_branch}</span>
                </div>
              </div>
            )}
            <button
              onClick={refresh}
              className="btn btn-secondary flex items-center space-x-2"
              disabled={loading}
            >
              <RefreshCw
                className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
              />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </header>

      {/* Status Bar */}
      {loading && (
        <div className="bg-blue-50 dark:bg-blue-900/20 border-b border-blue-200 dark:border-blue-800">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                <span className="text-sm text-blue-800 dark:text-blue-200">
                  {statusMessage ||
                    `Analyzing branches... (${progress.current} of ${progress.total})`}
                </span>
              </div>
              {progress.total > 0 && (
                <div className="w-48 bg-blue-200 dark:bg-blue-800 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${(progress.current / progress.total) * 100}%`,
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search branches or PRs..."
                  className="pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              {/* Filter */}
              <select
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={filterState}
                onChange={(e) => setFilterState(e.target.value)}
              >
                <option value="all">All States</option>
                <option value="safe_to_delete">Safe to Delete</option>
                <option value="review_required">Review Required</option>
                <option value="closed_pr">Closed PRs</option>
                <option value="active">Active</option>
                <option value="no_pr">No PR</option>
              </select>
            </div>

            {/* Bulk Actions */}
            {selectedBranches.size > 0 && (
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {selectedBranches.size} selected
                </span>
                <button
                  onClick={() => handleDelete(Array.from(selectedBranches))}
                  className="btn btn-danger flex items-center space-x-2"
                >
                  <Trash2 className="h-4 w-4" />
                  <span>Delete Selected</span>
                </button>
                <button
                  onClick={() => setSelectedBranches(new Set())}
                  className="btn btn-secondary"
                >
                  Clear Selection
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {Object.entries(BRANCH_CATEGORIES).map(
          ([categoryKey, categoryInfo]) => {
            const branchesInCategory = categorizedBranches[categoryKey] || [];
            if (branchesInCategory.length === 0) return null;

            const isExpanded = expandedCategories.has(categoryKey);
            const CategoryIcon = categoryInfo.icon;

            return (
              <div key={categoryKey} className="mb-6">
                {/* Category Header */}
                <div
                  className={`card p-4 cursor-pointer ${categoryInfo.bgColor} ${categoryInfo.borderColor}`}
                  onClick={() => toggleCategory(categoryKey)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      {isExpanded ? (
                        <ChevronDown className="h-5 w-5" />
                      ) : (
                        <ChevronRight className="h-5 w-5" />
                      )}
                      <CategoryIcon
                        className={`h-5 w-5 ${categoryInfo.color}`}
                      />
                      <h2 className="text-lg font-semibold">
                        {categoryInfo.title}
                      </h2>
                      <span className="badge bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
                        {branchesInCategory.length}
                      </span>
                    </div>
                    {isExpanded && (
                      <div
                        className="flex items-center space-x-2"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          onClick={() => selectAllInCategory(categoryKey)}
                          className="text-sm text-blue-600 hover:text-blue-800"
                        >
                          Select All
                        </button>
                        <span className="text-gray-400">|</span>
                        <button
                          onClick={() => deselectAllInCategory(categoryKey)}
                          className="text-sm text-blue-600 hover:text-blue-800"
                        >
                          Deselect All
                        </button>
                      </div>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 ml-8">
                    {categoryInfo.description}
                  </p>
                </div>

                {/* Branches in Category */}
                {isExpanded && (
                  <div className="mt-2 space-y-2">
                    {branchesInCategory.map((branch) => (
                      <BranchCard
                        key={branch.name}
                        branch={branch}
                        isSelected={selectedBranches.has(branch.name)}
                        onToggleSelect={() =>
                          toggleBranchSelection(branch.name)
                        }
                        onDelete={(includeRemote) =>
                          handleDelete([branch.name], includeRemote)
                        }
                        onViewDiff={(prNumber) => viewDiff(branch, prNumber)}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          },
        )}

        {/* Empty State */}
        {!loading && branches.length === 0 && (
          <div className="text-center py-12">
            <GitBranch className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">
              No branches found
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mt-2">
              All your branches are up to date or there are no local branches to
              analyze.
            </p>
            {repoInfo && (
              <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">
                <p>
                  Repository: <span className="font-mono">{repoInfo.path}</span>
                </p>
                <p>
                  Main branch:{" "}
                  <span className="font-mono">{repoInfo.main_branch}</span>
                </p>
                {repoInfo.total_branches === 0 ? (
                  <p className="mt-2 text-yellow-600 dark:text-yellow-400">
                    No branches found in this repository. Make sure you're in
                    the correct directory.
                  </p>
                ) : (
                  <p>Total branches found: {repoInfo.total_branches}</p>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Diff Viewer Modal */}
      {showDiffViewer && diffViewerData && (
        <DiffViewer
          data={diffViewerData}
          onClose={() => setShowDiffViewer(false)}
        />
      )}

      {/* Confirmation Dialog */}
      <ConfirmDialog
        open={confirmDialog.open}
        branches={confirmDialog.branches}
        includeRemote={confirmDialog.includeRemote}
        onConfirm={confirmDelete}
        onCancel={() =>
          setConfirmDialog({ open: false, branches: [], includeRemote: false })
        }
        onToggleRemote={(value) =>
          setConfirmDialog((prev) => ({ ...prev, includeRemote: value }))
        }
      />
    </div>
  );
}

export default App;
