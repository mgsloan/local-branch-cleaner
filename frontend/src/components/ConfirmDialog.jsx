import React, { useEffect, useRef } from "react";
import { AlertTriangle, X, GitBranch, Cloud } from "lucide-react";

const ConfirmDialog = ({
  open,
  branches,
  branchesWithRemotes,
  includeRemote,
  onConfirm,
  onCancel,
  onToggleRemote,
}) => {
  const deleteButtonRef = useRef(null);

  // Handle keyboard shortcuts
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e) => {
      // Don't handle shortcuts if any modifier keys are held
      if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) {
        return;
      }

      switch (e.key) {
        case "Enter":
          e.preventDefault();
          e.stopPropagation();
          onConfirm();
          break;
        case "Escape":
          e.preventDefault();
          e.stopPropagation();
          onCancel();
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onConfirm, onCancel]);

  // Focus the delete button when dialog opens
  useEffect(() => {
    if (open && deleteButtonRef.current) {
      deleteButtonRef.current.focus();
    }
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
        {/* Background overlay */}
        <div
          className="fixed inset-0 transition-opacity bg-gray-500 bg-opacity-75"
          onClick={onCancel}
        />

        {/* Modal panel */}
        <div className="inline-block overflow-hidden text-left align-bottom transition-all transform bg-white rounded-lg shadow-xl sm:my-8 sm:align-middle sm:max-w-lg sm:w-full dark:bg-gray-800">
          <div className="px-4 pt-5 pb-4 bg-white dark:bg-gray-800 sm:p-6 sm:pb-4">
            <div className="sm:flex sm:items-start">
              <div className="flex items-center justify-center flex-shrink-0 w-12 h-12 mx-auto bg-red-100 rounded-full sm:mx-0 sm:h-10 sm:w-10 dark:bg-red-900/20">
                <AlertTriangle className="w-6 h-6 text-red-600 dark:text-red-400" />
              </div>
              <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-white">
                  Delete{" "}
                  {branches.length === 1
                    ? "Branch"
                    : `${branches.length} Branches`}
                </h3>
                <div className="mt-2">
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Are you sure you want to delete{" "}
                    {branches.length === 1 ? "this branch" : "these branches"}?
                    This action cannot be undone.
                  </p>
                  <div className="mt-3 space-y-1">
                    {branches.map((branch) => (
                      <div
                        key={branch}
                        className="text-sm font-mono bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded"
                      >
                        {branch}
                      </div>
                    ))}
                  </div>
                  {branchesWithRemotes.length > 0 && (
                    <div className="mt-4">
                      <label className="flex items-center space-x-2 text-sm">
                        <input
                          type="checkbox"
                          checked={includeRemote}
                          onChange={(e) => onToggleRemote(e.target.checked)}
                          className="h-4 w-4 text-red-600 rounded border-gray-300 focus:ring-red-500"
                        />
                        <span className="text-gray-700 dark:text-gray-300">
                          Also delete remote{" "}
                          {branchesWithRemotes.length === 1
                            ? "branch"
                            : "branches"}
                        </span>
                      </label>
                      {branchesWithRemotes.length > 0 && (
                        <div className="mt-2 ml-6 space-y-2">
                          <div className="text-xs text-gray-600 dark:text-gray-400">
                            {branchesWithRemotes.length} remote{" "}
                            {branchesWithRemotes.length === 1
                              ? "branch exists"
                              : "branches exist"}
                            :
                            <div className="mt-1 flex flex-wrap gap-1">
                              {branchesWithRemotes.map((branch) => (
                                <span
                                  key={branch}
                                  className="font-mono text-gray-700 dark:text-gray-300"
                                >
                                  origin/{branch}
                                </span>
                              ))}
                            </div>
                          </div>
                          {includeRemote && (
                            <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/10 rounded border border-red-200 dark:border-red-800">
                              <p className="text-xs text-red-700 dark:text-red-300 font-medium flex items-center space-x-1">
                                <Cloud className="h-3 w-3" />
                                <span>
                                  These remote branches will be deleted
                                </span>
                              </p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
          <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 sm:px-6 sm:flex sm:flex-row-reverse">
            <button
              ref={deleteButtonRef}
              type="button"
              onClick={onConfirm}
              className="inline-flex justify-center w-full px-4 py-2 text-base font-medium text-white bg-red-600 border border-transparent rounded-md shadow-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:ml-3 sm:w-auto sm:text-sm"
            >
              Delete
            </button>
            <button
              type="button"
              onClick={onCancel}
              className="inline-flex justify-center w-full px-4 py-2 mt-3 text-base font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;
