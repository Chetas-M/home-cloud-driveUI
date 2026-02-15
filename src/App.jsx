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
import AuthPage from "./components/AuthPage";
import api from "./api";

export default function App() {
    // Auth state
    const [user, setUser] = useState(null);
    const [authLoading, setAuthLoading] = useState(true);

    // Core state
    const [view, setView] = useState("grid");
    const [currentPath, setCurrentPath] = useState([]);
    const [files, setFiles] = useState([]);
    const [searchQuery, setSearchQuery] = useState("");
    const [isDragging, setIsDragging] = useState(false);
    const [uploadProgress, setUploadProgress] = useState({});
    const [loading, setLoading] = useState(false);

    // View/Navigation state
    const [currentView, setCurrentView] = useState("home");
    const [theme, setTheme] = useState("dark");
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

    // Feature state
    const [sortBy, setSortBy] = useState("name");
    const [trashedFiles, setTrashedFiles] = useState([]);
    const [activityLog, setActivityLog] = useState([]);
    const [storageInfo, setStorageInfo] = useState(null);

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

    /* ---------------- AUTH CHECK ---------------- */
    useEffect(() => {
        const checkAuth = async () => {
            const token = api.getToken();
            if (token) {
                try {
                    const userData = await api.getMe();
                    setUser(userData);
                } catch (err) {
                    api.logout();
                }
            }
            setAuthLoading(false);
        };
        checkAuth();
    }, []);

    /* ---------------- LOAD FILES ---------------- */
    const loadFiles = useCallback(async () => {
        if (!user) return;
        setLoading(true);
        try {
            let data;
            if (currentView === "starred") {
                data = await api.listFiles([], { starredOnly: true });
            } else if (currentView === "trash") {
                data = await api.listFiles([], { includeTrash: true });
                data = data.filter(f => f.is_trashed);
                setTrashedFiles(data);
                setLoading(false);
                return;
            } else {
                data = await api.listFiles(currentPath);
            }
            setFiles(data.filter(f => !f.is_trashed));
        } catch (err) {
            console.error("Failed to load files:", err);
        }
        setLoading(false);
    }, [user, currentPath, currentView]);

    useEffect(() => {
        loadFiles();
    }, [loadFiles]);

    /* ---------------- LOAD ACTIVITY & STORAGE ---------------- */
    useEffect(() => {
        const loadExtra = async () => {
            if (!user) return;
            try {
                const [activities, storage] = await Promise.all([
                    api.getActivityLog(50),
                    api.getStorageInfo(),
                ]);
                setActivityLog(activities);
                setStorageInfo(storage);
            } catch (err) {
                console.error("Failed to load extra data:", err);
            }
        };
        loadExtra();
    }, [user, files]);

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

    /* ---------------- UPLOAD ---------------- */
    const handleUpload = async (fileList) => {
        const filesArray = Array.from(fileList);

        // Show progress
        filesArray.forEach((file, i) => {
            setUploadProgress((p) => ({
                ...p,
                [i]: { name: file.name, progress: 0 },
            }));
        });

        try {
            // Simulate progress
            const progressInterval = setInterval(() => {
                setUploadProgress((p) => {
                    const updated = { ...p };
                    Object.keys(updated).forEach((key) => {
                        if (updated[key].progress < 90) {
                            updated[key].progress += 10;
                        }
                    });
                    return updated;
                });
            }, 100);

            await api.uploadFiles(filesArray, currentPath);

            clearInterval(progressInterval);
            setUploadProgress({});
            loadFiles();
        } catch (err) {
            console.error("Upload failed:", err);
            setUploadProgress({});
        }
    };

    /* ---------------- DOWNLOAD ---------------- */
    const downloadFile = async (file) => {
        try {
            const blob = await api.downloadFile(file.id);
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = file.name;
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            console.error("Download failed:", err);
        }
    };

    /* ---------------- CREATE FOLDER ---------------- */
    const handleCreateFolder = async (name) => {
        try {
            await api.createFolder(name, currentPath);
            loadFiles();
        } catch (err) {
            console.error("Create folder failed:", err);
        }
    };

    /* ---------------- RENAME ---------------- */
    const handleRename = async (id, newName) => {
        try {
            await api.updateFile(id, { name: newName });
            loadFiles();
        } catch (err) {
            console.error("Rename failed:", err);
        }
    };

    /* ---------------- STAR/UNSTAR ---------------- */
    const handleStar = async (id) => {
        const file = files.find((f) => f.id === id);
        if (!file) return;
        try {
            await api.updateFile(id, { is_starred: !file.is_starred });
            loadFiles();
        } catch (err) {
            console.error("Star failed:", err);
        }
    };

    /* ---------------- TRASH ---------------- */
    const handleTrash = async (id) => {
        try {
            await api.trashFile(id);
            setDetailsFile(null);
            loadFiles();
        } catch (err) {
            console.error("Trash failed:", err);
        }
    };

    const handleRestore = async (id) => {
        try {
            await api.restoreFile(id);
            loadFiles();
            // Reload trash view
            const trashData = await api.listFiles([], { includeTrash: true });
            setTrashedFiles(trashData.filter(f => f.is_trashed));
        } catch (err) {
            console.error("Restore failed:", err);
        }
    };

    const handleDeletePermanently = async (id) => {
        try {
            await api.deleteFilePermanently(id);
            setTrashedFiles((t) => t.filter((item) => item.id !== id));
        } catch (err) {
            console.error("Delete failed:", err);
        }
    };

    const handleEmptyTrash = async () => {
        try {
            await api.emptyTrash();
            setTrashedFiles([]);
        } catch (err) {
            console.error("Empty trash failed:", err);
        }
    };

    /* ---------------- MOVE ---------------- */
    const handleMove = async (id, newPath) => {
        try {
            await api.updateFile(id, { path: newPath });
            loadFiles();
        } catch (err) {
            console.error("Move failed:", err);
        }
    };

    /* ---------------- COPY ---------------- */
    const handleCopy = (file) => {
        // For now, just show a message - would need backend support for copy
        console.log("Copy not yet implemented on backend");
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
        let result = [...files];

        // Search filter
        if (searchQuery) {
            result = result.filter((f) =>
                f.name.toLowerCase().includes(searchQuery.toLowerCase())
            );
        }

        // Sort
        result = result.sort((a, b) => {
            // Folders first
            if (a.type === "folder" && b.type !== "folder") return -1;
            if (a.type !== "folder" && b.type === "folder") return 1;

            switch (sortBy) {
                case "name":
                    return a.name.localeCompare(b.name);
                case "date":
                    return new Date(b.created_at) - new Date(a.created_at);
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
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
        .slice(0, 4);

    // Get starred files
    const starredFiles = files.filter(f => f.is_starred);

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
    const previewableFiles = filteredFiles.filter((f) => f.type !== "folder");
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
    const dragCounterRef = React.useRef(0);

    const handleDragEnter = (e) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounterRef.current++;
        if (e.dataTransfer.types.includes('Files')) {
            setIsDragging(true);
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        e.stopPropagation();
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounterRef.current--;
        if (dragCounterRef.current === 0) {
            setIsDragging(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounterRef.current = 0;
        setIsDragging(false);
        if (e.dataTransfer.files.length > 0) {
            handleUpload(e.dataTransfer.files);
        }
    };

    /* ---------------- LOGOUT ---------------- */
    const handleLogout = () => {
        api.logout();
        setUser(null);
        setFiles([]);
    };

    // Show recent section only on home view at root level
    const showRecentSection = currentView === "home" && currentPath.length === 0 && recentFiles.length > 0;

    /* ---------------- AUTH LOADING ---------------- */
    if (authLoading) {
        return (
            <div className="auth-container">
                <div className="auth-card" style={{ textAlign: 'center' }}>
                    <p>Loading...</p>
                </div>
            </div>
        );
    }

    /* ---------------- AUTH PAGE ---------------- */
    if (!user) {
        return <AuthPage onLogin={setUser} />;
    }

    /* ---------------- MAIN APP ---------------- */
    return (
        <div className={`app-container ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
            {/* Mobile sidebar backdrop */}
            <div
                className={`sidebar-backdrop ${isMobileMenuOpen ? 'visible' : ''}`}
                onClick={() => setIsMobileMenuOpen(false)}
            />

            <Sidebar
                currentView={currentView}
                onNavigate={handleNavigate}
                onNewFolder={() => setShowNewFolderModal(true)}
                theme={theme}
                onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
                files={files}
                storageInfo={storageInfo}
                trashedCount={trashedFiles.length}
                starredCount={starredFiles.length}
                isCollapsed={sidebarCollapsed}
                onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
                isMobileOpen={isMobileMenuOpen}
                onMobileClose={() => setIsMobileMenuOpen(false)}
            />

            <main
                className={`main-area ${detailsFile ? "with-details" : ""}`}
                onDragEnter={handleDragEnter}
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
                        user={user}
                        onLogout={handleLogout}
                        onMobileMenuToggle={() => setIsMobileMenuOpen(true)}
                    />
                )}

                <div className="file-area">
                    {isDragging && <DropZone />}

                    {loading ? (
                        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                            Loading files...
                        </div>
                    ) : currentView === "trash" ? (
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
                                                    isStarred={file.is_starred}
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
                                                isStarred={file.is_starred}
                                                isSelected={selectedIds.has(file.id)}
                                                isMultiSelect={isMultiSelect}
                                                onSelect={handleSelect}
                                            />
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* Floating Storage Panel (when sidebar collapsed) */}
                            {sidebarCollapsed && storageInfo && (
                                <aside className="floating-storage">
                                    <StorageChart
                                        files={files}
                                        storageInfo={storageInfo}
                                    />
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
                    isStarred={detailsFile.is_starred}
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
                    isStarred={contextMenu.file.is_starred}
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
