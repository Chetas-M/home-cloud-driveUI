/**
 * Home Cloud Drive - API Service
 * Handles all API calls to the backend
 */

// Use relative URL in production (nginx proxies /api to backend)
// In development, this can be overridden
const LOCAL_API_HOSTS = new Set(['localhost', '127.0.0.1', '::1']);
const API_BASE_URL = LOCAL_API_HOSTS.has(window.location.hostname)
    ? 'http://localhost:8000/api'
    : '/api';
const RESUMABLE_UPLOAD_KEY = 'hcd.resumableUploads';

function loadResumableSessions() {
    try {
        return JSON.parse(localStorage.getItem(RESUMABLE_UPLOAD_KEY)) || {};
    } catch (err) {
        return {};
    }
}

function persistResumableSessions(sessions) {
    try {
        localStorage.setItem(RESUMABLE_UPLOAD_KEY, JSON.stringify(sessions));
    } catch (err) {
        // Ignore storage quota errors; resumable uploads can still proceed without persistence.
    }
}

function buildUploadFingerprint(file, path) {
    return `${file.name}|${file.size}|${file.lastModified || 0}|${JSON.stringify(path)}`;
}

class ApiService {
    constructor() {
        this.token = localStorage.getItem('token');
    }

    setToken(token) {
        this.token = token;
        if (token) {
            localStorage.setItem('token', token);
        } else {
            localStorage.removeItem('token');
        }
    }

    getToken() {
        return this.token || localStorage.getItem('token');
    }

    async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;
        const headers = {
            ...options.headers,
        };

        if (this.getToken() && !options.skipAuth) {
            headers['Authorization'] = `Bearer ${this.getToken()}`;
        }

        // Don't set Content-Type for FormData (browser will set it with boundary)
        if (!(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }

        const response = await fetch(url, {
            ...options,
            headers,
        });

        if (response.status === 401) {
            this.setToken(null);
            window.location.reload();
            throw new Error('Unauthorized');
        }

        if (response.status === 429) {
            throw new Error('Too many attempts. Please try again later.');
        }

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            const detail = typeof error.detail === 'string' ? error.detail : 'Request failed';
            const code = typeof error.code === 'string' ? error.code : null;

            if (code === 'PASSWORD_RESET_NOT_CONFIGURED') {
                throw new Error('Password reset is unavailable right now because the server email setup is incomplete. Please contact the administrator.');
            }
            throw new Error(detail);
        }

        // Handle empty responses (204 No Content)
        if (response.status === 204) {
            return null;
        }

        return response.json();
    }

    // ============ AUTH ============
    async register(email, username, password) {
        const data = await this.request('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, username, password }),
            skipAuth: true,
        });
        return data;
    }

    async login(email, password) {
        const formData = new URLSearchParams();
        formData.append('username', email); // OAuth2 expects 'username' field
        formData.append('password', password);

        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData,
        });

        if (response.status === 429) {
            throw new Error('Too many login attempts. Please wait a minute and try again.');
        }

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Login failed' }));
            throw new Error(error.detail || 'Login failed');
        }

        const data = await response.json();
        if (data.access_token) {
            this.setToken(data.access_token);
        }
        return data;
    }

    async verifyTwoFactorLogin(temporaryToken, code) {
        const data = await this.request('/auth/login/2fa', {
            method: 'POST',
            body: JSON.stringify({ temporary_token: temporaryToken, code }),
            skipAuth: true,
        });
        if (data.access_token) {
            this.setToken(data.access_token);
        }
        return data;
    }

    async getMe() {
        return this.request('/auth/me');
    }

    logout() {
        this.setToken(null);
    }

    async logoutCurrentSession() {
        try {
            await this.request('/auth/logout', {
                method: 'POST',
            });
        } finally {
            this.setToken(null);
        }
    }

    async changePassword(currentPassword, newPassword) {
        return this.request('/auth/password', {
            method: 'PATCH',
            body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
        });
    }

    async requestPasswordReset(email) {
        return this.request('/auth/forgot-password', {
            method: 'POST',
            body: JSON.stringify({ email }),
            skipAuth: true,
        });
    }

    async resetPassword(token, newPassword) {
        return this.request('/auth/reset-password', {
            method: 'POST',
            body: JSON.stringify({ token, new_password: newPassword }),
            skipAuth: true,
        });
    }

    async getTwoFactorSetup() {
        return this.request('/auth/2fa/setup', {
            method: 'POST',
        });
    }

    async enableTwoFactor(code) {
        return this.request('/auth/2fa/enable', {
            method: 'POST',
            body: JSON.stringify({ code }),
        });
    }

    async disableTwoFactor(password, code) {
        return this.request('/auth/2fa/disable', {
            method: 'POST',
            body: JSON.stringify({ password, code }),
        });
    }

    async getSessions() {
        return this.request('/auth/sessions');
    }

    async revokeSession(sessionId) {
        return this.request(`/auth/sessions/${sessionId}`, {
            method: 'DELETE',
        });
    }

    // ============ FILES ============
    async listFiles(path = [], options = {}) {
        const params = new URLSearchParams();
        params.append('path', JSON.stringify(path));
        if (options.includeTrash) params.append('include_trashed', 'true');
        if (options.starredOnly) params.append('starred_only', 'true');

        return this.request(`/files?${params.toString()}`);
    }

    async uploadFiles(files, path = []) {
        const formData = new FormData();
        files.forEach(file => {
            formData.append('files', file);
        });

        const params = new URLSearchParams();
        params.append('path', JSON.stringify(path));

        return this.request(`/files/upload?${params.toString()}`, {
            method: 'POST',
            body: formData,
        });
    }

    async getUploadStatus(uploadId) {
        return this.request(`/files/upload/${uploadId}/status`);
    }

    /**
     * Upload a single file using chunked resumable upload with real-time progress tracking.
     * @param {File} file - The file to upload
     * @param {Array} path - Current folder path
     * @param {Function} onProgress - Callback: ({ loaded, total, percent, speed, eta })
     * @returns {{ promise: Promise, abort: Function }}
     */
    uploadFileWithProgress(file, path = [], onProgress) {
        let isAborted = false;
        let currentXhr = null;

        const promise = new Promise(async (resolve, reject) => {
            const sessions = loadResumableSessions();
            const fingerprint = buildUploadFingerprint(file, path);

            const updateSession = (data) => {
                sessions[fingerprint] = { ...(sessions[fingerprint] || {}), ...data };
                persistResumableSessions(sessions);
            };

            const clearSession = () => {
                delete sessions[fingerprint];
                persistResumableSessions(sessions);
            };

            const emitProgress = (loaded, avgSpeed = 0) => {
                const total = file.size;
                const safeLoaded = Math.min(loaded, total);
                const percent = total > 0 ? Math.round((safeLoaded / total) * 100) : 100;
                const remaining = Math.max(total - safeLoaded, 0);
                const eta = avgSpeed > 0 ? Math.ceil(remaining / avgSpeed) : 0;

                onProgress?.({
                    loaded: safeLoaded,
                    total,
                    percent,
                    speed: avgSpeed,
                    eta,
                });
            };

            try {
                let status = null;

                if (sessions[fingerprint]?.upload_id) {
                    try {
                        const candidate = await this.getUploadStatus(sessions[fingerprint].upload_id);
                        const candidatePath = Array.isArray(candidate.path) ? candidate.path : [];
                        const pathMatches =
                            candidate.path === undefined ||
                            candidatePath.length === 0 ||
                            JSON.stringify(candidatePath) === JSON.stringify(path || []);
                        if (candidate.total_size === file.size && pathMatches) {
                            status = candidate;
                        } else {
                            clearSession();
                        }
                    } catch (err) {
                        clearSession();
                    }
                }

                if (isAborted) throw new Error('Upload cancelled');

                if (!status) {
                    const initPayload = {
                        filename: file.name,
                        total_size: file.size,
                        path: path,
                    };
                    if (file.type) {
                        initPayload.mime_type = file.type;
                    }

                    const initRes = await this.request('/files/upload/init', {
                        method: 'POST',
                        body: JSON.stringify(initPayload),
                    });

                    status = {
                        upload_id: initRes.upload_id,
                        chunk_size: initRes.chunk_size,
                        uploaded_chunks: [],
                        uploaded_bytes: 0,
                        total_size: file.size,
                        path,
                    };
                    updateSession({
                        upload_id: initRes.upload_id,
                        path,
                        filename: file.name,
                    });
                }

                const { upload_id, chunk_size } = status;
                const totalChunks = Math.ceil(file.size / chunk_size) || 1; // Handle 0-byte files

                let loadedBytes = Math.min(status.uploaded_bytes || 0, file.size);
                let lastLoaded = loadedBytes;
                let lastTime = Date.now();
                let speedSamples = [];
                const uploadedChunks = new Set(status.uploaded_chunks || []);
                emitProgress(loadedBytes, 0);

                // 2. Upload Chunks sequentially
                for (let i = 0; i < totalChunks; i++) {
                    if (isAborted) throw new Error('Upload cancelled');

                    const start = i * chunk_size;
                    const end = Math.min(start + chunk_size, file.size);
                    const chunk = file.slice(start, end);
                    const chunkLength = end - start;

                    if (uploadedChunks.has(i)) {
                        // Bytes for this chunk are already reflected in the initial loadedBytes
                        // (from status.uploaded_bytes). Do not add them again.
                        emitProgress(loadedBytes, 0);
                        continue;
                    }

                    let chunkSuccess = false;
                    let retries = 0;
                    const maxRetries = 3;

                    while (!chunkSuccess && retries < maxRetries) {
                        if (isAborted) throw new Error('Upload cancelled');

                        try {
                            await new Promise((chunkResolve, chunkReject) => {
                                const formData = new FormData();
                                formData.append('file', chunk);

                                const xhr = new XMLHttpRequest();
                                currentXhr = xhr;
                                const url = `${API_BASE_URL}/files/upload/${upload_id}/chunk?chunk_index=${i}`;

                                xhr.open('POST', url);
                                xhr.setRequestHeader('Authorization', `Bearer ${this.getToken()}`);

                                xhr.upload.onprogress = (e) => {
                                    if (!e.lengthComputable || isAborted) return;
                                    
                                    // Calculate overall progress
                                    const currentLoaded = loadedBytes + e.loaded;
                                    const now = Date.now();
                                    const elapsed = (now - lastTime) / 1000;

                                    if (elapsed >= 0.3) {
                                        const bytesPerSec = (currentLoaded - lastLoaded) / Math.max(elapsed, 0.001);
                                        speedSamples.push(bytesPerSec);
                                        if (speedSamples.length > 5) speedSamples.shift();
                                        lastLoaded = currentLoaded;
                                        lastTime = now;
                                    }

                                    const avgSpeed = speedSamples.length > 0
                                        ? speedSamples.reduce((a, b) => a + b, 0) / speedSamples.length
                                        : 0;
                                    let remaining;
                                    let eta;
                                    let percent;

                                    if (file.size > 0) {
                                        remaining = file.size - currentLoaded;
                                        eta = avgSpeed > 0 ? Math.ceil(remaining / avgSpeed) : 0;
                                        percent = Math.round((currentLoaded / file.size) * 100);
                                    } else {
                                        // Handle 0-byte files explicitly to avoid NaN progress values
                                        remaining = 0;
                                        eta = 0;
                                        percent = 100;
                                    }

                                    onProgress?.({
                                        loaded: currentLoaded,
                                        total: file.size,
                                        percent,
                                        speed: avgSpeed,
                                        eta,
                                    });
                                };

                                xhr.onload = () => {
                                    currentXhr = null;
                                    if (xhr.status >= 200 && xhr.status < 300) {
                                        chunkResolve();
                                    } else {
                                        chunkReject(new Error(`Chunk upload failed: ${xhr.status}`));
                                    }
                                };

                                xhr.onerror = () => {
                                    currentXhr = null;
                                    chunkReject(new Error('Network error uploading chunk'));
                                };
                                
                                xhr.onabort = () => {
                                    currentXhr = null;
                                    chunkReject(new Error('Upload cancelled'));
                                };

                                xhr.send(formData);
                            });
                            
                            chunkSuccess = true;
                            loadedBytes += chunkLength;
                            uploadedChunks.add(i);
                            // Only persist the upload_id, path, and filename.
                            // uploaded_chunks/uploaded_bytes are fetched from the server on resume,
                            // so storing the full set would waste localStorage space needlessly.
                            updateSession({
                                upload_id,
                                path,
                                filename: file.name,
                            });
                            const avgSpeed = speedSamples.length > 0
                                ? speedSamples.reduce((a, b) => a + b, 0) / speedSamples.length
                                : 0;
                            emitProgress(loadedBytes, avgSpeed);
                        } catch (err) {
                            if (err.message === 'Upload cancelled') throw err;
                            retries++;
                            if (retries >= maxRetries) {
                                throw new Error(`Failed to upload chunk ${i} after ${maxRetries} attempts.`);
                            }
                            // Exponential backoff
                            await new Promise(r => setTimeout(r, 1000 * Math.pow(2, retries)));
                        }
                    }
                }

                if (isAborted) throw new Error('Upload cancelled');

                // 3. Complete Upload
                const completeRes = await this.request('/files/upload/complete', {
                    method: 'POST',
                    body: JSON.stringify({
                        upload_id: upload_id,
                        filename: file.name,
                        total_size: file.size,
                        path: path,
                        mime_type: file.type || undefined,
                    }),
                });

                clearSession();
                resolve(completeRes);

            } catch (err) {
                reject(err);
            }
        });

        return { 
            promise, 
            abort: () => {
                isAborted = true;
                if (currentXhr) {
                    currentXhr.abort();
                }
            } 
        };
    }

    async downloadFile(fileId) {
        const response = await fetch(`${API_BASE_URL}/files/${fileId}/download`, {
            headers: {
                'Authorization': `Bearer ${this.getToken()}`,
            },
        });

        if (!response.ok) {
            throw new Error('Download failed');
        }

        return response.blob();
    }

    async downloadVersion(fileId, versionId) {
        const response = await fetch(`${API_BASE_URL}/files/${fileId}/versions/${versionId}/download`, {
            headers: {
                'Authorization': `Bearer ${this.getToken()}`,
            },
        });

        if (!response.ok) {
            throw new Error('Download failed');
        }

        return response.blob();
    }

    async listVersions(fileId) {
        return this.request(`/files/${fileId}/versions`);
    }

    async uploadVersion(fileId, file) {
        const formData = new FormData();
        formData.append('new_file', file);
        return this.request(`/files/${fileId}/versions`, {
            method: 'POST',
            body: formData,
        });
    }

    async restoreVersion(fileId, versionId) {
        return this.request(`/files/${fileId}/versions/${versionId}/restore`, {
            method: 'POST',
        });
    }

    async deleteVersion(fileId, versionId) {
        return this.request(`/files/${fileId}/versions/${versionId}`, {
            method: 'DELETE',
        });
    }

    async updateFile(fileId, updates) {
        return this.request(`/files/${fileId}`, {
            method: 'PATCH',
            body: JSON.stringify(updates),
        });
    }

    async trashFile(fileId) {
        return this.request(`/files/${fileId}/trash`, {
            method: 'POST',
        });
    }

    async restoreFile(fileId) {
        return this.request(`/files/${fileId}/restore`, {
            method: 'POST',
        });
    }

    async deleteFilePermanently(fileId) {
        return this.request(`/files/${fileId}`, {
            method: 'DELETE',
        });
    }

    async copyFile(fileId) {
        return this.request(`/files/${fileId}/copy`, {
            method: 'POST',
        });
    }

    // ============ FOLDERS ============
    async createFolder(name, path = []) {
        return this.request('/folders', {
            method: 'POST',
            body: JSON.stringify({ name, path }),
        });
    }

    async deleteFolder(folderId) {
        return this.request(`/folders/${folderId}`, {
            method: 'DELETE',
        });
    }

    // ============ STORAGE ============
    async getStorageInfo() {
        return this.request('/storage');
    }

    async getActivityLog(limit = 50) {
        return this.request(`/storage/activity?limit=${limit}`);
    }

    async emptyTrash() {
        return this.request('/storage/trash', {
            method: 'DELETE',
        });
    }

    // ============ ADMIN ============
    async listUsers() {
        return this.request('/admin/users');
    }

    async getUser(userId) {
        return this.request(`/admin/users/${userId}`);
    }

    async updateUser(userId, updates) {
        return this.request(`/admin/users/${userId}`, {
            method: 'PATCH',
            body: JSON.stringify(updates),
        });
    }

    async deleteUser(userId) {
        return this.request(`/admin/users/${userId}`, {
            method: 'DELETE',
        });
    }

    async getSystemStats() {
        return this.request('/admin/stats');
    }

    async resetUserPassword(userId, newPassword) {
        return this.request(`/admin/users/${userId}/reset-password`, {
            method: 'POST',
            body: JSON.stringify({ new_password: newPassword }),
        });
    }

    // ============ SHARING ============
    async createShareLink(data) {
        return this.request('/share', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    async getMyShareLinks() {
        return this.request('/share/my-links');
    }

    async revokeShareLink(linkId) {
        return this.request(`/share/${linkId}`, {
            method: 'DELETE',
        });
    }

    async accessSharedFile(token, password = null) {
        const body = password ? { password } : {};
        return this.request(`/share/${token}`, {
            method: 'POST',
            body: JSON.stringify(body),
            skipAuth: true,
        });
    }

    getShareDownloadUrl(token) {
        return `${API_BASE_URL}/share/${token}/download`;
    }

    async downloadSharedFile(token, password = null) {
        const headers = {};
        if (password) {
            headers['X-Share-Password'] = password;
        }
        const response = await fetch(`${API_BASE_URL}/share/${token}/download`, { headers });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Download failed' }));
            throw new Error(error.detail || 'Download failed');
        }
        return response.blob();
    }

    // ============ SEARCH ============
    async searchFiles(query, filters = {}) {
        const params = new URLSearchParams();
        params.append('q', query);
        if (filters.type) params.append('type', filters.type);
        if (filters.dateFrom) params.append('date_from', filters.dateFrom);
        if (filters.dateTo) params.append('date_to', filters.dateTo);
        if (filters.starredOnly) params.append('starred_only', 'true');
        if (filters.includeTrash) params.append('include_trashed', 'true');

        return this.request(`/files/search?${params.toString()}`);
    }

    // ============ THUMBNAILS & PREVIEWS ============
    /**
     * Fetch a thumbnail as a blob URL using Authorization header.
     * @param {string} fileId
     * @returns {Promise<string>} Object URL for the thumbnail blob
     */
    async fetchThumbnailBlob(fileId) {
        const response = await fetch(`${API_BASE_URL}/files/${fileId}/thumbnail`, {
            headers: { 'Authorization': `Bearer ${this.getToken()}` },
        });
        if (!response.ok) throw new Error('Thumbnail fetch failed');
        const blob = await response.blob();
        return URL.createObjectURL(blob);
    }

    /**
     * Fetch a file preview as a blob URL using Authorization header.
     * @param {string} fileId
     * @returns {Promise<string>} Object URL for the preview blob
     */
    async fetchPreviewBlob(fileId) {
        const response = await fetch(`${API_BASE_URL}/files/${fileId}/preview`, {
            headers: { 'Authorization': `Bearer ${this.getToken()}` },
        });
        if (!response.ok) throw new Error('Preview fetch failed');
        const blob = await response.blob();
        return URL.createObjectURL(blob);
    }
}

export const api = new ApiService();
export default api;
