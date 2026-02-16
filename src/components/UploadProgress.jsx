import React from "react";
import { Upload, X, CheckCircle, AlertCircle, Clock, Zap } from "lucide-react";

function formatBytes(bytes) {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function formatEta(seconds) {
    if (seconds <= 0) return "calculating...";
    if (seconds < 60) return `${seconds}s remaining`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s remaining`;
}

function formatSpeed(bytesPerSec) {
    if (bytesPerSec <= 0) return "—";
    return formatBytes(bytesPerSec) + "/s";
}

function StatusIcon({ status }) {
    switch (status) {
        case 'done':
            return <CheckCircle size={16} className="upload-status-icon done" />;
        case 'error':
            return <AlertCircle size={16} className="upload-status-icon error" />;
        case 'uploading':
            return <Upload size={16} className="upload-status-icon uploading" />;
        default:
            return <Clock size={16} className="upload-status-icon waiting" />;
    }
}

export default function UploadProgress({ uploads, onCancel }) {
    const entries = Object.entries(uploads);

    if (entries.length === 0) return null;

    const totalFiles = entries.length;
    const doneCount = entries.filter(([, u]) => u.status === 'done').length;
    const activeUpload = entries.find(([, u]) => u.status === 'uploading');

    // Overall progress
    const totalBytes = entries.reduce((sum, [, u]) => sum + (u.total || 0), 0);
    const loadedBytes = entries.reduce((sum, [, u]) => sum + (u.loaded || 0), 0);
    const overallPercent = totalBytes > 0 ? Math.round((loadedBytes / totalBytes) * 100) : 0;

    return (
        <div className="upload-progress-container">
            {/* Header */}
            <div className="upload-progress-header">
                <div className="upload-progress-title">
                    <Upload size={18} />
                    <span>
                        {doneCount === totalFiles
                            ? `${totalFiles} file${totalFiles > 1 ? 's' : ''} uploaded`
                            : `Uploading ${doneCount + 1} of ${totalFiles}`
                        }
                    </span>
                </div>
                <div className="upload-progress-actions">
                    {activeUpload && (
                        <span className="upload-speed-badge">
                            <Zap size={12} />
                            {formatSpeed(activeUpload[1].speed)}
                        </span>
                    )}
                    {onCancel && doneCount < totalFiles && (
                        <button className="upload-cancel-btn" onClick={onCancel} title="Cancel upload">
                            <X size={16} />
                        </button>
                    )}
                </div>
            </div>

            {/* Overall progress bar */}
            <div className="upload-bar overall">
                <div
                    className="upload-bar-fill"
                    style={{ width: `${overallPercent}%` }}
                />
            </div>

            {/* File list */}
            <div className="upload-file-list">
                {entries.map(([id, upload]) => (
                    <div key={id} className={`upload-item ${upload.status}`}>
                        <StatusIcon status={upload.status} />
                        <div className="upload-item-info">
                            <span className="upload-item-name" title={upload.name}>
                                {upload.name}
                            </span>
                            <span className="upload-item-meta">
                                {upload.status === 'uploading' && (
                                    <>
                                        {formatBytes(upload.loaded)} / {formatBytes(upload.total)}
                                        {upload.eta > 0 && (
                                            <> · {formatEta(upload.eta)}</>
                                        )}
                                    </>
                                )}
                                {upload.status === 'done' && formatBytes(upload.total)}
                                {upload.status === 'waiting' && formatBytes(upload.total)}
                                {upload.status === 'error' && 'Failed'}
                            </span>
                        </div>
                        <span className="upload-item-percent">
                            {upload.status === 'done' ? '✓' : `${upload.percent}%`}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
