import React, { useState, useEffect, useCallback } from 'react';
import { Users, Shield, HardDrive, FileText, Trash2, Edit3, Check, X, ChevronDown, BarChart3, AlertTriangle } from 'lucide-react';
import api from '../api';

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

const QUOTA_PRESETS = [
    { label: '10 GB', value: 10737418240 },
    { label: '50 GB', value: 53687091200 },
    { label: '100 GB', value: 107374182400 },
    { label: '500 GB', value: 536870912000 },
    { label: '1 TB', value: 1099511627776 },
];

export default function AdminPanel() {
    const [users, setUsers] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [editingUser, setEditingUser] = useState(null);
    const [editQuota, setEditQuota] = useState('');
    const [deleteConfirm, setDeleteConfirm] = useState(null);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    const loadData = useCallback(async () => {
        try {
            setLoading(true);
            const [usersData, statsData] = await Promise.all([
                api.listUsers(),
                api.getSystemStats(),
            ]);
            setUsers(usersData);
            setStats(statsData);
        } catch (err) {
            setError('Failed to load admin data: ' + err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { loadData(); }, [loadData]);

    const handleUpdateQuota = async (userId) => {
        try {
            const quotaBytes = parseInt(editQuota);
            if (isNaN(quotaBytes) || quotaBytes < 0) {
                setError('Invalid quota value');
                return;
            }
            await api.updateUser(userId, { storage_quota: quotaBytes });
            setEditingUser(null);
            setSuccess('Quota updated successfully');
            setTimeout(() => setSuccess(''), 3000);
            loadData();
        } catch (err) {
            setError('Failed to update quota: ' + err.message);
        }
    };

    const handleToggleAdmin = async (userId, currentStatus) => {
        try {
            await api.updateUser(userId, { is_admin: !currentStatus });
            setSuccess(currentStatus ? 'Admin status removed' : 'Admin status granted');
            setTimeout(() => setSuccess(''), 3000);
            loadData();
        } catch (err) {
            setError('Failed to update admin status: ' + err.message);
        }
    };

    const handleDeleteUser = async (userId) => {
        try {
            await api.deleteUser(userId);
            setDeleteConfirm(null);
            setSuccess('User deleted successfully');
            setTimeout(() => setSuccess(''), 3000);
            loadData();
        } catch (err) {
            setError('Failed to delete user: ' + err.message);
        }
    };

    if (loading) {
        return (
            <div className="admin-panel">
                <div className="admin-loading">
                    <div className="loading-spinner" />
                    <p>Loading admin panel...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="admin-panel">
            <div className="admin-header">
                <div className="admin-header-title">
                    <Shield size={24} />
                    <h2>Admin Panel</h2>
                </div>
                <p className="admin-subtitle">Manage users, quotas, and system settings</p>
            </div>

            {error && (
                <div className="admin-alert admin-alert-error">
                    <AlertTriangle size={16} />
                    <span>{error}</span>
                    <button onClick={() => setError('')}><X size={14} /></button>
                </div>
            )}

            {success && (
                <div className="admin-alert admin-alert-success">
                    <Check size={16} />
                    <span>{success}</span>
                </div>
            )}

            {/* System Stats */}
            {stats && (
                <div className="admin-stats-grid">
                    <div className="admin-stat-card">
                        <div className="admin-stat-icon users-icon"><Users size={20} /></div>
                        <div className="admin-stat-info">
                            <span className="admin-stat-value">{stats.total_users}</span>
                            <span className="admin-stat-label">Total Users</span>
                        </div>
                    </div>
                    <div className="admin-stat-card">
                        <div className="admin-stat-icon files-icon"><FileText size={20} /></div>
                        <div className="admin-stat-info">
                            <span className="admin-stat-value">{stats.total_files}</span>
                            <span className="admin-stat-label">Total Files</span>
                        </div>
                    </div>
                    <div className="admin-stat-card">
                        <div className="admin-stat-icon storage-icon"><HardDrive size={20} /></div>
                        <div className="admin-stat-info">
                            <span className="admin-stat-value">{formatBytes(stats.total_storage_used)}</span>
                            <span className="admin-stat-label">Storage Used</span>
                        </div>
                    </div>
                    <div className="admin-stat-card">
                        <div className="admin-stat-icon disk-icon"><BarChart3 size={20} /></div>
                        <div className="admin-stat-info">
                            <span className="admin-stat-value">{formatBytes(stats.disk_free)}</span>
                            <span className="admin-stat-label">Disk Free</span>
                        </div>
                    </div>
                </div>
            )}

            {/* Users Table */}
            <div className="admin-section">
                <h3 className="admin-section-title">
                    <Users size={18} />
                    Users ({users.length})
                </h3>
                <div className="admin-table-wrapper">
                    <table className="admin-table">
                        <thead>
                            <tr>
                                <th>User</th>
                                <th>Files</th>
                                <th>Storage</th>
                                <th>Quota</th>
                                <th>Role</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {users.map(user => (
                                <tr key={user.id}>
                                    <td>
                                        <div className="admin-user-cell">
                                            <div className="admin-user-avatar">
                                                {user.username.charAt(0).toUpperCase()}
                                            </div>
                                            <div className="admin-user-details">
                                                <span className="admin-user-name">{user.username}</span>
                                                <span className="admin-user-email">{user.email}</span>
                                            </div>
                                        </div>
                                    </td>
                                    <td>{user.file_count}</td>
                                    <td>
                                        <div className="admin-storage-cell">
                                            <div className="admin-storage-bar">
                                                <div
                                                    className="admin-storage-fill"
                                                    style={{ width: `${Math.min((user.storage_used / user.storage_quota) * 100, 100)}%` }}
                                                />
                                            </div>
                                            <span>{formatBytes(user.storage_used)}</span>
                                        </div>
                                    </td>
                                    <td>
                                        {editingUser === user.id ? (
                                            <div className="admin-quota-edit">
                                                <select
                                                    value={editQuota}
                                                    onChange={e => setEditQuota(e.target.value)}
                                                    className="admin-quota-select"
                                                >
                                                    <option value="">Select...</option>
                                                    {QUOTA_PRESETS.map(p => (
                                                        <option key={p.value} value={p.value}>{p.label}</option>
                                                    ))}
                                                </select>
                                                <button className="admin-btn-sm admin-btn-confirm" onClick={() => handleUpdateQuota(user.id)}>
                                                    <Check size={14} />
                                                </button>
                                                <button className="admin-btn-sm admin-btn-cancel" onClick={() => setEditingUser(null)}>
                                                    <X size={14} />
                                                </button>
                                            </div>
                                        ) : (
                                            <div className="admin-quota-display" onClick={() => { setEditingUser(user.id); setEditQuota(user.storage_quota); }}>
                                                <span>{formatBytes(user.storage_quota)}</span>
                                                <Edit3 size={12} className="admin-edit-icon" />
                                            </div>
                                        )}
                                    </td>
                                    <td>
                                        <button
                                            className={`admin-role-badge ${user.is_admin ? 'admin' : 'user'}`}
                                            onClick={() => handleToggleAdmin(user.id, user.is_admin)}
                                            title={user.is_admin ? 'Remove admin' : 'Make admin'}
                                        >
                                            {user.is_admin ? '⚡ Admin' : '👤 User'}
                                        </button>
                                    </td>
                                    <td>
                                        {deleteConfirm === user.id ? (
                                            <div className="admin-delete-confirm">
                                                <span>Sure?</span>
                                                <button className="admin-btn-sm admin-btn-danger" onClick={() => handleDeleteUser(user.id)}>Yes</button>
                                                <button className="admin-btn-sm admin-btn-cancel" onClick={() => setDeleteConfirm(null)}>No</button>
                                            </div>
                                        ) : (
                                            <button className="admin-btn-sm admin-btn-delete" onClick={() => setDeleteConfirm(user.id)}>
                                                <Trash2 size={14} />
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
