import React, { useEffect, useState } from "react";
import { KeyRound, Laptop, Shield, ShieldCheck, Smartphone, X } from "lucide-react";
import api from "../api";

function formatDate(value) {
    if (!value) return "Unknown";
    return new Date(value).toLocaleString();
}

export default function SecurityModal({ user, onClose, onUserUpdate, onSignedOut }) {
    const [sessions, setSessions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const [setupData, setSetupData] = useState(null);
    const [enableCode, setEnableCode] = useState("");
    const [disablePassword, setDisablePassword] = useState("");
    const [disableCode, setDisableCode] = useState("");
    const [busyAction, setBusyAction] = useState("");

    useEffect(() => {
        loadSessions();
    }, []);

    const loadSessions = async () => {
        try {
            setLoading(true);
            const data = await api.getSessions();
            setSessions(data);
        } catch (err) {
            setError(err.message || "Failed to load sessions");
        } finally {
            setLoading(false);
        }
    };

    const startSetup = async () => {
        try {
            setBusyAction("setup");
            setError("");
            setSuccess("");
            const data = await api.getTwoFactorSetup();
            setSetupData(data);
        } catch (err) {
            setError(err.message || "Failed to start 2FA setup");
        } finally {
            setBusyAction("");
        }
    };

    const handleEnableTwoFactor = async (e) => {
        e.preventDefault();
        try {
            setBusyAction("enable");
            setError("");
            setSuccess("");
            const updatedUser = await api.enableTwoFactor(enableCode);
            onUserUpdate(updatedUser);
            setSetupData(null);
            setEnableCode("");
            setSuccess("Two-factor authentication is now enabled.");
        } catch (err) {
            setError(err.message || "Failed to enable 2FA");
        } finally {
            setBusyAction("");
        }
    };

    const handleDisableTwoFactor = async (e) => {
        e.preventDefault();
        try {
            setBusyAction("disable");
            setError("");
            setSuccess("");
            const updatedUser = await api.disableTwoFactor(disablePassword, disableCode);
            onUserUpdate(updatedUser);
            setDisablePassword("");
            setDisableCode("");
            setSuccess("Two-factor authentication has been disabled.");
        } catch (err) {
            setError(err.message || "Failed to disable 2FA");
        } finally {
            setBusyAction("");
        }
    };

    const handleRevokeSession = async (session) => {
        try {
            setBusyAction(session.id);
            setError("");
            setSuccess("");
            await api.revokeSession(session.id);
            setSessions((prev) => prev.map((item) => (
                item.id === session.id ? { ...item, revoked_at: new Date().toISOString() } : item
            )));

            if (session.is_current) {
                onSignedOut();
                return;
            }

            setSuccess("Session revoked.");
        } catch (err) {
            setError(err.message || "Failed to revoke session");
        } finally {
            setBusyAction("");
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content security-modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <div className="modal-icon">
                        <Shield size={24} />
                    </div>
                    <h3>Account Security</h3>
                    <button className="modal-close" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                {error && <div className="security-alert security-alert--error">{error}</div>}
                {success && <div className="security-alert security-alert--success">{success}</div>}

                <section className="security-section">
                    <div className="security-section__header">
                        <div>
                            <h4>Two-Factor Authentication</h4>
                            <p>Add a time-based code from your authenticator app when you sign in.</p>
                        </div>
                        <span className={`security-badge ${user?.two_factor_enabled ? "is-enabled" : ""}`}>
                            {user?.two_factor_enabled ? <ShieldCheck size={14} /> : <KeyRound size={14} />}
                            {user?.two_factor_enabled ? "Enabled" : "Disabled"}
                        </span>
                    </div>

                    {!user?.two_factor_enabled && !setupData && (
                        <button
                            className="btn-primary security-inline-btn"
                            onClick={startSetup}
                            disabled={busyAction === "setup"}
                        >
                            {busyAction === "setup" ? "Preparing..." : "Set up 2FA"}
                        </button>
                    )}

                    {!user?.two_factor_enabled && setupData && (
                        <div className="security-setup">
                            <p className="security-help">
                                Add this key in Google Authenticator or any TOTP app, then enter the 6-digit code.
                            </p>
                            <div className="security-secret-card">
                                <label>Manual setup key</label>
                                <code>{setupData.secret}</code>
                            </div>
                            <div className="security-secret-card">
                                <label>Authenticator link</label>
                                <input value={setupData.otpauth_url} readOnly />
                            </div>
                            <form className="security-form" onSubmit={handleEnableTwoFactor}>
                                <input
                                    type="text"
                                    inputMode="numeric"
                                    pattern="[0-9]{6}"
                                    className="modal-input"
                                    placeholder="123456"
                                    value={enableCode}
                                    onChange={(e) => setEnableCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                                    required
                                />
                                <div className="modal-actions">
                                    <button
                                        type="button"
                                        className="btn-secondary"
                                        onClick={() => {
                                            setSetupData(null);
                                            setEnableCode("");
                                        }}
                                    >
                                        Cancel
                                    </button>
                                    <button type="submit" className="btn-primary" disabled={busyAction === "enable" || enableCode.length !== 6}>
                                        {busyAction === "enable" ? "Enabling..." : "Enable 2FA"}
                                    </button>
                                </div>
                            </form>
                        </div>
                    )}

                    {user?.two_factor_enabled && (
                        <form className="security-form" onSubmit={handleDisableTwoFactor}>
                            <p className="security-help">
                                To disable 2FA, confirm your password and a current authenticator code.
                            </p>
                            <input
                                type="password"
                                className="modal-input"
                                placeholder="Current password"
                                value={disablePassword}
                                onChange={(e) => setDisablePassword(e.target.value)}
                                required
                            />
                            <input
                                type="text"
                                inputMode="numeric"
                                pattern="[0-9]{6}"
                                className="modal-input"
                                placeholder="6-digit authenticator code"
                                value={disableCode}
                                onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                                required
                            />
                            <div className="modal-actions">
                                <button type="submit" className="btn-secondary" disabled={busyAction === "disable"}>
                                    {busyAction === "disable" ? "Disabling..." : "Disable 2FA"}
                                </button>
                            </div>
                        </form>
                    )}
                </section>

                <section className="security-section">
                    <div className="security-section__header">
                        <div>
                            <h4>Active Sessions</h4>
                            <p>Review devices that are signed into your account and revoke any you do not trust.</p>
                        </div>
                        <button className="btn-secondary security-inline-btn" onClick={loadSessions} disabled={loading}>
                            {loading ? "Refreshing..." : "Refresh"}
                        </button>
                    </div>

                    <div className="security-sessions">
                        {sessions.map((session) => (
                            <article key={session.id} className={`security-session-card ${session.revoked_at ? "is-revoked" : ""}`}>
                                <div className="security-session-card__main">
                                    <div className="security-session-card__icon">
                                        {session.device_name?.toLowerCase().includes("android") || session.device_name?.toLowerCase().includes("ios")
                                            ? <Smartphone size={18} />
                                            : <Laptop size={18} />}
                                    </div>
                                    <div>
                                        <div className="security-session-card__title">
                                            <strong>{session.device_name || "Unknown device"}</strong>
                                            {session.is_current && <span className="security-chip">Current</span>}
                                            {session.is_suspicious && !session.revoked_at && <span className="security-chip warning">New login</span>}
                                            {session.revoked_at && <span className="security-chip muted">Revoked</span>}
                                        </div>
                                        <p>{session.ip_address || "Unknown IP"}</p>
                                        <p>Last active: {formatDate(session.last_seen_at)}</p>
                                        <p>Signed in: {formatDate(session.created_at)}</p>
                                    </div>
                                </div>
                                {!session.revoked_at && (
                                    <button
                                        className="btn-secondary security-revoke-btn"
                                        onClick={() => handleRevokeSession(session)}
                                        disabled={busyAction === session.id}
                                    >
                                        {busyAction === session.id ? "Revoking..." : (session.is_current ? "Sign out" : "Revoke")}
                                    </button>
                                )}
                            </article>
                        ))}
                    </div>
                </section>
            </div>
        </div>
    );
}
