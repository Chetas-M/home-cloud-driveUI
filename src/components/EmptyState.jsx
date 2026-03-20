import React from "react";
import { CloudUpload } from "lucide-react";

export default function EmptyState({
    title = "No files here",
    subtitle = "Upload or drag files to get started",
}) {
    return (
        <div className="empty-state">
            <div className="empty-icon">
                <CloudUpload size={48} />
            </div>
            <h3 className="empty-title">{title}</h3>
            <p className="empty-subtitle">{subtitle}</p>
        </div>
    );
}
