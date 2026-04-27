import React, { useEffect, useState } from "react";
import { X, Download, ChevronLeft, ChevronRight } from "lucide-react";
import api from "../api";

export default function FilePreviewModal({
    file,
    files,
    onClose,
    onDownload,
    onNavigate,
}) {
    const [textContent, setTextContent] = useState(null);
    const [textLoading, setTextLoading] = useState(false);
    const [previewUrl, setPreviewUrl] = useState(null);

    // Fetch text content when previewing text files
    useEffect(() => {
        if (file.type === "text" && !file.blob) {
            setTextLoading(true);
            setTextContent(null);
            api.downloadFile(file.id)
                .then(blob => blob.text())
                .then(text => {
                    // Limit display to ~100KB to prevent browser freeze
                    setTextContent(text.length > 102400 ? text.slice(0, 102400) + "\n\n... (truncated)" : text);
                })
                .catch(() => setTextContent("Failed to load file content."))
                .finally(() => setTextLoading(false));
        } else {
            setTextContent(null);
        }
    }, [file]);

    // Fetch blob URL for image/video/PDF previews (avoids JWT in URL)
    useEffect(() => {
        if (["image", "video", "pdf"].includes(file.type)) {
            let active = true;
            let objectUrl = null;
            setPreviewUrl(null);
            api.fetchPreviewBlob(file.id)
                .then(url => {
                    objectUrl = url;
                    if (active) {
                        setPreviewUrl(url);
                    } else {
                        URL.revokeObjectURL(url);
                    }
                })
                .catch(() => setPreviewUrl(null));
            return () => {
                active = false;
                if (objectUrl) URL.revokeObjectURL(objectUrl);
            };
        }
        setPreviewUrl(null);
    }, [file]);

    // Keyboard navigation
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === "Escape") onClose();
            if (e.key === "ArrowLeft") onNavigate?.("prev");
            if (e.key === "ArrowRight") onNavigate?.("next");
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [onClose, onNavigate]);

    const renderContent = () => {
        // Text files: fetch content and display in <pre>
        if (file.type === "text") {
            if (textLoading) {
                return (
                    <div className="preview-placeholder">
                        <p>Loading file content...</p>
                    </div>
                );
            }
            if (textContent !== null) {
                return (
                    <pre className="preview-text-content">{textContent}</pre>
                );
            }
        }

        // Image, video, PDF: use fetched blob URL
        if (!previewUrl) {
            return (
                <div className="preview-placeholder">
                    <p>Loading preview...</p>
                </div>
            );
        }

        if (file.type === "image") {
            return <img src={previewUrl} alt={file.name} className="preview-image" />;
        }

        if (file.type === "video") {
            return (
                <video src={previewUrl} controls autoPlay className="preview-video">
                    Your browser does not support video playback.
                </video>
            );
        }

        if (file.type === "pdf") {
            return (
                <iframe
                    src={previewUrl}
                    title={file.name}
                    className="preview-pdf"
                />
            );
        }

        return (
            <div className="preview-placeholder">
                <p>Cannot preview this file type</p>
                <p className="text-muted">Click Download to view it</p>
            </div>
        );
    };

    return (
        <div className="preview-modal-overlay" onClick={onClose}>
            <div className="preview-modal" onClick={(e) => e.stopPropagation()}>
                {/* Header */}
                <div className="preview-header">
                    <h3 className="preview-title">{file.name}</h3>
                    <div className="preview-actions">
                        <button
                            className="preview-btn"
                            onClick={() => onDownload(file)}
                            title="Download"
                        >
                            <Download size={20} />
                        </button>
                        <button className="preview-btn" onClick={onClose} title="Close">
                            <X size={20} />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="preview-content">
                    {onNavigate && (
                        <button
                            className="preview-nav prev"
                            onClick={() => onNavigate("prev")}
                        >
                            <ChevronLeft size={32} />
                        </button>
                    )}

                    {renderContent()}

                    {onNavigate && (
                        <button
                            className="preview-nav next"
                            onClick={() => onNavigate("next")}
                        >
                            <ChevronRight size={32} />
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}

