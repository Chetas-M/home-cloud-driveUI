import React from "react";
import {
    X,
    Download,
    Star,
    StarOff,
    Trash2,
    Folder,
    Image,
    FileText,
    Film,
    File,
    Calendar,
    HardDrive,
    MapPin,
    History,
} from "lucide-react";

const iconConfig = {
    folder: Folder,
    image: Image,
    pdf: FileText,
    video: Film,
    text: FileText,
    default: File,
};

function formatSize(bytes) {
    if (!bytes) return "—";
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    const gb = mb / 1024;
    return `${gb.toFixed(2)} GB`;
}

function formatDate(date) {
    if (!date) return "—";
    return new Date(date).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

export default function FileDetailsPanel({
    file,
    isStarred,
    onClose,
    onDownload,
    onStar,
    onTrash,
    onShowVersions,
}) {
    const Icon = iconConfig[file.type] || iconConfig.default;

    return (
        <div className="details-panel">
            <div className="details-header">
                <h3>Details</h3>
                <button className="details-close" onClick={onClose}>
                    <X size={20} />
                </button>
            </div>

            {/* Preview */}
            <div className="details-preview">
                {file.type === "image" && file.blob ? (
                    <img
                        src={URL.createObjectURL(file.blob)}
                        alt={file.name}
                        className="details-thumbnail"
                    />
                ) : (
                    <div className={`details-icon ${file.type}`}>
                        <Icon size={48} />
                    </div>
                )}
            </div>

            {/* File name */}
            <div className="details-name">{file.name}</div>

            {/* Quick actions */}
            <div className="details-actions">
                {file.type !== "folder" && file.blob && (
                    <button
                        className="details-action-btn"
                        onClick={() => onDownload(file)}
                    >
                        <Download size={18} />
                        <span>Download</span>
                    </button>
                )}
                {(!file.is_shared || file.can_share_public) && (
                    <button className="details-action-btn" onClick={() => onStar(file.id)}>
                        {isStarred ? <StarOff size={18} /> : <Star size={18} />}
                        <span>{isStarred ? "Unstar" : "Star"}</span>
                    </button>
                )}
                {file.can_manage && (
                    <button
                        className="details-action-btn danger"
                        onClick={() => onTrash(file.id)}
                    >
                        <Trash2 size={18} />
                        <span>Trash</span>
                    </button>
                )}
                {file.type !== "folder" && (
                    <button className="details-action-btn" onClick={onShowVersions}>
                        <History size={18} />
                        <span>Versions</span>
                    </button>
                )}
            </div>

            {/* Metadata */}
            <div className="details-metadata">
                <div className="metadata-item">
                    <span className="metadata-label">
                        <HardDrive size={14} /> Size
                    </span>
                    <span className="metadata-value">{formatSize(file.size)}</span>
                </div>

                <div className="metadata-item">
                    <span className="metadata-label">
                        <Calendar size={14} /> Modified
                    </span>
                    <span className="metadata-value">
                        {formatDate(
                            file.updated_at ||
                            file.updatedAt ||
                            file.modifiedAt ||
                            file.created_at ||
                            file.createdAt
                        )}
                    </span>
                </div>

                <div className="metadata-item">
                    <span className="metadata-label">
                        <MapPin size={14} /> Location
                    </span>
                    <span className="metadata-value">
                        /{file.path.length > 0 ? file.path.join("/") : "Home"}
                    </span>
                </div>
                {file.is_shared && file.owner_username && (
                    <div className="metadata-item">
                        <span className="metadata-label">
                            <Folder size={14} /> Owner
                        </span>
                        <span className="metadata-value">{file.owner_username}</span>
                    </div>
                )}
                {file.type !== "folder" && (
                    <div className="metadata-item">
                        <span className="metadata-label">
                            <History size={14} /> Version
                        </span>
                        <span className="metadata-value">v{file.version || 1}</span>
                    </div>
                )}
            </div>
        </div>
    );
}
