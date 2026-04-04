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
import AdminPanel from "./components/AdminPanel";
import ShareModal from "./components/ShareModal";
import SecurityModal from "./components/SecurityModal";
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
    const [searchResults, setSearchResults] = useState([]);
    const [searchLoading, setSearchLoading] = useState(false);
    const [searchError, setSearchError] = useState("");
    const [searchRefreshKey, setSearchRefreshKey] = useState(0);
    const [isDragging, setIsDragging] = useState(false);
    const [uploadProgress, setUploadProgress] = useState({});
    const uploadAbortRef = React.useRef(null);
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

    // Ref for stable keydown handler — avoids re-registering the global
    // listener on every render that changes files/search/sort state.
    const keydownStateRef = React.useRef({});

    // Modal/Panel state
    const [contextMenu, setContextMenu] = useState(null);
    const [previewFile, setPreviewFile] = useState(null);
    const [detailsFile, setDetailsFile] = useState(null);
    const [showNewFolderModal, setShowNewFolderModal] = useState(false);
    const [renameFile, setRenameFile] = useState(null);
    const [moveFile, setMoveFile] = useState(null);
    const [shareFile, setShareFile] = useState(null);
    const [showSecurityModal, setShowSecurityModal] = useState(false);

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

    /* ---------------- SEARCH ---------------- */
    useEffect(() => {
        if (!user) return;

        const trimmedQuery = searchQuery.trim();
        const searchEnabled = currentView !== "activity" && currentView !== "trash" && currentView !== "admin";

        if (!trimmedQuery || !searchEnabled) {
            setSearchResults([]);
            setSearchError("");
            setSearchLoading(false);
            return;
        }

        let cancelled = false;
        const timeoutId = setTimeout(async () => {
            setSearchLoading(true);
            setSearchError("");

            try {
                const results = await api.searchFiles(trimmedQuery, {
                    starredOnly: currentView === "starred",
                });
                if (!cancelled) {
                    setSearchResults(results);
                }
            } catch (err) {
                if (!cancelled) {
                    setSearchError(err.message || "Search failed");
                    setSearchResults([]);
                }
            } finally {
                if (!cancelled) {
                    setSearchLoading(false);
                }
            }
        }, 250);

        return () => {
            cancelled = true;
            clearTimeout(timeoutId);
        };
    }, [user, searchQuery, currentView, searchRefreshKey]);

    /* ---------------- LOAD ACTIVITY & STORAGE ---------------- */
    const loadExtra = useCallback(async () => {
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
    }, [user]);

    useEffect(() => {
        loadExtra();
    }, [loadExtra, files]);

    /* ---------------- THEME ---------------- */
    useEffect(() => {
        document.documentElement.setAttribute("data-theme", theme);
    }, [theme]);

    /* ---------------- KEYBOARD SHORTCUTS ---------------- */
    // Register the listener once. The handler reads the latest values through
    // keydownStateRef so the listener never needs to be removed/re-added.
    useEffect(() => {
        const handleKeyDown = (e) => {
            const { selectedIds, currentView, filteredFiles, handleTrash } =
                keydownStateRef.current;

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
    }, []); // Stable listener: latest state is read through keydownStateRef, not captured in closure.

    /* ---------------- UPLOAD ---------------- */
    const handleUpload = async (fileList) => {
        const filesArray = Array.from(fileList);
        const totalFiles = filesArray.length;

        // Initialize progress for all files
        const initialProgress = {};
        filesArray.forEach((file, i) => {
            initialProgress[i] = {
                name: file.name,
                size: file.size,
                loaded: 0,
                total: file.size,
                percent: 0,
                speed: 0,
                eta: 0,
                status: 'waiting', // waiting | uploading | done | error
                fileIndex: i + 1,
                totalFiles,
            };
        });
        setUploadProgress(initialProgress);

        try {
            // Upload files sequentially for accurate per-file progress
            for (let i = 0; i < filesArray.length; i++) {
                const file = filesArray[i];

                // Mark as uploading
                setUploadProgress(p => ({
                    ...p,
                    [i]: { ...p[i], status: 'uploading' },
                }));

                const { promise, abort } = api.uploadFileWithProgress(
                    file,
                    currentPath,
                    (progress) => {
                        setUploadProgress(p => ({
                            ...p,
                            [i]: {
                                ...p[i],
                                loaded: progress.loaded,
                                total: progress.total,
                                percent: progress.percent,
                                speed: progress.speed,
                                eta: progress.eta,
                                status: 'uploading',
                            },
                        }));
                    }
                );

                uploadAbortRef.current = abort;
                await promise;

                // Mark as done
                setUploadProgress(p => ({
                    ...p,
                    [i]: { ...p[i], percent: 100, status: 'done', speed: 0, eta: 0 },
                }));
            }

            // Clear progress after brief delay
            setTimeout(() => setUploadProgress({}), 1500);
            setSearchRefreshKey((key) => key + 1);
            loadFiles();
        } catch (err) {
            if (err.message === 'Upload cancelled') {
                setUploadProgress({});
            } else {
                console.error("Upload failed:", err);
                // Mark failed uploads
                setUploadProgress(p => {
                    const updated = { ...p };
                    Object.keys(updated).forEach(key => {
                        if (updated[key].status === 'uploading' || updated[key].status === 'waiting') {
                            updated[key].status = 'error';
                        }
                    });
                    return updated;
                });
                setTimeout(() => setUploadProgress({}), 3000);
            }
        }
        uploadAbortRef.current = null;
    };

    /* ---------------- FOLDER UPLOAD ---------------- */
    const handleFolderUpload = async (fileList) => {
        const filesArray = Array.from(fileList).filter(f => f.size > 0 || f.name);
        if (filesArray.length === 0) return;

        // Collect unique intermediate folder paths from webkitRelativePath
        // e.g. "myFolder/sub/file.txt" -> folders: ["myFolder", "myFolder/sub"]
        const folderSet = new Set();
        filesArray.forEach(file => {
            const relPath = file.webkitRelativePath || file.name;
            const parts = relPath.split('/');
            // All but the last part are folder segments
            for (let i = 1; i < parts.length; i++) {
                folderSet.add(parts.slice(0, i).join('/'));
            }
        });

        // Sort folders by depth so parents are created first
        const foldersToCreate = Array.from(folderSet).sort(
            (a, b) => a.split('/').length - b.split('/').length
        );

        // Create folders
        const createdFolders = new Set();
        for (const folderPath of foldersToCreate) {
            const parts = folderPath.split('/');
            const folderName = parts[parts.length - 1];
            // Parent path = currentPath + all parts except the last
            const parentPath = [...currentPath, ...parts.slice(0, -1)];
            try {
                await api.createFolder(folderName, parentPath);
                createdFolders.add(folderPath);
            } catch (err) {
                // Folder may already exist — that's OK
                if (!err.message?.includes('already exists')) {
                    console.error(`Failed to create folder ${folderPath}:`, err);
                }
            }
        }

        // Now upload each file with the correct sub-path
        const totalFiles = filesArray.length;
        const initialProgress = {};
        filesArray.forEach((file, i) => {
            initialProgress[i] = {
                name: file.webkitRelativePath || file.name,
                size: file.size,
                loaded: 0,
                total: file.size,
                percent: 0,
                speed: 0,
                eta: 0,
                status: 'waiting',
                fileIndex: i + 1,
                totalFiles,
            };
        });
        setUploadProgress(initialProgress);

        try {
            for (let i = 0; i < filesArray.length; i++) {
                const file = filesArray[i];
                const relPath = file.webkitRelativePath || file.name;
                const parts = relPath.split('/');
                // The file's target path = currentPath + all folder segments
                const filePath = [...currentPath, ...parts.slice(0, -1)];

                setUploadProgress(p => ({
                    ...p,
                    [i]: { ...p[i], status: 'uploading' },
                }));

                const { promise, abort } = api.uploadFileWithProgress(
                    file,
                    filePath,
                    (progress) => {
                        setUploadProgress(p => ({
                            ...p,
                            [i]: {
                                ...p[i],
                                loaded: progress.loaded,
                                total: progress.total,
                                percent: progress.percent,
                                speed: progress.speed,
                                eta: progress.eta,
                                status: 'uploading',
                            },
                        }));
                    }
                );

                uploadAbortRef.current = abort;
                await promise;

                setUploadProgress(p => ({
                    ...p,
                    [i]: { ...p[i], percent: 100, status: 'done', speed: 0, eta: 0 },
                }));
            }

            setTimeout(() => setUploadProgress({}), 1500);
            setSearchRefreshKey((key) => key + 1);
            loadFiles();
        } catch (err) {
            if (err.message === 'Upload cancelled') {
                setUploadProgress({});
            } else {
                console.error('Folder upload failed:', err);
                setUploadProgress(p => {
                    const updated = { ...p };
                    Object.keys(updated).forEach(key => {
                        if (updated[key].status === 'uploading' || updated[key].status === 'waiting') {
                            updated[key].status = 'error';
                        }
                    });
                    return updated;
                });
                setTimeout(() => setUploadProgress({}), 3000);
            }
        }
        uploadAbortRef.current = null;
    };

    const cancelUpload = () => {
        if (uploadAbortRef.current) {
            uploadAbortRef.current();
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
            a.style.display = "none";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            // Delay revocation so the browser has time to start reading the blob
            setTimeout(() => URL.revokeObjectURL(url), 10000);
        } catch (err) {
            console.error("Download failed:", err);
        }
    };

    /* ---------------- CREATE FOLDER ---------------- */
    const handleCreateFolder = async (name) => {
        try {
            await api.createFolder(name, currentPath);
            setSearchRefreshKey((key) => key + 1);
            loadFiles();
        } catch (err) {
            console.error("Create folder failed:", err);
        }
    };

    /* ---------------- RENAME ---------------- */
    const handleRename = async (id, newName) => {
        try {
            await api.updateFile(id, { name: newName });
            setSearchRefreshKey((key) => key + 1);
            loadFiles();
        } catch (err) {
            console.error("Rename failed:", err);
        }
    };

    /* ---------------- STAR/UNSTAR ---------------- */
    const handleStar = async (id) => {
        const file = [...files, ...searchResults].find((f) => f.id === id);
        if (!file) return;
        try {
            await api.updateFile(id, { is_starred: !file.is_starred });
            setSearchRefreshKey((key) => key + 1);
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
            setSearchRefreshKey((key) => key + 1);
            loadFiles();
        } catch (err) {
            console.error("Trash failed:", err);
        }
    };

    const handleRestore = async (id) => {
        try {
            await api.restoreFile(id);
            setSearchRefreshKey((key) => key + 1);
            loadFiles();
            // Reload trash view
            const trashData = await api.listFiles([], { includeTrash: true });
            setTrashedFiles(trashData.filter(f => f.is_trashed));
        } catch (err) {
            console.error("Restore failed:", err);
        }
    };

    const handleDeletePermanently = async (id) => {
        if (!confirm("Delete forever? This cannot be undone.")) return;
        try {
            await api.deleteFilePermanently(id);
            setSearchRefreshKey((key) => key + 1);
            setTrashedFiles((t) => t.filter((item) => item.id !== id));
        } catch (err) {
            console.error("Delete failed:", err);
        }
    };

    const handleEmptyTrash = async () => {
        if (!confirm("Permanently delete all items in trash? This cannot be undone.")) return;
        try {
            await api.emptyTrash();
            setSearchRefreshKey((key) => key + 1);
            setTrashedFiles([]);
        } catch (err) {
            console.error("Empty trash failed:", err);
        }
    };

    /* ---------------- MOVE ---------------- */
    const handleMove = async (id, newPath) => {
        try {
            await api.updateFile(id, { path: newPath });
            setSearchRefreshKey((key) => key + 1);
            loadFiles();
        } catch (err) {
            console.error("Move failed:", err);
        }
    };

    /* ---------------- DRAG-DROP MOVE TO FOLDER ---------------- */
    const handleMoveToFolder = async (fileId, targetFolder) => {
        const targetPath = [...(targetFolder.path || []), targetFolder.name];
        try {
            await api.updateFile(fileId, { path: targetPath });
            await loadFiles();
            setSearchRefreshKey((key) => key + 1);
            await loadExtra();
        } catch (err) {
            alert(err.message || "Failed to move file");
        }
    };

    /* ---------------- COPY ---------------- */
    const handleCopy = async (file) => {
        if (file.type === "folder") {
            alert("Folder copy is not supported yet.");
            return;
        }
        try {
            await api.copyFile(file.id);
            await loadFiles();
            setSearchRefreshKey((key) => key + 1);
            await loadExtra();
        } catch (err) {
            alert(err.message || "Failed to copy file");
        }
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
        let result = [...(isSearchMode ? searchResults : files)];

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

    const isSearchMode = searchQuery.trim().length > 0;
    const filteredFiles = getFilteredFiles();

    // Keep the keydown handler ref up to date on every render so the stable
    // listener always operates on the latest state without being re-registered.
    keydownStateRef.current = { selectedIds, currentView, filteredFiles, handleTrash };

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
        setSearchResults([]);
        setSearchError("");
        setSelectedIds(new Set());
        setIsMultiSelect(false);
    };

    const handleFileClick = (file) => {
        if (file.type === "folder") {
            setSearchQuery("");
            setSearchResults([]);
            setSearchError("");
            setCurrentPath([...(file.path || []), file.name]);
            setCurrentView("home");
        }
    };

    const handleFileDoubleClick = (file) => {
        if (file.type !== "folder") {
            setPreviewFile(file);
        }
    };

    const handleNavigateToPath = (path) => {
        setSearchQuery("");
        setSearchResults([]);
        setSearchError("");
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
        admin: "Admin Panel",
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
    const handleLogout = async () => {
        try {
            await api.logoutCurrentSession();
        } catch (error) {
            console.error("Failed to log out current session:", error);
        } finally {
            handleLocalSignOut();
        }
    };

    const handleLocalSignOut = () => {
        api.logout();
        setUser(null);
        setFiles([]);
        setSearchQuery("");
        setSearchResults([]);
        setSearchError("");
        setShowSecurityModal(false);
    };

    // Show recent section only on home view at root level
    const showRecentSection = currentView === "home" && currentPath.length === 0 && recentFiles.length > 0 && !isSearchMode;

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
                user={user}
            />

            <main
                className={`main-area ${detailsFile ? "with-details" : ""}`}
                onDragEnter={handleDragEnter}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
            >
                <Header
                    currentPath={currentPath}
                    searchQuery={searchQuery}
                    onSearchChange={setSearchQuery}
                    view={view}
                    onViewChange={setView}
                    onUpload={handleUpload}
                    onUploadFolder={handleFolderUpload}
                    onNewFolder={() => setShowNewFolderModal(true)}
                    onNavigateToPath={handleNavigateToPath}
                    sortBy={sortBy}
                    onSortChange={setSortBy}
                    isMultiSelect={isMultiSelect}
                    onToggleMultiSelect={() => {
                        setIsMultiSelect(!isMultiSelect);
                        if (isMultiSelect) setSelectedIds(new Set());
                    }}
                    selectedCount={selectedIds.size}
                    viewTitle={isSearchMode ? "Search Results" : viewTitles[currentView]}
                    user={user}
                    onLogout={handleLogout}
                    onOpenSecurity={() => setShowSecurityModal(true)}
                    onMobileMenuToggle={() => setIsMobileMenuOpen(true)}
                    showFileControls={currentView !== "activity" && currentView !== "trash" && currentView !== "admin"}
                />

                <div className="file-area">
                    {isDragging && <DropZone />}

                    {loading || searchLoading ? (
                        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                            {searchLoading ? "Searching files..." : "Loading files..."}
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
                    ) : currentView === "admin" && user?.is_admin ? (
                        <AdminPanel />
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
                                                    onMoveToFolder={handleMoveToFolder}
                                                />
                                            ))}
                                        </div>
                                    </section>
                                )}

                                {/* All Files Section */}
                                {showRecentSection && <h2 className="section-title">All Files</h2>}

                                {filteredFiles.length === 0 ? (
                                    <EmptyState
                                        title={isSearchMode ? "No search results" : "No files here"}
                                        subtitle={
                                            isSearchMode
                                                ? (searchError || `No matches found for "${searchQuery.trim()}"`)
                                                : "Upload or drag files to get started"
                                        }
                                    />
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
                                                onMoveToFolder={handleMoveToFolder}
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

                <UploadProgress uploads={uploadProgress} onCancel={cancelUpload} />
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
                    onShare={() => setShareFile(contextMenu.file)}
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

            {/* Share Modal */}
            {shareFile && (
                <ShareModal
                    file={shareFile}
                    onClose={() => setShareFile(null)}
                />
            )}

            {showSecurityModal && (
                <SecurityModal
                    user={user}
                    onClose={() => setShowSecurityModal(false)}
                    onUserUpdate={setUser}
                    onSignedOut={handleLocalSignOut}
                />
            )}
        </div>
    );
}
