import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import FileCard from "./components/FileCard";
import EmptyState from "./components/EmptyState";
import DropZone from "./components/DropZone";
import UploadProgress from "./components/UploadProgress";
import ContextMenu from "./components/ContextMenu";
import FilePreviewModal from "./components/FilePreviewModal";
import NewFolderModal from "./components/NewFolderModal";
import RenameModal from "./components/RenameModal";
import MoveModal from "./components/MoveModal";
import FileDetailsPanel from "./components/FileDetailsPanel";
import TrashView from "./components/TrashView";
import ActivityLog from "./components/ActivityLog";
import StorageChart from "./components/StorageChart";

export default function App() {
    // Core state
    const [view, setView] = useState("grid");
    const [currentPath, setCurrentPath] = useState([]);
    const [files, setFiles] = useState([]);
    const [searchQuery, setSearchQuery] = useState("");
    const [isDragging, setIsDragging] = useState(false);
    const [uploadProgress, setUploadProgress] = useState({});

    // View/Navigation state
    const [currentView, setCurrentView] = useState("home");
    const [theme, setTheme] = useState("dark");
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

    // Feature state
    const [sortBy, setSortBy] = useState("name");
    const [starredIds, setStarredIds] = useState(new Set());
    const [trashedFiles, setTrashedFiles] = useState([]);
    const [activityLog, setActivityLog] = useState([]);

    // Selection state
    const [isMultiSelect, setIsMultiSelect] = useState(false);
    const [selectedIds, setSelectedIds] = useState(new Set());

    // Modal/Panel state
    const [contextMenu, setContextMenu] = useState(null);
    const [previewFile, setPreviewFile] = useState(null);
    const [detailsFile, setDetailsFile] = useState(null);
    const [showNewFolderModal, setShowNewFolderModal] = useState(false);
    const [renameFile, setRenameFile] = useState(null);
    const [moveFile, setMoveFile] = useState(null);

    /* ---------------- INITIAL DATA ---------------- */
    useEffect(() => {
        const now = Date.now();
        setFiles([
            { id: "1", name: "Project.pdf", type: "pdf", size: 2400000, path: [], createdAt: now - 86400000 },
            { id: "2", name: "photo.jpg", type: "image", size: 3100000, path: [], createdAt: now - 172800000 },
            { id: "3", name: "Videos", type: "folder", path: [], createdAt: now - 259200000 },
            { id: "4", name: "Docs", type: "folder", path: [], createdAt: now - 345600000 },
            { id: "5", name: "demo.mp4", type: "video", size: 15000000, path: ["Videos"], createdAt: now - 432000000 },
            { id: "6", name: "notes.txt", type: "text", size: 4000, path: ["Docs"], createdAt: now - 518400000 },
            { id: "7", name: "presentation.pdf", type: "pdf", size: 5200000, path: [], createdAt: now - 3600000 },
            { id: "8", name: "screenshot.jpg", type: "image", size: 1800000, path: [], createdAt: now - 7200000 },
        ]);
    }, []);

    /* ---------------- THEME ---------------- */
    useEffect(() => {
        document.documentElement.setAttribute("data-theme", theme);
    }, [theme]);

    /* ---------------- KEYBOARD SHORTCUTS ---------------- */
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === "Escape") {
                setContextMenu(null);
                setPreviewFile(null);
                setDetailsFile(null);
                setShowNewFolderModal(false);
                setRenameFile(null);
                setMoveFile(null);
                setIsMultiSelect(false);
                setSelectedIds(new Set());
            }

            if (e.key === "Delete" && selectedIds.size > 0) {
                selectedIds.forEach((id) => handleTrash(id));
                setSelectedIds(new Set());
                setIsMultiSelect(false);
            }

            if (e.ctrlKey && e.key === "a" && currentView === "home") {
                e.preventDefault();
                setIsMultiSelect(true);
                const allIds = new Set(filteredFiles.map((f) => f.id));
                setSelectedIds(allIds);
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [selectedIds, currentView]);

    /* ---------------- ACTIVITY LOG HELPER ---------------- */
    const logActivity = (action, fileName) => {
        setActivityLog((prev) => [
            { action, fileName, timestamp: Date.now() },
            ...prev.slice(0, 49),
        ]);
    };

    /* ---------------- UPLOAD ---------------- */
    const handleUpload = (fileList) => {
        Array.from(fileList).forEach((file, i) => {
            const id = Date.now() + i;
            let progress = 0;

            setUploadProgress((p) => ({
                ...p,
                [id]: { name: file.name, progress: 0 },
            }));

            const interval = setInterval(() => {
                progress += 10;
                setUploadProgress((p) => ({
                    ...p,
                    [id]: { name: file.name, progress },
                }));

                if (progress >= 100) {
                    clearInterval(interval);
                    setUploadProgress((p) => {
                        const copy = { ...p };
                        delete copy[id];
                        return copy;
                    });

                    const newFile = {
                        id: id.toString(),
                        name: file.name,
                        type: file.type.startsWith("image/")
                            ? "image"
                            : file.type.startsWith("video/")
                                ? "video"
                                : file.type === "application/pdf"
                                    ? "pdf"
                                    : "text",
                        size: file.size,
                        path: currentPath,
                        blob: file,
                        createdAt: Date.now(),
                    };

                    setFiles((f) => [newFile, ...f]);
                    logActivity("upload", file.name);
                }
            }, 120);
        });
    };

    /* ---------------- DOWNLOAD ---------------- */
    const downloadFile = (file) => {
        if (!file.blob) return;
        const url = URL.createObjectURL(file.blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = file.name;
        a.click();
        URL.revokeObjectURL(url);
        logActivity("download", file.name);
    };

    /* ---------------- CREATE FOLDER ---------------- */
    const handleCreateFolder = (name) => {
        const newFolder = {
            id: Date.now().toString(),
            name,
            type: "folder",
            path: currentPath,
            createdAt: Date.now(),
        };
        setFiles((f) => [newFolder, ...f]);
        logActivity("create_folder", name);
    };

    /* ---------------- RENAME ---------------- */
    const handleRename = (id, newName) => {
        setFiles((f) =>
            f.map((file) => (file.id === id ? { ...file, name: newName } : file))
        );
        const file = files.find((f) => f.id === id);
        if (file) logActivity("rename", `${file.name} → ${newName}`);
    };

    /* ---------------- STAR/UNSTAR ---------------- */
    const handleStar = (id) => {
        setStarredIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
                const file = files.find((f) => f.id === id);
                if (file) logActivity("star", file.name);
            }
            return next;
        });
    };

    /* ---------------- TRASH ---------------- */
    const handleTrash = (id) => {
        const file = files.find((f) => f.id === id);
        if (file) {
            setFiles((f) => f.filter((item) => item.id !== id));
            setTrashedFiles((t) => [file, ...t]);
            setStarredIds((s) => {
                const next = new Set(s);
                next.delete(id);
                return next;
            });
            logActivity("trash", file.name);
            setDetailsFile(null);
        }
    };

    const handleRestore = (id) => {
        const file = trashedFiles.find((f) => f.id === id);
        if (file) {
            setTrashedFiles((t) => t.filter((item) => item.id !== id));
            setFiles((f) => [file, ...f]);
            logActivity("restore", file.name);
        }
    };

    const handleDeletePermanently = (id) => {
        setTrashedFiles((t) => t.filter((item) => item.id !== id));
    };

    const handleEmptyTrash = () => {
        setTrashedFiles([]);
    };

    /* ---------------- MOVE ---------------- */
    const handleMove = (id, newPath) => {
        setFiles((f) =>
            f.map((file) => (file.id === id ? { ...file, path: newPath } : file))
        );
    };

    /* ---------------- COPY ---------------- */
    const handleCopy = (file) => {
        const copy = {
            ...file,
            id: Date.now().toString(),
            name: `${file.name} (copy)`,
            createdAt: Date.now(),
        };
        setFiles((f) => [copy, ...f]);
    };

    /* ---------------- SELECTION ---------------- */
    const handleSelect = (id) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    };

    /* ---------------- CONTEXT MENU ---------------- */
    const handleContextMenu = (e, file) => {
        setContextMenu({
            x: e.clientX,
            y: e.clientY,
            file,
        });
    };

    /* ---------------- FILTER & SORT ---------------- */
    const getFilteredFiles = () => {
        let result = files;

        if (currentView === "starred") {
            result = result.filter((f) => starredIds.has(f.id));
        } else if (currentView === "recent") {
            result = [...result].sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0)).slice(0, 20);
        } else if (currentView === "home") {
            result = result.filter((f) => JSON.stringify(f.path) === JSON.stringify(currentPath));
        }

        if (searchQuery) {
            result = result.filter((f) =>
                f.name.toLowerCase().includes(searchQuery.toLowerCase())
            );
        }

        result = [...result].sort((a, b) => {
            if (a.type === "folder" && b.type !== "folder") return -1;
            if (a.type !== "folder" && b.type === "folder") return 1;

            switch (sortBy) {
                case "name":
                    return a.name.localeCompare(b.name);
                case "date":
                    return (b.createdAt || 0) - (a.createdAt || 0);
                case "size":
                    return (b.size || 0) - (a.size || 0);
                case "type":
                    return a.type.localeCompare(b.type);
                default:
                    return 0;
            }
        });

        return result;
    };

    const filteredFiles = getFilteredFiles();

    // Get recent files (top 4 most recent non-folder files)
    const recentFiles = [...files]
        .filter(f => f.type !== "folder")
        .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0))
        .slice(0, 4);

    /* ---------------- NAVIGATION ---------------- */
    const handleNavigate = (viewId) => {
        setCurrentView(viewId);
        if (viewId === "home") {
            setCurrentPath([]);
        }
        setSearchQuery("");
        setSelectedIds(new Set());
        setIsMultiSelect(false);
    };

    const handleFileClick = (file) => {
        if (file.type === "folder") {
            setCurrentPath([...currentPath, file.name]);
            setCurrentView("home");
        }
    };

    const handleFileDoubleClick = (file) => {
        if (file.type !== "folder") {
            setPreviewFile(file);
        }
    };

    const handleNavigateToPath = (path) => {
        setCurrentPath(path);
        setCurrentView("home");
    };

    /* ---------------- PREVIEW NAVIGATION ---------------- */
    const previewableFiles = filteredFiles.filter((f) => f.type !== "folder" && (f.blob || f.previewUrl));
    const currentPreviewIndex = previewableFiles.findIndex((f) => f.id === previewFile?.id);

    const handlePreviewNavigate = (direction) => {
        if (previewableFiles.length === 0) return;
        let newIndex = currentPreviewIndex;
        if (direction === "prev") {
            newIndex = currentPreviewIndex > 0 ? currentPreviewIndex - 1 : previewableFiles.length - 1;
        } else {
            newIndex = currentPreviewIndex < previewableFiles.length - 1 ? currentPreviewIndex + 1 : 0;
        }
        setPreviewFile(previewableFiles[newIndex]);
    };

    /* ---------------- VIEW TITLES ---------------- */
    const viewTitles = {
        home: null,
        starred: "Starred",
        recent: "Recent",
        activity: "Activity",
        trash: "Trash",
    };

    /* ---------------- DRAG HANDLERS ---------------- */
    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);
        handleUpload(e.dataTransfer.files);
    };

    // Show recent section only on home view at root level
    const showRecentSection = currentView === "home" && currentPath.length === 0 && recentFiles.length > 0;

    /* ---------------- RENDER ---------------- */
    return (
        <div className={`app-container ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
            <Sidebar
                currentView={currentView}
                onNavigate={handleNavigate}
                onNewFolder={() => setShowNewFolderModal(true)}
                theme={theme}
                onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
                files={files}
                trashedCount={trashedFiles.length}
                starredCount={starredIds.size}
                isCollapsed={sidebarCollapsed}
                onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
            />

            <main
                className={`main-area ${detailsFile ? "with-details" : ""}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
            >
                {currentView !== "activity" && currentView !== "trash" && (
                    <Header
                        currentPath={currentPath}
                        searchQuery={searchQuery}
                        onSearchChange={setSearchQuery}
                        view={view}
                        onViewChange={setView}
                        onUpload={handleUpload}
                        onNavigateToPath={handleNavigateToPath}
                        sortBy={sortBy}
                        onSortChange={setSortBy}
                        isMultiSelect={isMultiSelect}
                        onToggleMultiSelect={() => {
                            setIsMultiSelect(!isMultiSelect);
                            if (isMultiSelect) setSelectedIds(new Set());
                        }}
                        selectedCount={selectedIds.size}
                        viewTitle={viewTitles[currentView]}
                    />
                )}

                <div className="file-area">
                    {isDragging && <DropZone />}

                    {currentView === "trash" ? (
                        <TrashView
                            trashedFiles={trashedFiles}
                            onRestore={handleRestore}
                            onDeletePermanently={handleDeletePermanently}
                            onEmptyTrash={handleEmptyTrash}
                        />
                    ) : currentView === "activity" ? (
                        <ActivityLog activities={activityLog} />
                    ) : (
                        <div className="file-content-wrapper">
                            {/* Main files area */}
                            <div className="files-main">
                                {/* Recent Files Section */}
                                {showRecentSection && (
                                    <section className="recent-section">
                                        <h2 className="section-title">Recent Files</h2>
                                        <div className="recent-files-grid">
                                            {recentFiles.map((file, index) => (
                                                <FileCard
                                                    key={file.id}
                                                    file={file}
                                                    view="grid"
                                                    index={index}
                                                    onClick={() => handleFileClick(file)}
                                                    onDoubleClick={() => handleFileDoubleClick(file)}
                                                    onDownload={downloadFile}
                                                    onContextMenu={handleContextMenu}
                                                    isStarred={starredIds.has(file.id)}
                                                    isSelected={selectedIds.has(file.id)}
                                                    isMultiSelect={isMultiSelect}
                                                    onSelect={handleSelect}
                                                />
                                            ))}
                                        </div>
                                    </section>
                                )}

                                {/* All Files Section */}
                                {showRecentSection && <h2 className="section-title">All Files</h2>}

                                {filteredFiles.length === 0 ? (
                                    <EmptyState />
                                ) : (
                                    <div className={`file-grid ${view === "grid" ? "grid-view" : "list-view"}`}>
                                        {filteredFiles.map((file, index) => (
                                            <FileCard
                                                key={file.id}
                                                file={file}
                                                view={view}
                                                index={index}
                                                onClick={() => handleFileClick(file)}
                                                onDoubleClick={() => handleFileDoubleClick(file)}
                                                onDownload={downloadFile}
                                                onContextMenu={handleContextMenu}
                                                isStarred={starredIds.has(file.id)}
                                                isSelected={selectedIds.has(file.id)}
                                                isMultiSelect={isMultiSelect}
                                                onSelect={handleSelect}
                                            />
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* Floating Storage Panel (when sidebar collapsed) */}
                            {sidebarCollapsed && (
                                <aside className="floating-storage">
                                    <StorageChart files={files} />
                                </aside>
                            )}
                        </div>
                    )}
                </div>

                <UploadProgress uploads={uploadProgress} />
            </main>

            {/* Details Panel */}
            {detailsFile && (
                <FileDetailsPanel
                    file={detailsFile}
                    isStarred={starredIds.has(detailsFile.id)}
                    onClose={() => setDetailsFile(null)}
                    onDownload={downloadFile}
                    onStar={handleStar}
                    onTrash={handleTrash}
                />
            )}

            {/* Context Menu */}
            {contextMenu && (
                <ContextMenu
                    x={contextMenu.x}
                    y={contextMenu.y}
                    file={contextMenu.file}
                    isStarred={starredIds.has(contextMenu.file.id)}
                    onClose={() => setContextMenu(null)}
                    onPreview={() => setPreviewFile(contextMenu.file)}
                    onDownload={() => downloadFile(contextMenu.file)}
                    onStar={() => handleStar(contextMenu.file.id)}
                    onRename={() => setRenameFile(contextMenu.file)}
                    onMove={() => setMoveFile(contextMenu.file)}
                    onCopy={() => handleCopy(contextMenu.file)}
                    onTrash={() => handleTrash(contextMenu.file.id)}
                    onDetails={() => setDetailsFile(contextMenu.file)}
                />
            )}

            {/* Preview Modal */}
            {previewFile && (
                <FilePreviewModal
                    file={previewFile}
                    files={previewableFiles}
                    onClose={() => setPreviewFile(null)}
                    onDownload={downloadFile}
                    onNavigate={previewableFiles.length > 1 ? handlePreviewNavigate : null}
                />
            )}

            {/* New Folder Modal */}
            {showNewFolderModal && (
                <NewFolderModal
                    onClose={() => setShowNewFolderModal(false)}
                    onCreate={handleCreateFolder}
                />
            )}

            {/* Rename Modal */}
            {renameFile && (
                <RenameModal
                    file={renameFile}
                    onClose={() => setRenameFile(null)}
                    onRename={handleRename}
                />
            )}

            {/* Move Modal */}
            {moveFile && (
                <MoveModal
                    file={moveFile}
                    folders={files.filter((f) => f.type === "folder")}
                    currentPath={moveFile.path}
                    onClose={() => setMoveFile(null)}
                    onMove={handleMove}
                />
            )}
        </div>
    );
}
