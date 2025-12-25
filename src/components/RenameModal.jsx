import React, { useState, useEffect, useRef } from "react";
import { Edit3, X } from "lucide-react";

export default function RenameModal({ file, onClose, onRename }) {
    const [name, setName] = useState(file.name);
    const inputRef = useRef(null);

    useEffect(() => {
        inputRef.current?.focus();
        // Select filename without extension
        const dotIndex = file.name.lastIndexOf(".");
        if (dotIndex > 0 && file.type !== "folder") {
            inputRef.current?.setSelectionRange(0, dotIndex);
        } else {
            inputRef.current?.select();
        }
    }, [file]);

    const handleSubmit = (e) => {
        e.preventDefault();
        if (name.trim() && name !== file.name) {
            onRename(file.id, name.trim());
        }
        onClose();
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
                        <Edit3 size={24} />
                    </div>
                    <h3>Rename</h3>
                    <button className="modal-close" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                <form onSubmit={handleSubmit}>
                    <input
                        ref={inputRef}
                        type="text"
                        className="modal-input"
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
                            Rename
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
