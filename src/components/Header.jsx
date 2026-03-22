import React, { useState, useEffect, useRef } from "react";
import {
    Search,
    Grid,
    List,
    Upload,
    FolderUp,
    FolderPlus,
    Home,
    ChevronRight,
    ChevronDown,
    CheckSquare,
    User,
    LogOut,
    Settings,
    Menu,
    X,
} from "lucide-react";

const sortOptions = [
    { value: "name", label: "Name" },
    { value: "date", label: "Date modified" },
    { value: "size", label: "Size" },
    { value: "type", label: "Type" },
];

export default function Header({
    currentPath,
    searchQuery,
    onSearchChange,
    view,
    onViewChange,
    onUpload,
    onUploadFolder,
    onNewFolder,
    onNavigateToPath,
    sortBy,
    onSortChange,
    isMultiSelect,
    onToggleMultiSelect,
    selectedCount,
    viewTitle,
    user,
    onLogout,
    onOpenSecurity,
    onMobileMenuToggle,
    showFileControls = true,
}) {
    const [showUserMenu, setShowUserMenu] = useState(false);
    const [showMobileSearch, setShowMobileSearch] = useState(false);
    const userMenuRef = useRef(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        if (!showUserMenu) return;
        const handleClickOutside = (e) => {
            if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
                setShowUserMenu(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [showUserMenu]);

    return (
        <header className="header">
            <div className="header-left">
                {/* Mobile menu button */}
                <button
                    className="mobile-menu-btn"
                    onClick={onMobileMenuToggle}
                    aria-label="Open menu"
                >
                    <Menu size={22} />
                </button>

                <h1>{viewTitle || "My Drive"}</h1>
                {showFileControls && (currentPath.length > 0 || !viewTitle) ? (
                    <nav className="breadcrumb">
                        <span
                            className="breadcrumb-item clickable"
                            onClick={() => onNavigateToPath([])}
                        >
                            <Home size={14} />
                        </span>
                        {currentPath.map((folder, index) => (
                            <span key={index} className="breadcrumb-item">
                                <ChevronRight size={14} />
                                <span
                                    className="clickable"
                                    onClick={() => onNavigateToPath(currentPath.slice(0, index + 1))}
                                >
                                    {folder}
                                </span>
                            </span>
                        ))}
                    </nav>
                ) : null}

                {/* Desktop search - only on file views */}
                {showFileControls && (
                    <div className={`search-box ${showMobileSearch ? 'mobile-visible' : ''}`}>
                        <Search size={18} />
                        <input
                            type="text"
                            placeholder="Search files..."
                            value={searchQuery}
                            onChange={(e) => onSearchChange(e.target.value)}
                            autoFocus={showMobileSearch}
                        />
                        {showMobileSearch && (
                            <button
                                className="search-close-btn"
                                onClick={() => {
                                    setShowMobileSearch(false);
                                    onSearchChange('');
                                }}
                            >
                                <X size={18} />
                            </button>
                        )}
                    </div>
                )}

                {/* Mobile search toggle - only on file views */}
                {showFileControls && (
                    <button
                        className="search-toggle-btn"
                        onClick={() => setShowMobileSearch(true)}
                        aria-label="Search"
                    >
                        <Search size={18} />
                    </button>
                )}
            </div>

            <div className="header-right">
                {/* Multi-select indicator */}
                {showFileControls && isMultiSelect && selectedCount > 0 && (
                    <span className="selected-count">{selectedCount} selected</span>
                )}

                {/* Sort dropdown - only on file views */}
                {showFileControls && (
                    <div className="sort-dropdown">
                        <select
                            value={sortBy}
                            onChange={(e) => onSortChange(e.target.value)}
                            className="sort-select"
                        >
                            {sortOptions.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                </option>
                            ))}
                        </select>
                        <ChevronDown size={14} className="sort-icon" />
                    </div>
                )}

                {/* Multi-select toggle - only on file views */}
                {showFileControls && (
                    <button
                        className={`header-btn ${isMultiSelect ? "active" : ""}`}
                        onClick={onToggleMultiSelect}
                        title="Multi-select"
                    >
                        <CheckSquare size={18} />
                    </button>
                )}

                {/* View toggle - only on file views */}
                {showFileControls && (
                    <div className="view-toggle">
                        <button
                            className={`view-btn ${view === "grid" ? "active" : ""}`}
                            onClick={() => onViewChange("grid")}
                            aria-label="Grid view"
                        >
                            <Grid size={18} />
                        </button>
                        <button
                            className={`view-btn ${view === "list" ? "active" : ""}`}
                            onClick={() => onViewChange("list")}
                            aria-label="List view"
                        >
                            <List size={18} />
                        </button>
                    </div>
                )}

                {/* New Folder button - only on file views */}
                {showFileControls && onNewFolder && (
                    <button className="header-btn" onClick={onNewFolder} title="New Folder">
                        <FolderPlus size={18} />
                    </button>
                )}

                {/* Upload Folder button - only on file views */}
                {showFileControls && (
                    <label className="upload-btn upload-folder-btn" title="Upload Folder">
                        <FolderUp size={18} />
                        <span>Folder</span>
                        <input
                            type="file"
                            hidden
                            webkitdirectory=""
                            directory=""
                            multiple
                            onChange={(e) => onUploadFolder(e.target.files)}
                        />
                    </label>
                )}

                {/* Upload button - only on file views */}
                {showFileControls && (
                    <label className="upload-btn">
                        <Upload size={18} />
                        <span>Upload</span>
                        <input
                            type="file"
                            multiple
                            hidden
                            onChange={(e) => onUpload(e.target.files)}
                        />
                    </label>
                )}

                {/* Profile avatar with menu */}
                <div className="user-menu" ref={userMenuRef}>
                    <div
                        className="profile-avatar"
                        title={user?.username || "Profile"}
                        onClick={() => setShowUserMenu(!showUserMenu)}
                    >
                        <User size={20} />
                    </div>

                    {showUserMenu && (
                        <div className="user-menu-dropdown">
                            <div className="user-menu-item" style={{ cursor: 'default', opacity: 0.7 }}>
                                <User size={16} />
                                <span>{user?.username || user?.email}</span>
                            </div>
                            <button
                                className="user-menu-item"
                                onClick={() => {
                                    setShowUserMenu(false);
                                    onOpenSecurity?.();
                                }}
                            >
                                <Settings size={16} />
                                <span>Account Security</span>
                            </button>
                            <button
                                className="user-menu-item danger"
                                onClick={() => {
                                    setShowUserMenu(false);
                                    onLogout();
                                }}
                            >
                                <LogOut size={16} />
                                <span>Sign Out</span>
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </header>
    );
}
