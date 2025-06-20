import React from "react";
import { formatDistanceToNow } from "date-fns";
import {
  GitBranch,
  GitMerge,
  GitPullRequest,
  Trash2,
  Eye,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Clock,
  User,
} from "lucide-react";

const BranchCard = ({
  branch,
  isSelected,
  onToggleSelect,
  onDelete,
  onViewDiff,
}) => {
  const getPRIcon = (state) => {
    switch (state) {
      case "MERGED":
        return <GitMerge className="h-4 w-4 text-github-merged" />;
      case "OPEN":
        return <GitPullRequest className="h-4 w-4 text-github-open" />;
      case "CLOSED":
        return <XCircle className="h-4 w-4 text-github-closed" />;
      default:
        return <GitBranch className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStatusIcon = () => {
    switch (branch.status) {
      case "safe_to_delete":
        return <CheckCircle2 className="h-5 w-5 text-green-600" />;
      case "review_required":
        return <AlertCircle className="h-5 w-5 text-yellow-600" />;
      case "closed_pr":
        return <XCircle className="h-5 w-5 text-red-600" />;
      case "active":
        return <GitPullRequest className="h-5 w-5 text-blue-600" />;
      default:
        return <GitBranch className="h-5 w-5 text-gray-400" />;
    }
  };

  const handleDeleteClick = () => {
    // Always use the custom confirmation dialog
    onDelete(false);
  };

  const mergedPR = branch.prs?.find((pr) => pr.state === "MERGED");

  return (
    <div className={`card p-4 ${isSelected ? "ring-2 ring-blue-500" : ""}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3 flex-1">
          {/* Selection Checkbox */}
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onToggleSelect}
            className="mt-1 h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
          />

          {/* Status Icon */}
          <div className="flex-shrink-0 mt-0.5">{getStatusIcon()}</div>

          {/* Branch Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-medium text-gray-900 dark:text-white truncate">
                {branch.name}
              </h3>
              {branch.has_differences && (
                <span className="badge bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-200">
                  Has differences
                </span>
              )}
            </div>

            {/* PR List */}
            {branch.prs && branch.prs.length > 0 && (
              <div className="mt-2 space-y-1">
                {branch.prs.map((pr) => (
                  <div
                    key={pr.number}
                    className="flex items-center space-x-2 text-sm"
                  >
                    {getPRIcon(pr.state)}
                    <a
                      href={pr.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                    >
                      #{pr.number}
                    </a>
                    <span className="text-gray-600 dark:text-gray-400 truncate">
                      {pr.title}
                    </span>
                    <ExternalLink className="h-3 w-3 text-gray-400 flex-shrink-0" />
                  </div>
                ))}
              </div>
            )}

            {/* Diff Stats */}
            {branch.diff_stats && (
              <div className="mt-2 flex items-center space-x-3 text-sm text-gray-600 dark:text-gray-400">
                <span className="text-green-600 dark:text-green-400">
                  +{branch.diff_stats.additions}
                </span>
                <span className="text-red-600 dark:text-red-400">
                  -{branch.diff_stats.deletions}
                </span>
                <span>
                  {branch.diff_stats.files_changed}{" "}
                  {branch.diff_stats.files_changed === 1 ? "file" : "files"}
                </span>
              </div>
            )}

            {/* Last Commit Info */}
            <div className="mt-2 flex items-center space-x-4 text-xs text-gray-500 dark:text-gray-400">
              {branch.last_commit_date && (
                <div className="flex items-center space-x-1">
                  <Clock className="h-3 w-3" />
                  <span>
                    {formatDistanceToNow(new Date(branch.last_commit_date), {
                      addSuffix: true,
                    })}
                  </span>
                </div>
              )}
              {branch.last_commit_author && (
                <div className="flex items-center space-x-1">
                  <User className="h-3 w-3" />
                  <span>{branch.last_commit_author}</span>
                </div>
              )}
            </div>

            {/* Error Message */}
            {branch.error && (
              <div className="mt-2 text-sm text-red-600 dark:text-red-400">
                Error: {branch.error}
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center space-x-2 ml-4">
          {branch.has_differences && mergedPR && (
            <button
              onClick={() => onViewDiff(mergedPR.number)}
              className="p-2 text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
              title="View differences"
            >
              <Eye className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={handleDeleteClick}
            className="p-2 text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
            title="Delete branch"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default BranchCard;
