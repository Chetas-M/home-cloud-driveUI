import React, { useState, useCallback, useEffect } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';

let toastIdCounter = 0;
let addToastExternal = null;

// Global function to show toasts from anywhere
export function showToast(message, type = 'info', duration = 3500) {
    if (addToastExternal) {
        addToastExternal({ message, type, duration });
    }
}

const ICONS = {
    success: CheckCircle,
    error: XCircle,
    warning: AlertTriangle,
    info: Info,
};

export default function ToastContainer() {
    const [toasts, setToasts] = useState([]);

    const addToast = useCallback(({ message, type = 'info', duration = 3500 }) => {
        const id = ++toastIdCounter;
        setToasts(prev => [...prev, { id, message, type, exiting: false }]);

        // Auto-dismiss
        setTimeout(() => {
            setToasts(prev =>
                prev.map(t => (t.id === id ? { ...t, exiting: true } : t))
            );
            setTimeout(() => {
                setToasts(prev => prev.filter(t => t.id !== id));
            }, 300); // match CSS exit animation
        }, duration);
    }, []);

    // Expose addToast globally
    useEffect(() => {
        addToastExternal = addToast;
        return () => { addToastExternal = null; };
    }, [addToast]);

    const dismiss = (id) => {
        setToasts(prev =>
            prev.map(t => (t.id === id ? { ...t, exiting: true } : t))
        );
        setTimeout(() => {
            setToasts(prev => prev.filter(t => t.id !== id));
        }, 300);
    };

    if (toasts.length === 0) return null;

    return (
        <div className="toast-container">
            {toasts.map(toast => {
                const Icon = ICONS[toast.type] || ICONS.info;
                return (
                    <div
                        key={toast.id}
                        className={`toast toast--${toast.type} ${toast.exiting ? 'toast--exit' : ''}`}
                    >
                        <Icon size={18} className="toast__icon" />
                        <span className="toast__message">{toast.message}</span>
                        <button className="toast__close" onClick={() => dismiss(toast.id)}>
                            <X size={14} />
                        </button>
                    </div>
                );
            })}
        </div>
    );
}
