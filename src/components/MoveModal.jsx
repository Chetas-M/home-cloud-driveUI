import React, { useState } from "react";
import { FolderInput, X, Folder, ChevronRight, Home } from "lucide-react";

export default function MoveModal({ file, folders, currentPath, onClose, onMove }) {
    const [targetPath, setTargetPath] = useState([]);

    // Get folders at the current target path
    const foldersAtPath = folders.filter(
        (f) =>
            f.type === "folder" &&
            JSON.stringify(f.path) === JSON.stringify(targetPath) &&
            f.id !== file.id // Don't show self
    );

    const handleMove = () => {
        onMove(file.id, targetPath);
        onClose();
    };

    const navigateToFolder = (folderName) => {
        setTargetPath([...targetPath, folderName]);
    };

    const navigateUp = (index) => {
        setTargetPath(targetPath.slice(0, index));
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div
                className="modal-content modal-move"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="modal-header">
                    <div className="modal-icon">
                        <FolderInput size={24} />
                    </div>
                    <h3>Move "{file.name}"</h3>
                    <button className="modal-close" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                {/* Breadcrumb */}
                <div className="move-breadcrumb">
                    <button
                        className="move-breadcrumb-item"
                        onClick={() => setTargetPath([])}
                    >
                        <Home size={14} /> Home
                    </button>
                    {targetPath.map((folder, index) => (
                        <span key={index} className="move-breadcrumb-item">
                            <ChevronRight size={14} />
                            <button onClick={() => navigateUp(index + 1)}>{folder}</button>
                        </span>
                    ))}
                </div>

                {/* Folder list */}
                <div className="move-folder-list">
                    {foldersAtPath.length === 0 ? (
                        <p className="move-empty">No subfolders here</p>
                    ) : (
                        foldersAtPath.map((folder) => (
                            <button
                                key={folder.id}
                                className="move-folder-item"
                                onClick={() => navigateToFolder(folder.name)}
                            >
                                <Folder size={18} />
                                <span>{folder.name}</span>
                                <ChevronRight size={16} className="move-arrow" />
                            </button>
                        ))
                    )}
                </div>

                <div className="modal-actions">
                    <button className="btn-secondary" onClick={onClose}>
                        Cancel
                    </button>
                    <button
                        className="btn-primary"
                        onClick={handleMove}
                        disabled={JSON.stringify(targetPath) === JSON.stringify(file.path)}
                    >
                        Move here
                    </button>
                </div>
            </div>
        </div>
    );
}
