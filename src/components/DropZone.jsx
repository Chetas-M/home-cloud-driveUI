import React from "react";
import { Upload } from "lucide-react";

export default function DropZone() {
    return (
        <div className="drop-overlay">
            <div className="drop-zone">
                <Upload size={56} />
                <p className="drop-zone-text">Drop files here to upload</p>
            </div>
        </div>
    );
}
