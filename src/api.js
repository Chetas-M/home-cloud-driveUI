/**
 * Home Cloud Drive - API Service
 * Handles all API calls to the backend
 */

// Use relative URL in production (nginx proxies /api to backend)
// In development, this can be overridden
const API_BASE_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:8001/api'
    : '/api';

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

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || 'Request failed');
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

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Login failed' }));
            throw new Error(error.detail || 'Login failed');
        }

        const data = await response.json();
        this.setToken(data.access_token);
        return data;
    }

    async getMe() {
        return this.request('/auth/me');
    }

    logout() {
        this.setToken(null);
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

    /**
     * Upload a single file with real-time progress tracking via XMLHttpRequest.
     * @param {File} file - The file to upload
     * @param {Array} path - Current folder path
     * @param {Function} onProgress - Callback: ({ loaded, total, percent, speed, eta })
     * @returns {{ promise: Promise, abort: Function }}
     */
    uploadFileWithProgress(file, path = [], onProgress) {
        const formData = new FormData();
        formData.append('files', file);

        const params = new URLSearchParams();
        params.append('path', JSON.stringify(path));

        const url = `${API_BASE_URL}/files/upload?${params.toString()}`;
        const token = this.getToken();

        const xhr = new XMLHttpRequest();
        let startTime = Date.now();
        let lastLoaded = 0;
        let lastTime = startTime;
        let speedSamples = [];

        const promise = new Promise((resolve, reject) => {
            xhr.open('POST', url);
            xhr.setRequestHeader('Authorization', `Bearer ${token}`);

            xhr.upload.onprogress = (e) => {
                if (!e.lengthComputable) return;

                const now = Date.now();
                const elapsed = (now - lastTime) / 1000;

                if (elapsed >= 0.3) {
                    const bytesPerSec = (e.loaded - lastLoaded) / elapsed;
                    speedSamples.push(bytesPerSec);
                    if (speedSamples.length > 5) speedSamples.shift();
                    lastLoaded = e.loaded;
                    lastTime = now;
                }

                const avgSpeed = speedSamples.length > 0
                    ? speedSamples.reduce((a, b) => a + b, 0) / speedSamples.length
                    : 0;
                const remaining = e.total - e.loaded;
                const eta = avgSpeed > 0 ? Math.ceil(remaining / avgSpeed) : 0;
                const percent = Math.round((e.loaded / e.total) * 100);

                onProgress?.({
                    loaded: e.loaded,
                    total: e.total,
                    percent,
                    speed: avgSpeed,
                    eta,
                });
            };

            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        resolve(JSON.parse(xhr.responseText));
                    } catch {
                        resolve(xhr.responseText);
                    }
                } else {
                    reject(new Error(`Upload failed: ${xhr.status}`));
                }
            };

            xhr.onerror = () => reject(new Error('Upload network error'));
            xhr.onabort = () => reject(new Error('Upload cancelled'));

            xhr.send(formData);
        });

        return { promise, abort: () => xhr.abort() };
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

        return this.request(`/files/search?${params.toString()}`);
    }

    // ============ THUMBNAILS ============
    getFileThumbnailUrl(fileId) {
        const token = this.getToken();
        return `${API_BASE_URL}/files/${fileId}/thumbnail?token=${encodeURIComponent(token)}`;
    }
}

export const api = new ApiService();
export default api;
