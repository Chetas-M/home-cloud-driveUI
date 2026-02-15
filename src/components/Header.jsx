import React, { useState } from "react";
import {
    Search,
    Grid,
    List,
    Upload,
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
    onNavigateToPath,
    sortBy,
    onSortChange,
    isMultiSelect,
    onToggleMultiSelect,
    selectedCount,
    viewTitle,
    user,
    onLogout,
    onMobileMenuToggle,
}) {
    const [showUserMenu, setShowUserMenu] = useState(false);
    const [showMobileSearch, setShowMobileSearch] = useState(false);

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
                {currentPath.length > 0 || !viewTitle ? (
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

                {/* Desktop search - hidden on mobile */}
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

                {/* Mobile search toggle button */}
                <button
                    className="search-toggle-btn"
                    onClick={() => setShowMobileSearch(true)}
                    aria-label="Search"
                >
                    <Search size={18} />
                </button>
            </div>

            <div className="header-right">
                {/* Multi-select indicator */}
                {isMultiSelect && selectedCount > 0 && (
                    <span className="selected-count">{selectedCount} selected</span>
                )}

                {/* Sort dropdown */}
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

                {/* Multi-select toggle */}
                <button
                    className={`header-btn ${isMultiSelect ? "active" : ""}`}
                    onClick={onToggleMultiSelect}
                    title="Multi-select"
                >
                    <CheckSquare size={18} />
                </button>

                {/* View toggle */}
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

                {/* Upload button */}
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

                {/* Profile avatar with menu */}
                <div className="user-menu">
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
