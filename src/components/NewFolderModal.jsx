import React, { useState, useEffect, useRef } from "react";
import { FolderPlus, X } from "lucide-react";

export default function NewFolderModal({ onClose, onCreate }) {
    const [name, setName] = useState("");
    const inputRef = useRef(null);

    useEffect(() => {
        inputRef.current?.focus();
    }, []);

    const handleSubmit = (e) => {
        e.preventDefault();
        if (name.trim()) {
            onCreate(name.trim());
            onClose();
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === "Escape") onClose();
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div
                className="modal-content"
                onClick={(e) => e.stopPropagation()}
                onKeyDown={handleKeyDown}
            >
                <div className="modal-header">
                    <div className="modal-icon">
                        <FolderPlus size={24} />
                    </div>
                    <h3>New Folder</h3>
                    <button className="modal-close" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                <form onSubmit={handleSubmit}>
                    <input
                        ref={inputRef}
                        type="text"
                        className="modal-input"
                        placeholder="Folder name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                    />

                    <div className="modal-actions">
                        <button type="button" className="btn-secondary" onClick={onClose}>
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className="btn-primary"
                            disabled={!name.trim()}
                        >
                            Create
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
