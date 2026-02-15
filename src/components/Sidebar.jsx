import React from "react";
import {
    Cloud,
    Home,
    FolderOpen,
    Clock,
    Trash2,
    Star,
    FolderPlus,
    Activity,
    Sun,
    Moon,
    ChevronLeft,
    ChevronRight,
} from "lucide-react";
import StorageChart from "./StorageChart";

export default function Sidebar({
    currentView,
    onNavigate,
    onNewFolder,
    theme,
    onToggleTheme,
    files,
    storageInfo,
    trashedCount,
    starredCount,
    isCollapsed,
    onToggleCollapse,
    isMobileOpen,
    onMobileClose,
}) {
    const navItems = [
        { id: "home", icon: Home, label: "Home" },
        { id: "starred", icon: Star, label: "Starred", count: starredCount },
        { id: "recent", icon: Clock, label: "Recent" },
        { id: "activity", icon: Activity, label: "Activity" },
        { id: "trash", icon: Trash2, label: "Trash", count: trashedCount },
    ];

    const handleNavClick = (id) => {
        onNavigate(id);
        if (onMobileClose) onMobileClose();
    };

    return (
        <aside className={`sidebar ${isCollapsed ? "collapsed" : ""} ${isMobileOpen ? "mobile-open" : ""}`}>
            {/* Collapse toggle button */}
            <button
                className="sidebar-toggle"
                onClick={onToggleCollapse}
                title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
                {isCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            </button>

            {/* Logo */}
            <div className="sidebar-logo">
                <div className="sidebar-logo-icon">
                    <Cloud size={22} color="white" />
                </div>
                {!isCollapsed && <span className="sidebar-logo-text">Home Cloud</span>}
            </div>

            {/* New Folder Button */}
            <button className="new-folder-btn" onClick={onNewFolder} title="New Folder">
                <FolderPlus size={18} />
                {!isCollapsed && <span>New Folder</span>}
            </button>

            {/* Navigation */}
            <nav className="sidebar-nav">
                {navItems.map((item) => {
                    const Icon = item.icon;
                    return (
                        <button
                            key={item.id}
                            className={`nav-item ${currentView === item.id ? "active" : ""}`}
                            onClick={() => handleNavClick(item.id)}
                            title={isCollapsed ? item.label : undefined}
                        >
                            <Icon size={20} />
                            {!isCollapsed && <span>{item.label}</span>}
                            {!isCollapsed && item.count > 0 && (
                                <span className="nav-count">{item.count}</span>
                            )}
                        </button>
                    );
                })}
            </nav>

            {/* Theme toggle */}
            <button className="theme-toggle" onClick={onToggleTheme} title={theme === "dark" ? "Light Mode" : "Dark Mode"}>
                {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
                {!isCollapsed && <span>{theme === "dark" ? "Light Mode" : "Dark Mode"}</span>}
            </button>

            {/* Storage - only show when not collapsed */}
            {!isCollapsed && <StorageChart files={files} storageInfo={storageInfo} />}
        </aside>
    );
}
