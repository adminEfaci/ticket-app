import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  
  // Don't set Content-Type for FormData - let browser set it with boundary
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type'];
  }
  
  return config;
});

// Handle auth errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// API functions
export const api = {
  // Auth
  login: (credentials: { email: string; password: string }) =>
    apiClient.post('/auth/login', credentials),
  
  // Batches
  uploadBatch: (files: FormData) =>
    apiClient.post('/api/upload/files', files, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  
  getBatches: () => apiClient.get('/api/batch'),
  
  processBatch: (batchId: string) =>
    apiClient.post(`/api/batch/${batchId}/process`),
  
  // Clients
  getClients: () => apiClient.get('/api/clients'),
  
  createClient: (data: any) => apiClient.post('/api/clients', data),
  
  // Rates
  getClientRates: (clientId: string) =>
    apiClient.get(`/api/clients/${clientId}/rates`),
  
  createRate: (clientId: string, data: any) =>
    apiClient.post(`/api/clients/${clientId}/rates`, data),
  
  // Export
  validateExport: (data: any) => apiClient.post('/api/export/validate', data),
  
  createExport: (date: string) =>
    apiClient.get(`/api/export/invoices-bundle/${date}`, {
      responseType: 'blob',
    }),
};