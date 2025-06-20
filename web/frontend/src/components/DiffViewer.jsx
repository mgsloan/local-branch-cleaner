import React, { useState, useMemo } from 'react'
import ReactDiffViewer from 'react-diff-viewer-continued'
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
  FileEdit
} from 'lucide-react'

const DiffViewer = ({ data, onClose }) => {
  const [viewMode, setViewMode] = useState('split') // 'split' or 'unified'
  const [expandedFiles, setExpandedFiles] = useState(new Set())
  const [selectedFile, setSelectedFile] = useState(null)

  // Parse the diff data
  const parsedDiffs = useMemo(() => {
    if (!data) return { files: [], hasChanges: false }

    const branchFiles = new Map(data.branch_files.map(f => [f.filename, f]))
    const prFiles = new Map(data.pr_files.map(f => [f.filename, f]))

    // Get all unique filenames
    const allFiles = new Set([
      ...branchFiles.keys(),
      ...prFiles.keys()
    ])

    const files = Array.from(allFiles).map(filename => {
      const branchFile = branchFiles.get(filename)
      const prFile = prFiles.get(filename)

      let status = 'modified'
      if (!prFile) {
        status = 'added-in-branch'
      } else if (!branchFile) {
        status = 'removed-in-branch'
      } else if (branchFile.status === 'A') {
        status = 'added'
      } else if (branchFile.status === 'D') {
        status = 'deleted'
      }

      return {
        filename,
        status,
        branchStatus: branchFile?.status,
        prStatus: prFile?.status
      }
    })

    // Sort files by name
    files.sort((a, b) => a.filename.localeCompare(b.filename))

    return {
      files,
      hasChanges: files.length > 0
    }
  }, [data])

  const getFileIcon = (status) => {
    switch (status) {
      case 'added':
      case 'added-in-branch':
        return <FilePlus className="h-4 w-4 text-green-600" />
      case 'deleted':
      case 'removed-in-branch':
        return <FileMinus className="h-4 w-4 text-red-600" />
      default:
        return <FileEdit className="h-4 w-4 text-yellow-600" />
    }
  }

  const getFileStatusText = (file) => {
    switch (file.status) {
      case 'added-in-branch':
        return 'Only in branch'
      case 'removed-in-branch':
        return 'Only in PR'
      case 'added':
        return 'Added'
      case 'deleted':
        return 'Deleted'
      default:
        return 'Modified'
    }
  }

  const toggleFile = (filename) => {
    setExpandedFiles(prev => {
      const next = new Set(prev)
      if (next.has(filename)) {
        next.delete(filename)
      } else {
        next.add(filename)
      }
      return next
    })
  }

  const extractFileDiff = (fullDiff, filename) => {
    // Simple extraction - in production, use a proper diff parser
    const lines = fullDiff.split('\n')
    const fileDiffs = []
    let currentFile = null
    let currentDiff = []

    for (const line of lines) {
      if (line.startsWith('diff --git')) {
        if (currentFile && currentDiff.length > 0) {
          fileDiffs.push({ file: currentFile, diff: currentDiff.join('\n') })
        }
        // Extract filename from diff header
        const match = line.match(/diff --git a\/(.*) b\/(.*)/)
        currentFile = match ? match[2] : null
        currentDiff = [line]
      } else if (currentFile) {
        currentDiff.push(line)
      }
    }

    if (currentFile && currentDiff.length > 0) {
      fileDiffs.push({ file: currentFile, diff: currentDiff.join('\n') })
    }

    const fileDiff = fileDiffs.find(fd => fd.file === filename)
    return fileDiff ? fileDiff.diff : ''
  }

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
              <GitMerge className="h-5 w-5 text-github-merged" />
              <span>PR #{data.prNumber}</span>
            </h2>
          </div>
          <div className="flex items-center space-x-4">
            {/* View Mode Toggle */}
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setViewMode(viewMode === 'split' ? 'unified' : 'split')}
                className="flex items-center space-x-2 px-3 py-1 rounded-md bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700"
              >
                {viewMode === 'split' ? (
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
              </button>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* File List Sidebar */}
          <div className="w-80 border-r border-gray-200 dark:border-gray-700 overflow-y-auto">
            <div className="p-4">
              <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3">
                Changed Files ({parsedDiffs.files.length})
              </h3>
              <div className="space-y-1">
                {parsedDiffs.files.map(file => (
                  <div
                    key={file.filename}
                    className={`p-2 rounded-md cursor-pointer transition-colors ${
                      selectedFile === file.filename
                        ? 'bg-blue-50 dark:bg-blue-900/20'
                        : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                    }`}
                    onClick={() => setSelectedFile(file.filename)}
                  >
                    <div className="flex items-center space-x-2">
                      {getFileIcon(file.status)}
                      <span className="text-sm truncate flex-1">{file.filename}</span>
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
                    {getFileIcon(parsedDiffs.files.find(f => f.filename === selectedFile)?.status)}
                    <span>{selectedFile}</span>
                  </h3>
                </div>
                <div className="diff-viewer">
                  <ReactDiffViewer
                    oldValue={extractFileDiff(data.pr_diff, selectedFile)}
                    newValue={extractFileDiff(data.branch_diff, selectedFile)}
                    splitView={viewMode === 'split'}
                    useDarkTheme={window.matchMedia('(prefers-color-scheme: dark)').matches}
                    leftTitle="Merged PR"
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
  )
}

export default DiffViewer
