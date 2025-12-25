import React from "react";
import { Trash2, RotateCcw, X } from "lucide-react";

export default function TrashView({
    trashedFiles,
    onRestore,
    onDeletePermanently,
    onEmptyTrash,
}) {
    if (trashedFiles.length === 0) {
        return (
            <div className="trash-empty">
                <Trash2 size={48} className="trash-empty-icon" />
                <h3>Trash is empty</h3>
                <p>Items you delete will appear here</p>
            </div>
        );
    }

    return (
        <div className="trash-view">
            <div className="trash-header">
                <span className="trash-count">
                    {trashedFiles.length} item{trashedFiles.length > 1 ? "s" : ""} in trash
                </span>
                <button className="empty-trash-btn" onClick={onEmptyTrash}>
                    <Trash2 size={16} />
                    Empty Trash
                </button>
            </div>

            <div className="trash-list">
                {trashedFiles.map((file) => (
                    <div key={file.id} className="trash-item">
                        <span className="trash-item-name">{file.name}</span>
                        <div className="trash-item-actions">
                            <button
                                className="trash-action restore"
                                onClick={() => onRestore(file.id)}
                                title="Restore"
                            >
                                <RotateCcw size={16} />
                            </button>
                            <button
                                className="trash-action delete"
                                onClick={() => onDeletePermanently(file.id)}
                                title="Delete forever"
                            >
                                <X size={16} />
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
