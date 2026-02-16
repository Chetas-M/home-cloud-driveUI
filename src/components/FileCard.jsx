import React, { useState, useEffect } from "react";
import {
    Folder,
    Image,
    FileText,
    Film,
    Archive,
    File,
    Download,
    Star,
    Check,
} from "lucide-react";
import api from "../api";

const iconConfig = {
    folder: { Icon: Folder, className: "folder" },
    image: { Icon: Image, className: "image" },
    pdf: { Icon: FileText, className: "pdf" },
    video: { Icon: Film, className: "video" },
    text: { Icon: FileText, className: "text" },
    archive: { Icon: Archive, className: "archive" },
    default: { Icon: File, className: "default" },
};

function formatSize(bytes) {
    if (!bytes) return "";
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    return `${mb.toFixed(1)} MB`;
}

export default function FileCard({
    file,
    view,
    index,
    onClick,
    onDoubleClick,
    onDownload,
    onContextMenu,
    isStarred,
    isSelected,
    isMultiSelect,
    onSelect,
}) {
    const config = iconConfig[file.type] || iconConfig.default;
    const { Icon, className } = config;
    const [thumbnail, setThumbnail] = useState(null);

    // Use server thumbnail if available, fallback to client blob
    useEffect(() => {
        if (file.thumbnail_url) {
            setThumbnail(api.getFileThumbnailUrl(file.id));
        } else if (file.type === "image" && file.blob) {
            const url = URL.createObjectURL(file.blob);
            setThumbnail(url);
            return () => URL.revokeObjectURL(url);
        } else {
            setThumbnail(null);
        }
    }, [file]);

    const handleClick = (e) => {
        if (isMultiSelect) {
            e.stopPropagation();
            onSelect?.(file.id);
        } else {
            onClick?.();
        }
    };

    const handleDoubleClick = (e) => {
        if (!isMultiSelect) {
            onDoubleClick?.();
        }
    };

    const handleContextMenu = (e) => {
        e.preventDefault();
        onContextMenu?.(e, file);
    };

    const handleDownload = (e) => {
        e.stopPropagation();
        onDownload(file);
    };

    const handleCheckbox = (e) => {
        e.stopPropagation();
        onSelect?.(file.id);
    };

    return (
        <div
            className={`file-card ${view === "list" ? "list-item" : ""} ${isSelected ? "selected" : ""
                }`}
            onClick={handleClick}
            onDoubleClick={handleDoubleClick}
            onContextMenu={handleContextMenu}
            style={{ animationDelay: `${index * 0.03}s` }}
        >
            {/* Checkbox for multi-select */}
            {isMultiSelect && (
                <button
                    className={`file-checkbox ${isSelected ? "checked" : ""}`}
                    onClick={handleCheckbox}
                >
                    {isSelected && <Check size={14} />}
                </button>
            )}

            {/* Star indicator */}
            {isStarred && (
                <div className="file-star">
                    <Star size={14} fill="currentColor" />
                </div>
            )}

            {/* Icon or thumbnail */}
            <div className={`file-icon ${className}`}>
                {thumbnail ? (
                    <img src={thumbnail} alt="" className="file-thumbnail" />
                ) : (
                    <Icon size={view === "list" ? 24 : 28} />
                )}
            </div>

            {view === "list" ? (
                <div className="file-info">
                    <div>
                        <div className="file-name">{file.name}</div>
                        {file.type !== "folder" && (
                            <div className="file-size">{formatSize(file.size)}</div>
                        )}
                    </div>
                    {file.type !== "folder" && file.blob && (
                        <button className="download-btn" onClick={handleDownload}>
                            <Download size={14} />
                            Download
                        </button>
                    )}
                </div>
            ) : (
                <>
                    <div className="file-name">{file.name}</div>
                    {file.type !== "folder" && (
                        <div className="file-size">{formatSize(file.size)}</div>
                    )}
                    {file.type !== "folder" && file.blob && (
                        <div className="file-actions">
                            <button className="download-btn" onClick={handleDownload}>
                                <Download size={14} />
                                Download
                            </button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
