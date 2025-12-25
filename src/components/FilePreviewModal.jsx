import React, { useEffect } from "react";
import { X, Download, ChevronLeft, ChevronRight } from "lucide-react";

export default function FilePreviewModal({
    file,
    files,
    onClose,
    onDownload,
    onNavigate,
}) {
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
        if (!file.blob && !file.previewUrl) {
            return (
                <div className="preview-placeholder">
                    <p>Preview not available</p>
                    <p className="text-muted">Upload a file to enable preview</p>
                </div>
            );
        }

        const url = file.previewUrl || URL.createObjectURL(file.blob);

        if (file.type === "image") {
            return <img src={url} alt={file.name} className="preview-image" />;
        }

        if (file.type === "video") {
            return (
                <video src={url} controls autoPlay className="preview-video">
                    Your browser does not support video playback.
                </video>
            );
        }

        if (file.type === "pdf") {
            return (
                <iframe
                    src={url}
                    title={file.name}
                    className="preview-pdf"
                />
            );
        }

        if (file.type === "text") {
            return (
                <div className="preview-text">
                    <p>Text file preview</p>
                    <p className="text-muted">{file.name}</p>
                </div>
            );
        }

        return (
            <div className="preview-placeholder">
                <p>Cannot preview this file type</p>
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
                        {file.blob && (
                            <button
                                className="preview-btn"
                                onClick={() => onDownload(file)}
                                title="Download"
                            >
                                <Download size={20} />
                            </button>
                        )}
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
