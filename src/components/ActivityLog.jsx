import React from "react";
import {
    Upload,
    Download,
    FolderPlus,
    Edit3,
    Trash2,
    Star,
    RotateCcw,
} from "lucide-react";

const iconMap = {
    upload: Upload,
    download: Download,
    create_folder: FolderPlus,
    rename: Edit3,
    trash: Trash2,
    restore: RotateCcw,
    star: Star,
};

const actionLabels = {
    upload: "Uploaded",
    download: "Downloaded",
    create_folder: "Created folder",
    rename: "Renamed",
    trash: "Moved to trash",
    restore: "Restored",
    star: "Starred",
};

function formatTime(timestamp) {
    const now = Date.now();
    const diff = now - timestamp;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return "Just now";
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;

    return new Date(timestamp).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
    });
}

export default function ActivityLog({ activities }) {
    if (!activities || activities.length === 0) {
        return (
            <div className="activity-log">
                <h3 className="activity-title">Recent Activity</h3>
                <p className="activity-empty">No recent activity</p>
            </div>
        );
    }

    return (
        <div className="activity-log">
            <h3 className="activity-title">Recent Activity</h3>
            <div className="activity-list">
                {activities.slice(0, 20).map((activity, index) => {
                    const Icon = iconMap[activity.action] || Upload;
                    return (
                        <div key={index} className="activity-item">
                            <div className="activity-icon">
                                <Icon size={14} />
                            </div>
                            <div className="activity-content">
                                <span className="activity-action">
                                    {actionLabels[activity.action] || activity.action}
                                </span>
                                <span className="activity-filename">{activity.fileName}</span>
                            </div>
                            <span className="activity-time">
                                {formatTime(activity.timestamp)}
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
