import React, { useRef } from "react";
import { X, History, UploadCloud, RotateCw, Download, Trash2 } from "lucide-react";

function formatSize(bytes) {
    if (!bytes && bytes !== 0) return "—";
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    const gb = mb / 1024;
    return `${gb.toFixed(2)} GB`;
}

function formatDate(date) {
    if (!date) return "—";
    return new Date(date).toLocaleString();
}

export default function VersionHistoryModal({
    file,
    versions = [],
    loading = false,
    error = "",
    onClose,
    onUpload,
    onRestore,
    onDelete,
    onDownload,
}) {
    const inputRef = useRef(null);

    const handleUploadClick = () => inputRef.current?.click();
    const handleFileChange = (e) => {
        const selected = e.target.files?.[0];
        if (selected) {
            onUpload(selected);
        }
        e.target.value = "";
    };

    const sortedVersions = [...versions].sort((a, b) => (b.version || 0) - (a.version || 0));

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content wide" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <div className="modal-icon">
                        <History size={24} />
                    </div>
                    <div className="modal-title-group">
                        <h3>Version history</h3>
                        <div className="modal-subtitle">{file.name}</div>
                    </div>
                    <button className="modal-close" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                <div className="version-toolbar">
                    <div>
                        <div className="version-label">Current version</div>
                        <div className="version-value">v{file.version || 1}</div>
                    </div>
                    <div className="version-actions">
                        <input
                            ref={inputRef}
                            type="file"
                            style={{ display: "none" }}
                            onChange={handleFileChange}
                        />
                        <button className="btn-secondary" onClick={handleUploadClick} disabled={loading}>
                            <UploadCloud size={16} />
                            <span>Upload new version</span>
                        </button>
                    </div>
                </div>

                {error && <div className="version-error">{error}</div>}

                <div className="version-list">
                    {loading && <div className="version-row">Loading versions...</div>}
                    {!loading && sortedVersions.length === 0 && (
                        <div className="version-row">No versions found yet.</div>
                    )}
                    {!loading && sortedVersions.map((version) => (
                        <div key={version.id} className="version-row">
                            <div className="version-meta">
                                <div className="version-badge">v{version.version}</div>
                                <div>
                                    <div className="version-date">{formatDate(version.created_at)}</div>
                                    <div className="version-size">{formatSize(version.size)}</div>
                                </div>
                                {version.is_current && (
                                    <span className="version-current">Current</span>
                                )}
                            </div>
                            <div className="version-buttons">
                                <button
                                    className="btn-icon"
                                    onClick={() => onDownload(version)}
                                    title="Download"
                                >
                                    <Download size={16} />
                                </button>
                                <button
                                    className="btn-icon"
                                    onClick={() => onRestore(version.id)}
                                    disabled={version.is_current || loading}
                                    title="Restore as latest"
                                >
                                    <RotateCw size={16} />
                                </button>
                                <button
                                    className="btn-icon danger"
                                    onClick={() => onDelete(version.id)}
                                    disabled={version.is_current || loading}
                                    title="Delete version"
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
