import React, { useState, useEffect, useRef } from 'react';
import { Eye, EyeOff, AlertCircle, User, Lock, Mail } from 'lucide-react';
import api from '../api';

export default function AuthPage({ onLogin }) {
    const [authMode, setAuthMode] = useState('login');
    const [email, setEmail] = useState('');
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [twoFactorCode, setTwoFactorCode] = useState('');
    const [temporaryToken, setTemporaryToken] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);
    const [resetToken, setResetToken] = useState('');
    const starsRef = useRef(null);
    const windsRef = useRef(null);

    const isLogin = authMode === 'login';
    const isRegister = authMode === 'register';
    const isForgotPassword = authMode === 'forgot';
    const isResetPassword = authMode === 'reset';
    const isTwoFactor = authMode === '2fa';

    const isResetPath = () => window.location.pathname === '/reset-password';

    const replaceAuthUrl = ({ resetPath = false, clearToken = false } = {}) => {
        const url = new URL(window.location.href);
        url.pathname = resetPath ? '/reset-password' : '/';
        if (clearToken) {
            url.searchParams.delete('reset_token');
        }
        window.history.replaceState({}, document.title, url.toString());
    };

    useEffect(() => {
        const container = starsRef.current;
        if (!container) return;
        container.innerHTML = '';
        const count = window.innerWidth < 768 ? 80 : 120;
        for (let i = 0; i < count; i++) {
            const star = document.createElement('div');
            star.className = 'sky-star';
            star.style.cssText = `
                left: ${Math.random() * 100}%;
                top: ${Math.random() * 100}%;
                --star-dur: ${2 + Math.random() * 4}s;
                --star-delay: ${Math.random() * 6}s;
                --star-max-op: ${0.15 + Math.random() * 0.5};
                width: ${1 + Math.random() * 2}px;
                height: ${1 + Math.random() * 2}px;
            `;
            container.appendChild(star);
        }
    }, []);

    useEffect(() => {
        const container = windsRef.current;
        if (!container) return;
        container.innerHTML = '';
        const positions = [8, 18, 28, 42, 55, 63, 72, 82, 91];
        positions.forEach((top) => {
            const wind = document.createElement('div');
            wind.className = 'sky-login__wind';
            const dur = (1.2 + Math.random() * 2).toFixed(1);
            const del = (Math.random() * 5).toFixed(1);
            const wid = 20 + Math.random() * 20;
            wind.style.cssText = `
                top: ${top}%;
                --wind-duration: ${dur}s;
                --wind-delay: ${del}s;
                width: ${wid}%;
            `;
            container.appendChild(wind);
        });
    }, []);

    useEffect(() => {
        const searchParams = new URLSearchParams(window.location.search);
        const token = searchParams.get('reset_token');
        if (token) {
            setResetToken(token);
            setAuthMode('reset');
            setError('');
            setMessage('Choose a new password for your account.');
            replaceAuthUrl({ resetPath: true, clearToken: true });
            return;
        }

        if (isResetPath()) {
            setAuthMode('reset');
            setError('');
            setMessage('Open the password reset link from your email to continue.');
        }
    }, []);

    const clearUrlResetToken = () => {
        replaceAuthUrl({ resetPath: isResetPath(), clearToken: true });
    };

    const resetToLogin = () => {
        setAuthMode('login');
        setUsername('');
        setPassword('');
        setConfirmPassword('');
        setTwoFactorCode('');
        setTemporaryToken('');
        setResetToken('');
        setShowPassword(false);
        setError('');
        replaceAuthUrl({ resetPath: false, clearToken: true });
    };

    const handleModeChange = (mode) => {
        setAuthMode(mode);
        setError('');
        setMessage('');
        setPassword('');
        setConfirmPassword('');
        setTwoFactorCode('');
        setShowPassword(false);
        if (mode !== 'reset') {
            setResetToken('');
            replaceAuthUrl({ resetPath: false, clearToken: true });
        } else {
            replaceAuthUrl({ resetPath: true, clearToken: true });
        }
        if (mode !== '2fa') {
            setTemporaryToken('');
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setMessage('');
        setLoading(true);

        try {
            if (isLogin) {
                const loginResponse = await api.login(email, password);
                if (loginResponse.requires_2fa) {
                    setTemporaryToken(loginResponse.temporary_token);
                    setPassword('');
                    setAuthMode('2fa');
                    setMessage('Enter the 6-digit code from your authenticator app.');
                    return;
                }
                const user = await api.getMe();
                onLogin(user);
            } else if (isTwoFactor) {
                await api.verifyTwoFactorLogin(temporaryToken, twoFactorCode);
                const user = await api.getMe();
                onLogin(user);
            } else if (isRegister) {
                await api.register(email, username, password);
                await api.login(email, password);
                const user = await api.getMe();
                onLogin(user);
            } else if (isForgotPassword) {
                const response = await api.requestPasswordReset(email);
                setMessage(response.detail || 'If an account exists for that email, a reset link has been sent.');
            } else if (isResetPassword) {
                if (!resetToken) {
                    throw new Error('Open the password reset link from your email to continue');
                }
                if (password !== confirmPassword) {
                    throw new Error('Passwords do not match');
                }
                const response = await api.resetPassword(resetToken, password);
                setMessage(response.detail || 'Password reset successfully. You can now sign in.');
                setPassword('');
                setConfirmPassword('');
                clearUrlResetToken();
                resetToLogin();
            }
        } catch (err) {
            setError(err.message || 'An error occurred');
        } finally {
            setLoading(false);
        }
    };

    const submitLabel = loading
        ? 'Please wait...'
        : isLogin
            ? 'Login'
            : isTwoFactor
                ? 'Verify Code'
            : isRegister
                ? 'Create Account'
                : isForgotPassword
                    ? 'Send Reset Link'
                    : 'Update Password';

    const emailField = !isResetPassword && !isTwoFactor && (
        <div className="sky-login__field">
            <div className="sky-login__cloud sky-login__cloud--1">
                <div className="sky-login__cloud-bump sky-login__cloud-bump--left" />
                <div className="sky-login__cloud-bump sky-login__cloud-bump--right" />
            </div>
            <div className="sky-login__string" />
            <div className="sky-login__glass-input">
                <input
                    type="email"
                    placeholder="Email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                />
            </div>
        </div>
    );

    const usernameField = isRegister && (
        <div className="sky-login__field">
            <div className="sky-login__cloud sky-login__cloud--3">
                <div className="sky-login__cloud-bump sky-login__cloud-bump--left-sm" />
                <div className="sky-login__cloud-bump sky-login__cloud-bump--right-xs" />
            </div>
            <div className="sky-login__string" />
            <div className="sky-login__glass-input">
                <input
                    type="text"
                    placeholder="Choose a username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    minLength={3}
                    required
                />
            </div>
        </div>
    );

    const passwordField = !isForgotPassword && !isTwoFactor && (
        <div className="sky-login__field">
            <div className="sky-login__cloud sky-login__cloud--2">
                <div className="sky-login__cloud-bump sky-login__cloud-bump--left-lg" />
                <div className="sky-login__cloud-bump sky-login__cloud-bump--right-md" />
            </div>
            <div className="sky-login__string" />
            <div className="sky-login__glass-input sky-login__glass-input--password">
                <input
                    type={showPassword ? 'text' : 'password'}
                    placeholder={isResetPassword ? 'New Password' : 'Password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    minLength={6}
                    required
                />
                <button
                    type="button"
                    className="sky-login__eye-toggle"
                    onClick={() => setShowPassword(!showPassword)}
                >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
            </div>
        </div>
    );

    const confirmPasswordField = isResetPassword && (
        <div className="sky-login__field">
            <div className="sky-login__cloud sky-login__cloud--3">
                <div className="sky-login__cloud-bump sky-login__cloud-bump--left-sm" />
                <div className="sky-login__cloud-bump sky-login__cloud-bump--right-xs" />
            </div>
            <div className="sky-login__string" />
            <div className="sky-login__glass-input sky-login__glass-input--password">
                <input
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Confirm New Password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    minLength={6}
                    required
                />
            </div>
        </div>
    );

    const twoFactorField = isTwoFactor && (
        <div className="sky-login__field">
            <div className="sky-login__cloud sky-login__cloud--2">
                <div className="sky-login__cloud-bump sky-login__cloud-bump--left-lg" />
                <div className="sky-login__cloud-bump sky-login__cloud-bump--right-md" />
            </div>
            <div className="sky-login__string" />
            <div className="sky-login__glass-input">
                <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]{6}"
                    placeholder="6-digit authentication code"
                    value={twoFactorCode}
                    onChange={(e) => setTwoFactorCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    required
                />
            </div>
        </div>
    );

    return (
        <main className="sky-login">
            <div className="sky-stars" ref={starsRef} />
            <div className="sky-winds" ref={windsRef} />

            <div className="sky-login__bg">
                <div className="sky-login__cloud-bg sky-login__cloud-bg--1" />
                <div className="sky-login__cloud-bg sky-login__cloud-bg--2" />
            </div>

            <header className="sky-login__header">
                <h1 className="sky-login__title">Home Cloud</h1>
                <p className="sky-login__subtitle sky-login__subtitle--desktop">Your files, floating gracefully.</p>
            </header>

            {error && (
                <div className="sky-login__error">
                    <AlertCircle size={16} />
                    <span>{error}</span>
                </div>
            )}

            {message && (
                <div className="sky-login__notice">
                    <span>{message}</span>
                </div>
            )}

            <form onSubmit={handleSubmit} className="sky-login__form sky-login__form--desktop">
                {emailField}
                {usernameField}
                {passwordField}
                {confirmPasswordField}
                {twoFactorField}

                <div className="sky-login__field">
                    <div className="sky-login__cloud sky-login__cloud--3">
                        <div className="sky-login__cloud-bump sky-login__cloud-bump--left-sm" />
                        <div className="sky-login__cloud-bump sky-login__cloud-bump--right-xs" />
                    </div>
                    <div className="sky-login__string" />
                    <button type="submit" className="sky-login__submit" disabled={loading}>
                        {submitLabel}
                    </button>
                </div>
            </form>

            <form onSubmit={handleSubmit} className="sky-login__form sky-login__form--mobile">
                <div className="sky-rig">
                    <div className="sky-rig__cloud">
                        <div className="sky-rig__cloud-bump sky-rig__cloud-bump--1" />
                        <div className="sky-rig__cloud-bump sky-rig__cloud-bump--2" />
                        <div className="sky-rig__cloud-bump sky-rig__cloud-bump--3" />
                        <div className="sky-rig__cloud-body" />
                    </div>

                    <div className="sky-rig__thread sky-rig__thread--long" />

                    {!isResetPassword && !isTwoFactor && (
                        <div className="sky-rig__card">
                            <div className="sky-rig__card-inner">
                                {isForgotPassword ? <Mail size={18} className="sky-rig__icon" /> : <User size={18} className="sky-rig__icon" />}
                                <input
                                    type="email"
                                    placeholder="Email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    required
                                />
                            </div>
                        </div>
                    )}

                    {isRegister && (
                        <>
                            <div className="sky-rig__thread sky-rig__thread--short" />
                            <div className="sky-rig__card">
                                <div className="sky-rig__card-inner">
                                    <User size={18} className="sky-rig__icon" />
                                    <input
                                        type="text"
                                        placeholder="Choose a username"
                                        value={username}
                                        onChange={(e) => setUsername(e.target.value)}
                                        minLength={3}
                                        required
                                    />
                                </div>
                            </div>
                        </>
                    )}

                    {!isForgotPassword && (
                        !isTwoFactor && (
                        <>
                            <div className="sky-rig__thread sky-rig__thread--short" />
                            <div className="sky-rig__card">
                                <div className="sky-rig__card-inner">
                                    <Lock size={18} className="sky-rig__icon" />
                                    <input
                                        type={showPassword ? 'text' : 'password'}
                                        placeholder={isResetPassword ? 'New Password' : 'Password'}
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        minLength={6}
                                        required
                                    />
                                    <button
                                        type="button"
                                        className="sky-login__eye-toggle"
                                        onClick={() => setShowPassword(!showPassword)}
                                    >
                                        {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                                    </button>
                                </div>
                            </div>
                        </>
                        )
                    )}

                    {isTwoFactor && (
                        <>
                            <div className="sky-rig__thread sky-rig__thread--short" />
                            <div className="sky-rig__card">
                                <div className="sky-rig__card-inner">
                                    <Lock size={18} className="sky-rig__icon" />
                                    <input
                                        type="text"
                                        inputMode="numeric"
                                        pattern="[0-9]{6}"
                                        placeholder="6-digit authentication code"
                                        value={twoFactorCode}
                                        onChange={(e) => setTwoFactorCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                        required
                                    />
                                </div>
                            </div>
                        </>
                    )}

                    {isResetPassword && (
                        <>
                            <div className="sky-rig__thread sky-rig__thread--short" />
                            <div className="sky-rig__card">
                                <div className="sky-rig__card-inner">
                                    <Lock size={18} className="sky-rig__icon" />
                                    <input
                                        type={showPassword ? 'text' : 'password'}
                                        placeholder="Confirm New Password"
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        minLength={6}
                                        required
                                    />
                                </div>
                            </div>
                        </>
                    )}

                    <div className="sky-rig__btn-wrap">
                        <button type="submit" className="sky-rig__btn" disabled={loading}>
                            <span>{submitLabel}</span>
                        </button>
                    </div>
                </div>
            </form>

            <footer className="sky-login__footer">
                {!isResetPassword && (
                    <button
                        type="button"
                        onClick={() => handleModeChange(isForgotPassword ? 'login' : 'forgot')}
                    >
                        {isForgotPassword ? 'Back to Sign In' : 'Forgot Password?'}
                    </button>
                )}
                {!isForgotPassword && !isResetPassword && !isTwoFactor && (
                    <button
                        type="button"
                        onClick={() => handleModeChange(isLogin ? 'register' : 'login')}
                    >
                        {isLogin ? 'Create Account' : 'Sign In'}
                    </button>
                )}
                {isTwoFactor && (
                    <button
                        type="button"
                        onClick={() => handleModeChange('login')}
                    >
                        Back to Sign In
                    </button>
                )}
                {isResetPassword && (
                    <button
                        type="button"
                        onClick={() => {
                            clearUrlResetToken();
                            resetToLogin();
                            setMessage('');
                        }}
                    >
                        Sign In
                    </button>
                )}
                <a href="#" onClick={(e) => e.preventDefault()}>Help</a>
            </footer>
        </main>
    );
}
