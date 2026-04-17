import React from "react";
import {
    Download,
    Star,
    StarOff,
    Edit3,
    Trash2,
    FolderInput,
    Eye,
    Copy,
    Info,
    Share2,
    History,
} from "lucide-react";

export default function ContextMenu({
    x,
    y,
    file,
    isStarred,
    onClose,
    onPreview,
    onDownload,
    onStar,
    onRename,
    onMove,
    onCopy,
    onTrash,
    onDetails,
    onShare,
    onVersions,
}) {
    const menuItems = [
        { icon: Eye, label: "Preview", action: onPreview, show: file.type !== "folder" },
        { icon: Download, label: "Download", action: onDownload, show: file.type !== "folder" },
        { divider: true },
        { icon: isStarred ? StarOff : Star, label: isStarred ? "Unstar" : "Star", action: onStar, show: !file.is_shared || file.can_share_public },
        { icon: Edit3, label: "Rename", action: onRename, show: file.can_write },
        { icon: FolderInput, label: "Move to...", action: onMove, show: file.can_write },
        { icon: Copy, label: "Make a copy", action: onCopy, show: file.type !== "folder" && !file.is_shared },
        { icon: Share2, label: file.type === "folder" ? "Manage access" : "Share", action: onShare, show: file.type === "folder" ? file.can_manage && (!file.is_shared || file.is_shared_root) : file.can_share_public },
        { divider: true },
        { icon: History, label: "Version history", action: onVersions, show: file.type !== "folder" },
        { icon: Info, label: "Details", action: onDetails },
        { icon: Trash2, label: "Move to Trash", action: onTrash, danger: true, show: file.can_manage },
    ];

    const handleClick = (action) => {
        action?.();
        onClose();
    };

    // Adjust position to keep menu in viewport
    const adjustedX = Math.min(x, window.innerWidth - 220);
    const adjustedY = Math.min(y, window.innerHeight - 350);

    return (
        <>
            <div className="context-menu-overlay" onClick={onClose} />
            <div
                className="context-menu"
                style={{ left: adjustedX, top: adjustedY }}
            >
                {menuItems.map((item, index) => {
                    if (item.divider) {
                        return <div key={index} className="context-menu-divider" />;
                    }
                    if (item.show === false) return null;
                    const Icon = item.icon;
                    return (
                        <button
                            key={index}
                            className={`context-menu-item ${item.danger ? "danger" : ""}`}
                            onClick={() => handleClick(item.action)}
                        >
                            <Icon size={16} />
                            <span>{item.label}</span>
                        </button>
                    );
                })}
            </div>
        </>
    );
}
