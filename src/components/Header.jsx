import React from "react";
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
}) {
    return (
        <header className="header">
            <div className="header-left">
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

                {/* Search - moved next to title */}
                <div className="search-box">
                    <Search size={18} />
                    <input
                        type="text"
                        placeholder="Search files..."
                        value={searchQuery}
                        onChange={(e) => onSearchChange(e.target.value)}
                    />
                </div>
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

                {/* Profile avatar */}
                <div className="profile-avatar" title="Profile">
                    <User size={20} />
                </div>
            </div>
        </header>
    );
}

