import React, { useState, useEffect } from 'react';
import { Share2, Copy, Check, X, Lock, Clock, Download, Link2, Trash2, Eye } from 'lucide-react';
import api from '../api';

export default function ShareModal({ file, onClose }) {
    const [permission, setPermission] = useState('download');
    const [password, setPassword] = useState('');
    const [usePassword, setUsePassword] = useState(false);
    const [expiresHours, setExpiresHours] = useState('');
    const [maxDownloads, setMaxDownloads] = useState('');
    const [existingLinks, setExistingLinks] = useState([]);
    const [newLink, setNewLink] = useState(null);
    const [copied, setCopied] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        loadLinks();
    }, []);

    const loadLinks = async () => {
        try {
            const links = await api.getMyShareLinks();
            setExistingLinks(links.filter(l => l.file_id === file.id && l.is_active));
        } catch (err) {
            console.error('Failed to load share links:', err);
        }
    };

    const handleCreate = async () => {
        try {
            setLoading(true);
            setError('');
            const data = {
                file_id: file.id,
                permission,
            };
            if (usePassword && password) data.password = password;
            if (expiresHours) data.expires_in_hours = parseInt(expiresHours);
            if (maxDownloads) data.max_downloads = parseInt(maxDownloads);

            const link = await api.createShareLink(data);
            setNewLink(link);
            loadLinks();
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleCopy = () => {
        const url = `${window.location.origin}/shared/${newLink.token}`;
        navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleRevoke = async (linkId) => {
        try {
            await api.revokeShareLink(linkId);
            loadLinks();
        } catch (err) {
            setError(err.message);
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content share-modal" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <h3><Share2 size={18} /> Share "{file.name}"</h3>
                    <button className="modal-close" onClick={onClose}><X size={18} /></button>
                </div>

                {error && <div className="share-error">{error}</div>}

                {newLink ? (
                    <div className="share-link-created">
                        <div className="share-success-icon"><Check size={32} /></div>
                        <p className="share-success-text">Share link created!</p>
                        <div className="share-link-url">
                            <input
                                type="text"
                                readOnly
                                value={`${window.location.origin}/shared/${newLink.token}`}
                            />
                            <button className="share-copy-btn" onClick={handleCopy}>
                                {copied ? <Check size={16} /> : <Copy size={16} />}
                                {copied ? 'Copied!' : 'Copy'}
                            </button>
                        </div>
                        <div className="share-link-details">
                            {newLink.has_password && <span className="share-badge"><Lock size={12} /> Password protected</span>}
                            {newLink.expires_at && <span className="share-badge"><Clock size={12} /> Expires {new Date(newLink.expires_at).toLocaleDateString()}</span>}
                            {newLink.max_downloads && <span className="share-badge"><Download size={12} /> Max {newLink.max_downloads} downloads</span>}
                        </div>
                        <button className="share-new-btn" onClick={() => setNewLink(null)}>Create another link</button>
                    </div>
                ) : (
                    <div className="share-form">
                        {/* Permission */}
                        <div className="share-field">
                            <label>Permission</label>
                            <div className="share-permission-toggle">
                                <button
                                    className={`share-perm-btn ${permission === 'view' ? 'active' : ''}`}
                                    onClick={() => setPermission('view')}
                                >
                                    <Eye size={14} /> View only
                                </button>
                                <button
                                    className={`share-perm-btn ${permission === 'download' ? 'active' : ''}`}
                                    onClick={() => setPermission('download')}
                                >
                                    <Download size={14} /> Download
                                </button>
                            </div>
                        </div>

                        {/* Password */}
                        <div className="share-field">
                            <label className="share-checkbox-label">
                                <input type="checkbox" checked={usePassword} onChange={e => setUsePassword(e.target.checked)} />
                                <Lock size={14} /> Password protect
                            </label>
                            {usePassword && (
                                <input
                                    type="password"
                                    placeholder="Enter password..."
                                    value={password}
                                    onChange={e => setPassword(e.target.value)}
                                    className="share-input"
                                />
                            )}
                        </div>

                        {/* Expiry */}
                        <div className="share-field">
                            <label><Clock size={14} /> Expires after</label>
                            <select value={expiresHours} onChange={e => setExpiresHours(e.target.value)} className="share-select">
                                <option value="">Never</option>
                                <option value="1">1 hour</option>
                                <option value="24">1 day</option>
                                <option value="168">1 week</option>
                                <option value="720">30 days</option>
                            </select>
                        </div>

                        {/* Max downloads */}
                        <div className="share-field">
                            <label><Download size={14} /> Max downloads</label>
                            <select value={maxDownloads} onChange={e => setMaxDownloads(e.target.value)} className="share-select">
                                <option value="">Unlimited</option>
                                <option value="1">1</option>
                                <option value="5">5</option>
                                <option value="10">10</option>
                                <option value="50">50</option>
                            </select>
                        </div>

                        <button className="share-create-btn" onClick={handleCreate} disabled={loading}>
                            <Link2 size={16} />
                            {loading ? 'Creating...' : 'Create share link'}
                        </button>
                    </div>
                )}

                {/* Existing links */}
                {existingLinks.length > 0 && (
                    <div className="share-existing">
                        <h4>Active links ({existingLinks.length})</h4>
                        <div className="share-links-list">
                            {existingLinks.map(link => (
                                <div key={link.id} className="share-link-item">
                                    <div className="share-link-info">
                                        <span className="share-link-perm">{link.permission === 'download' ? '⬇️' : '👁️'} {link.permission}</span>
                                        <span className="share-link-meta">{link.download_count} downloads</span>
                                        {link.has_password && <Lock size={12} />}
                                    </div>
                                    <button className="share-revoke-btn" onClick={() => handleRevoke(link.id)}>
                                        <Trash2 size={14} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
