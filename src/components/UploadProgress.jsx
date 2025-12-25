import React from "react";

export default function UploadProgress({ uploads }) {
    const entries = Object.entries(uploads);

    if (entries.length === 0) return null;

    return (
        <div className="upload-progress-container">
            {entries.map(([id, { name, progress }]) => (
                <div key={id} className="upload-item">
                    <div className="upload-item-header">
                        <span className="upload-item-name" title={name}>
                            {name}
                        </span>
                        <span className="upload-item-percent">{progress}%</span>
                    </div>
                    <div className="upload-bar">
                        <div
                            className="upload-bar-fill"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                </div>
            ))}
        </div>
    );
}
