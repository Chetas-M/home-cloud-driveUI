import React from "react";
import { Image, FileText, Film, Folder, File, Archive, Code } from "lucide-react";

// More vibrant and colorful legend colors
const colors = {
    image: { color: "#22d3ee", bg: "rgba(34, 211, 238, 0.25)" },    // Cyan
    pdf: { color: "#f472b6", bg: "rgba(244, 114, 182, 0.25)" },     // Pink
    video: { color: "#a855f7", bg: "rgba(168, 85, 247, 0.25)" },    // Purple
    folder: { color: "#3b82f6", bg: "rgba(59, 130, 246, 0.25)" },   // Blue
    text: { color: "#10b981", bg: "rgba(16, 185, 129, 0.25)" },     // Emerald
    archive: { color: "#f59e0b", bg: "rgba(245, 158, 11, 0.25)" },  // Amber
    file: { color: "#6b7280", bg: "rgba(107, 114, 128, 0.25)" },    // Gray
    other: { color: "#94a3b8", bg: "rgba(148, 163, 184, 0.25)" },   // Slate
};

const typeIcons = {
    image: Image,
    pdf: FileText,
    video: Film,
    folder: Folder,
    text: Code,
    archive: Archive,
    file: File,
    other: File,
};

export default function StorageChart({ files, storageInfo }) {
    // Calculate storage by type from files
    const breakdown = files.reduce((acc, file) => {
        if (file.type === "folder") return acc;
        const type = file.type || "other";
        acc[type] = (acc[type] || 0) + (file.size || 0);
        return acc;
    }, {});

    const total = Object.values(breakdown).reduce((a, b) => a + b, 0);

    // Use actual HDD storage from storageInfo (quota), treat 0 as unlimited
    const maxStorage = storageInfo?.quota || 0;
    const usedPercent = maxStorage > 0 ? ((total / maxStorage) * 100).toFixed(1) : "0.0";

    const formatSize = (bytes) => {
        if (bytes === 0) return "0 B";
        const tb = bytes / (1024 * 1024 * 1024 * 1024);
        if (tb >= 1) return `${tb.toFixed(2)} TB`;
        const gb = bytes / (1024 * 1024 * 1024);
        if (gb >= 1) return `${gb.toFixed(1)} GB`;
        const mb = bytes / (1024 * 1024);
        if (mb >= 1) return `${mb.toFixed(1)} MB`;
        const kb = bytes / 1024;
        return `${kb.toFixed(1)} KB`;
    };

    // Build segments for the ring chart
    const segments = [];
    let currentAngle = 0;
    const totalForChart = maxStorage > 0 ? maxStorage : (total > 0 ? total : 1);

    Object.entries(breakdown).forEach(([type, size]) => {
        const percent = (size / totalForChart) * 100;
        const angle = (percent / 100) * 360;
        segments.push({
            type,
            size,
            percent,
            startAngle: currentAngle,
            endAngle: currentAngle + angle,
            color: colors[type]?.color || colors.other.color,
        });
        currentAngle += angle;
    });

    // Create SVG arc path
    const createArc = (startAngle, endAngle, radius, innerRadius) => {
        if (endAngle - startAngle < 0.1) return ""; // Skip tiny segments
        const start = ((startAngle - 90) * Math.PI) / 180;
        const end = ((endAngle - 90) * Math.PI) / 180;
        const largeArc = endAngle - startAngle > 180 ? 1 : 0;

        const x1 = 50 + radius * Math.cos(start);
        const y1 = 50 + radius * Math.sin(start);
        const x2 = 50 + radius * Math.cos(end);
        const y2 = 50 + radius * Math.sin(end);
        const x3 = 50 + innerRadius * Math.cos(end);
        const y3 = 50 + innerRadius * Math.sin(end);
        const x4 = 50 + innerRadius * Math.cos(start);
        const y4 = 50 + innerRadius * Math.sin(start);

        return `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} L ${x3} ${y3} A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${x4} ${y4} Z`;
    };

    // Get storage display text - show actual disk capacity
    const getStorageText = () => {
        const diskTotal = storageInfo?.disk_total || 0;
        if (diskTotal > 0) {
            return `${formatSize(total)} of ${formatSize(diskTotal)}`;
        }
        if (maxStorage > 0) {
            return `${formatSize(total)} of ${formatSize(maxStorage)}`;
        }
        return `${formatSize(total)} used`;
    };

    return (
        <div className="storage-chart">
            <div className="storage-chart-title">STORAGE</div>

            {/* Donut chart */}
            <div className="storage-donut">
                <svg viewBox="0 0 100 100">
                    {/* Background ring */}
                    <circle
                        cx="50"
                        cy="50"
                        r="40"
                        fill="none"
                        stroke="var(--storage-ring-bg, rgba(100,100,100,0.2))"
                        strokeWidth="12"
                    />
                    {/* Segments */}
                    {segments.map((seg, i) => (
                        <path
                            key={i}
                            d={createArc(seg.startAngle, seg.endAngle, 46, 34)}
                            fill={seg.color}
                            className="storage-segment"
                        />
                    ))}
                </svg>
                <div className="storage-donut-center">
                    <span className="storage-percent">{usedPercent}%</span>
                    <span className="storage-label">used</span>
                </div>
            </div>

            {/* Legend with icons and colorful styling */}
            <div className="storage-legend">
                {Object.entries(breakdown).map(([type, size]) => {
                    const Icon = typeIcons[type] || typeIcons.other;
                    const color = colors[type]?.color || colors.other.color;
                    return (
                        <div key={type} className="storage-legend-item">
                            <span
                                className="storage-legend-dot"
                                style={{ background: color, boxShadow: `0 0 8px ${color}40` }}
                            />
                            <span className="storage-legend-type" style={{ textTransform: 'capitalize' }}>
                                {type}
                            </span>
                            <span className="storage-legend-size">{formatSize(size)}</span>
                        </div>
                    );
                })}
            </div>

            {/* Total */}
            <div className="storage-total">
                {getStorageText()}
            </div>
        </div>
    );
}
