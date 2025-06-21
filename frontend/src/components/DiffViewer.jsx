import React, { useState, useMemo, useEffect } from "react";
import ReactDiffViewer from "react-diff-viewer-continued";
import {
  X,
  FileText,
  GitBranch,
  GitMerge,
  ToggleLeft,
  ToggleRight,
  ChevronDown,
  ChevronRight,
  File,
  FilePlus,
  FileMinus,
  FileEdit,
  Terminal,
  Copy,
} from "lucide-react";

const DiffViewer = ({ data, onClose }) => {
  const [viewMode, setViewMode] = useState("unified"); // 'split' or 'unified'
  const [expandedFiles, setExpandedFiles] = useState(new Set());
  const [selectedFile, setSelectedFile] = useState(null);
  const [showCommands, setShowCommands] = useState(false);

  // Handle browser back button
  React.useEffect(() => {
    const handlePopState = (e) => {
      e.preventDefault();
      onClose();
    };

    // Push a new state when the viewer opens
    window.history.pushState({ diffViewer: true }, "");
    window.addEventListener("popstate", handlePopState);

    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, [onClose]);

  // Parse the diff data
  const parsedDiffs = useMemo(() => {
    if (!data) return { files: [], hasChanges: false };

    const branchFiles = new Map(data.branch_files.map((f) => [f.filename, f]));
    const prFiles = new Map(data.pr_files.map((f) => [f.filename, f]));

    // Get all unique filenames
    // Files are already filtered by the backend to only include those with differences
    const allFiles = new Set();
    data.branch_files.forEach((f) => allFiles.add(f.filename));
    data.pr_files.forEach((f) => allFiles.add(f.filename));

    const files = Array.from(allFiles).map((filename) => {
      const branchFile = branchFiles.get(filename);
      const prFile = prFiles.get(filename);

      let status = "modified";
      if (!prFile) {
        status = "added-in-branch";
      } else if (!branchFile) {
        status = "removed-in-branch";
      } else if (branchFile.status === "A") {
        status = "added";
      } else if (branchFile.status === "D") {
        status = "deleted";
      }

      return {
        filename,
        status,
        branchStatus: branchFile?.status,
        prStatus: prFile?.status,
      };
    });

    // Sort files by name
    files.sort((a, b) => a.filename.localeCompare(b.filename));

    return {
      files,
      hasChanges: files.length > 0,
    };
  }, [data]);

  // Auto-select first file when data changes
  React.useEffect(() => {
    if (parsedDiffs.files.length > 0 && !selectedFile) {
      setSelectedFile(parsedDiffs.files[0].filename);
    }
  }, [parsedDiffs.files, selectedFile]);

  // Keyboard navigation for files
  useEffect(() => {
    const handleKeyPress = (e) => {
      // Don't handle shortcuts if any modifier keys are held
      if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) {
        return;
      }

      const currentIndex = parsedDiffs.files.findIndex(
        (f) => f.filename === selectedFile,
      );

      switch (e.key) {
        case "j":
          e.preventDefault();
          if (currentIndex < parsedDiffs.files.length - 1) {
            setSelectedFile(parsedDiffs.files[currentIndex + 1].filename);
          }
          break;
        case "k":
          e.preventDefault();
          if (currentIndex > 0) {
            setSelectedFile(parsedDiffs.files[currentIndex - 1].filename);
          }
          break;
        case "g":
          e.preventDefault();
          setShowCommands(true);
          // Select the git commands text after a short delay
          setTimeout(() => {
            const commandsElement = document.querySelector(
              "[data-git-commands]",
            );
            if (commandsElement) {
              const selection = window.getSelection();
              const range = document.createRange();
              range.selectNodeContents(commandsElement);
              selection.removeAllRanges();
              selection.addRange(range);
            }
          }, 100);
          break;
        case "u":
          e.preventDefault();
          onClose();
          break;
        case "v":
          e.preventDefault();
          setViewMode((prev) => (prev === "split" ? "unified" : "split"));
          break;
        case "o":
          e.preventDefault();
          if (!data.is_merge_base_diff) {
            const pr = data.branch.prs?.find((p) => p.number === data.prNumber);
            if (pr && pr.url) {
              window.open(pr.url, "_blank");
            }
          }
          break;
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [selectedFile, parsedDiffs.files, onClose, data]);

  const getFileIcon = (status) => {
    switch (status) {
      case "added":
      case "added-in-branch":
        return <FilePlus className="h-4 w-4 text-green-600" />;
      case "deleted":
      case "removed-in-branch":
        return <FileMinus className="h-4 w-4 text-red-600" />;
      default:
        return <FileEdit className="h-4 w-4 text-yellow-600" />;
    }
  };

  const getFileStatusText = (file) => {
    switch (file.status) {
      case "added-in-branch":
        return "Only in branch";
      case "removed-in-branch":
        return "Only in PR";
      case "added":
        return "Added";
      case "deleted":
        return "Deleted";
      default:
        return "Modified";
    }
  };

  const toggleFile = (filename) => {
    setExpandedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) {
        next.delete(filename);
      } else {
        next.add(filename);
      }
      return next;
    });
  };

  const extractFileDiff = (fullDiff, filename) => {
    // Simple extraction - in production, use a proper diff parser
    const lines = fullDiff.split("\n");
    const fileDiffs = [];
    let currentFile = null;
    let currentDiff = [];

    for (const line of lines) {
      if (line.startsWith("diff --git")) {
        if (currentFile && currentDiff.length > 0) {
          fileDiffs.push({ file: currentFile, diff: currentDiff.join("\n") });
        }
        // Extract filename from diff header
        const match = line.match(/diff --git a\/(.*) b\/(.*)/);
        currentFile = match ? match[2] : null;
        currentDiff = [line];
      } else if (currentFile) {
        currentDiff.push(line);
      }
    }

    if (currentFile && currentDiff.length > 0) {
      fileDiffs.push({ file: currentFile, diff: currentDiff.join("\n") });
    }

    const fileDiff = fileDiffs.find((fd) => fd.file === filename);
    return fileDiff ? fileDiff.diff : "";
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  const gitCommands = {
    branch: `git diff ${data.git_commands?.branch_merge_base || "<merge-base>"}..${data.branch.name}`,
    pr: `git diff ${data.git_commands?.pr_merge_base || "<pr-parent>"}..${data.git_commands?.merge_commit || "<merge-commit>"}`,
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black bg-opacity-50">
      <div className="absolute inset-4 flex flex-col bg-white dark:bg-gray-900 rounded-lg shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-4">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white flex items-center space-x-2">
              <GitBranch className="h-5 w-5" />
              <span>{data.branch.name}</span>
              <span className="text-gray-500">vs</span>
              {data.is_merge_base_diff ? (
                <>
                  <GitBranch className="h-5 w-5" />
                  <span>merge base</span>
                </>
              ) : (
                <>
                  <GitMerge className="h-5 w-5 text-github-merged" />
                  <a
                    href={
                      data.branch.prs?.find((pr) => pr.number === data.prNumber)
                        ?.url || `#${data.prNumber}`
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                  >
                    PR #{data.prNumber}
                  </a>
                </>
              )}
            </h2>
          </div>
          <div className="flex items-center space-x-4">
            {/* Git Commands Toggle */}
            <button
              onClick={() => setShowCommands(!showCommands)}
              className="flex items-center space-x-2 px-3 py-1 rounded-md bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700"
            >
              <Terminal className="h-4 w-4" />
              <span className="text-sm">Git Commands</span>
              <kbd className="ml-1 text-xs px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">
                G
              </kbd>
            </button>
            {/* View Mode Toggle */}
            <div className="flex items-center space-x-2">
              <button
                onClick={() =>
                  setViewMode(viewMode === "split" ? "unified" : "split")
                }
                className="flex items-center space-x-2 px-3 py-1 rounded-md bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700"
              >
                {viewMode === "split" ? (
                  <>
                    <ToggleRight className="h-4 w-4" />
                    <span className="text-sm">Split View</span>
                  </>
                ) : (
                  <>
                    <ToggleLeft className="h-4 w-4" />
                    <span className="text-sm">Unified View</span>
                  </>
                )}
                <kbd className="ml-1 text-xs px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">
                  V
                </kbd>
              </button>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md flex items-center space-x-1"
              title="Close (U)"
            >
              <X className="h-5 w-5" />
              <kbd className="text-xs px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">
                U
              </kbd>
            </button>
          </div>
        </div>

        {/* Git Commands Section */}
        {showCommands && (
          <div className="px-6 py-4 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                {data.is_merge_base_diff
                  ? "Git Command to Generate This Diff"
                  : "Git Commands to Compare These Diffs"}
              </h3>
              <div className="flex items-center space-x-2">
                <pre
                  className="flex-1 text-xs bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded px-3 py-2 font-mono overflow-x-auto"
                  data-git-commands
                >
                  {data.is_merge_base_diff
                    ? `# Generate the diff
${gitCommands.branch}`
                    : `# Generate the diff files
${gitCommands.pr} > merged.diff
${gitCommands.branch} > local-branch.diff

# Compare them
diff merged.diff local-branch.diff`}
                </pre>
                <button
                  onClick={() =>
                    copyToClipboard(
                      data.is_merge_base_diff
                        ? gitCommands.branch
                        : `${gitCommands.pr} > merged.diff
${gitCommands.branch} > local-branch.diff

# Compare them
diff merged.diff local-branch.diff`,
                    )
                  }
                  className="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                  title="Copy to clipboard"
                >
                  <Copy className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* File List Sidebar */}
          <div className="w-80 border-r border-gray-200 dark:border-gray-700 overflow-y-auto">
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                  Files with Differences ({parsedDiffs.files.length})
                </h3>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  <kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">
                    j
                  </kbd>
                  /
                  <kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">
                    k
                  </kbd>{" "}
                  to navigate •{" "}
                  <kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">
                    o
                  </kbd>{" "}
                  open PR
                </div>
              </div>
              <div className="space-y-1">
                {parsedDiffs.files.map((file, index) => (
                  <div
                    key={file.filename}
                    className={`p-2 rounded-md cursor-pointer transition-colors ${
                      selectedFile === file.filename
                        ? "bg-blue-50 dark:bg-blue-900/20 ring-2 ring-blue-500"
                        : "hover:bg-gray-100 dark:hover:bg-gray-800"
                    }`}
                    onClick={() => setSelectedFile(file.filename)}
                  >
                    <div className="flex items-center space-x-2">
                      {getFileIcon(file.status)}
                      <span className="text-sm truncate flex-1">
                        {file.filename}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 ml-6">
                      {getFileStatusText(file)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Diff Content */}
          <div className="flex-1 overflow-y-auto">
            {selectedFile ? (
              <div className="p-4">
                <div className="mb-4">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white flex items-center space-x-2">
                    {getFileIcon(
                      parsedDiffs.files.find((f) => f.filename === selectedFile)
                        ?.status,
                    )}
                    <span>{selectedFile}</span>
                  </h3>
                </div>
                <div className="diff-viewer">
                  <ReactDiffViewer
                    oldValue={extractFileDiff(data.pr_diff, selectedFile)}
                    newValue={extractFileDiff(data.branch_diff, selectedFile)}
                    splitView={viewMode === "split"}
                    useDarkTheme={
                      window.matchMedia("(prefers-color-scheme: dark)").matches
                    }
                    leftTitle={
                      data.is_merge_base_diff ? "Merge Base" : "Merged PR"
                    }
                    rightTitle="Current Branch"
                    hideLineNumbers={false}
                  />
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500 dark:text-gray-400">
                <div className="text-center">
                  <FileText className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>Select a file to view differences</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DiffViewer;
