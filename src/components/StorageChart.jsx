import React from "react";
import { Image, FileText, Film, Folder, File } from "lucide-react";

const colors = {
    image: { color: "#5eead4", bg: "rgba(94, 234, 212, 0.2)" },
    pdf: { color: "#fb7185", bg: "rgba(251, 113, 133, 0.2)" },
    video: { color: "#a78bfa", bg: "rgba(167, 139, 250, 0.2)" },
    folder: { color: "#38bdf8", bg: "rgba(56, 189, 248, 0.2)" },
    text: { color: "#38bdf8", bg: "rgba(56, 189, 248, 0.2)" },
    other: { color: "#94a3b8", bg: "rgba(148, 163, 184, 0.2)" },
};

export default function StorageChart({ files }) {
    // Calculate storage by type
    const breakdown = files.reduce((acc, file) => {
        if (file.type === "folder") return acc;
        const type = file.type || "other";
        acc[type] = (acc[type] || 0) + (file.size || 0);
        return acc;
    }, {});

    const total = Object.values(breakdown).reduce((a, b) => a + b, 0);
    const maxStorage = 10 * 1024 * 1024 * 1024; // 10 GB
    const usedPercent = ((total / maxStorage) * 100).toFixed(1);

    const formatSize = (bytes) => {
        if (bytes === 0) return "0 B";
        const gb = bytes / (1024 * 1024 * 1024);
        if (gb >= 1) return `${gb.toFixed(2)} GB`;
        const mb = bytes / (1024 * 1024);
        if (mb >= 1) return `${mb.toFixed(1)} MB`;
        const kb = bytes / 1024;
        return `${kb.toFixed(1)} KB`;
    };

    // Build segments for the ring chart
    const segments = [];
    let currentAngle = 0;

    Object.entries(breakdown).forEach(([type, size]) => {
        const percent = (size / maxStorage) * 100;
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

    return (
        <div className="storage-chart">
            <div className="storage-chart-title">Storage</div>

            {/* Donut chart */}
            <div className="storage-donut">
                <svg viewBox="0 0 100 100">
                    {/* Background ring */}
                    <circle
                        cx="50"
                        cy="50"
                        r="40"
                        fill="none"
                        stroke="rgba(255,255,255,0.1)"
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

            {/* Legend */}
            <div className="storage-legend">
                {Object.entries(breakdown).map(([type, size]) => (
                    <div key={type} className="storage-legend-item">
                        <span
                            className="storage-legend-dot"
                            style={{ background: colors[type]?.color || colors.other.color }}
                        />
                        <span className="storage-legend-type">{type}</span>
                        <span className="storage-legend-size">{formatSize(size)}</span>
                    </div>
                ))}
            </div>

            {/* Total */}
            <div className="storage-total">
                {formatSize(total)} of 10 GB
            </div>
        </div>
    );
}
