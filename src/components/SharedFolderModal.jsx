import React, { useEffect, useState } from "react";
import { Mail, Shield, Trash2, UserPlus, Users, X } from "lucide-react";
import api from "../api";

const roles = [
    { value: "viewer", label: "Viewer" },
    { value: "editor", label: "Editor" },
    { value: "admin", label: "Admin" },
];

export default function SharedFolderModal({ folder, onClose }) {
    const [identifier, setIdentifier] = useState("");
    const [role, setRole] = useState("viewer");
    const [entries, setEntries] = useState([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");

    const loadEntries = async () => {
        setLoading(true);
        setError("");
        try {
            const data = await api.getFolderAccess(folder.id);
            setEntries(data);
        } catch (err) {
            setError(err.message || "Failed to load folder access");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadEntries();
    }, [folder.id]);

    const handleInvite = async () => {
        if (!identifier.trim()) {
            setError("Enter an email or username.");
            return;
        }
        setSaving(true);
        setError("");
        try {
            await api.inviteFolderAccess(folder.id, identifier.trim(), role);
            setIdentifier("");
            await loadEntries();
        } catch (err) {
            setError(err.message || "Failed to add access");
        } finally {
            setSaving(false);
        }
    };

    const handleRoleChange = async (accessId, nextRole) => {
        setSaving(true);
        setError("");
        try {
            await api.updateFolderAccess(folder.id, accessId, nextRole);
            await loadEntries();
        } catch (err) {
            setError(err.message || "Failed to update role");
        } finally {
            setSaving(false);
        }
    };

    const handleRemove = async (accessId) => {
        setSaving(true);
        setError("");
        try {
            await api.removeFolderAccess(folder.id, accessId);
            await loadEntries();
        } catch (err) {
            setError(err.message || "Failed to remove access");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content share-modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h3><Users size={18} /> Shared access for "{folder.name}"</h3>
                    <button className="modal-close" onClick={onClose}><X size={18} /></button>
                </div>

                {error && <div className="share-error">{error}</div>}

                <div className="share-form">
                    <div className="share-field">
                        <label><Mail size={14} /> Invite by email or username</label>
                        <input
                            className="share-input"
                            value={identifier}
                            onChange={(e) => setIdentifier(e.target.value)}
                            placeholder="jane@example.com or janedoe"
                        />
                    </div>

                    <div className="share-field">
                        <label><Shield size={14} /> Role</label>
                        <select className="share-select" value={role} onChange={(e) => setRole(e.target.value)}>
                            {roles.map((item) => (
                                <option key={item.value} value={item.value}>{item.label}</option>
                            ))}
                        </select>
                    </div>

                    <button className="share-create-btn" onClick={handleInvite} disabled={saving}>
                        <UserPlus size={16} />
                        {saving ? "Saving..." : "Invite user"}
                    </button>
                </div>

                <div className="share-existing">
                    <h4>People with access</h4>
                    {loading ? (
                        <p className="move-empty">Loading access…</p>
                    ) : entries.length === 0 ? (
                        <p className="move-empty">No one else has access yet.</p>
                    ) : (
                        <div className="share-links-list">
                            {entries.map((entry) => (
                                <div key={entry.id} className="share-link-item">
                                    <div className="share-link-info">
                                        <strong>{entry.username}</strong>
                                        <span className="share-link-meta">{entry.email}</span>
                                    </div>
                                    <div className="share-link-info">
                                        <select
                                            className="share-select"
                                            value={entry.role}
                                            onChange={(e) => handleRoleChange(entry.id, e.target.value)}
                                            disabled={saving}
                                        >
                                            {roles.map((item) => (
                                                <option key={item.value} value={item.value}>{item.label}</option>
                                            ))}
                                        </select>
                                        <button className="share-revoke-btn" onClick={() => handleRemove(entry.id)} disabled={saving}>
                                            <Trash2 size={14} />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
