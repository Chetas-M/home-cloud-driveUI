import React from "react";
import { CloudUpload } from "lucide-react";

export default function EmptyState() {
    return (
        <div className="empty-state">
            <div className="empty-icon">
                <CloudUpload size={48} />
            </div>
            <h3 className="empty-title">No files here</h3>
            <p className="empty-subtitle">
                Upload or drag files to get started
            </p>
        </div>
    );
}
