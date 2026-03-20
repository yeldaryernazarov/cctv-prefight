import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001';

const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor to handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      // Redirect to login if not already there
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const auth = {
  login: (username, password) =>
    axios.post(`${API_URL}/api/auth/login`, new URLSearchParams({ username, password })),
  me: () => api.get('/auth/me'),
};

export const alerts = {
  getAll: (params) => api.get('/alerts', { params }),
  getById: (id) => api.get(`/alerts/${id}`),
  createDecision: (id, data) => api.post(`/alerts/${id}/decision`, data),
};

export const cameras = {
  getAll: () => api.get('/cameras'),
  getStats: (id, hours = 24) => api.get(`/cameras/${id}/stats`, { params: { hours } }),
};

export const dashboard = {
  getStats: () => api.get('/dashboard/stats'),
};

export const config = {
  get: () => api.get('/config'),
  update: (key, value) => api.put(`/config/${key}`, { value }),
};

export default api;
