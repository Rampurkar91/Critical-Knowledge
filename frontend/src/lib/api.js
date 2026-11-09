const TOKEN_KEY = 'knowledgebridge_token';

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
};

async function parseResponse(response, raw = false) {
  if (raw) {
    if (!response.ok) throw new ApiError(`Request failed (${response.status})`, response.status, null);
    return response.blob();
  }
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === 'object' && payload?.detail ? payload.detail : `Request failed (${response.status})`;
    throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail), response.status, payload);
  }
  return payload;
}

export async function request(path, { method = 'GET', body, headers = {}, raw = false, signal } = {}) {
  const token = getToken();
  const finalHeaders = { ...headers };
  if (token) finalHeaders.Authorization = `Bearer ${token}`;
  let payload = body;
  if (body !== undefined && !(body instanceof FormData) && typeof body !== 'string') {
    finalHeaders['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const response = await fetch(path, {
    method,
    headers: finalHeaders,
    body: payload,
    signal,
  });
  return parseResponse(response, raw);
}

export const api = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  patch: (path, body, options) => request(path, { ...options, method: 'PATCH', body }),
  upload: (path, formData, options) => request(path, { ...options, method: 'POST', body: formData }),
  raw: (path, options) => request(path, { ...options, raw: true }),
  meta: () => request('/api/meta'),
  login: (email, password) => request('/api/auth/login', { method: 'POST', body: { email, password } }),
  demoLogin: (email) => request('/api/auth/demo-login', { method: 'POST', body: { email } }),
  register: (payload) => request('/api/auth/register', { method: 'POST', body: payload }),
  forgotPassword: (email) => request('/api/auth/forgot-password', { method: 'POST', body: { email } }),
  resetPassword: (payload) => request('/api/auth/reset-password', { method: 'POST', body: payload }),
  me: () => request('/api/auth/me'),
  async download(path, filename) {
    const blob = await this.raw(path);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },
};

export const projectPath = (projectId, suffix = '') =>
  `/api/projects/${encodeURIComponent(projectId)}${suffix}`;
