import axios, { AxiosInstance, AxiosError } from 'axios';
import {
  SessionResponse,
  ContainerListResponse,
  ContainerStartResponse,
  DesktopTypesResponse,
  ContainerHealthResponse,
  ApiResponse,
  Container
} from '../types';

// Get API base URL from environment or use current origin for absolute URLs
// This fixes 421 Misdirected Request errors on iOS/Safari by ensuring proper SNI
const API_BASE_URL = process.env.REACT_APP_API_URL || window.location.origin;

class ApiService {
  private client: AxiosInstance;
  private sessionId: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      withCredentials: true,
      headers: {
        'Host': window.location.hostname,
      }
    });

    // Load session from localStorage
    this.sessionId = localStorage.getItem('session_id');

    // Add request interceptor to add session header
    this.client.interceptors.request.use((config) => {
      if (this.sessionId) {
        config.headers['X-Session-ID'] = this.sessionId;
      }
      return config;
    });

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Session expired or invalid
          this.clearSession();
          window.location.href = '/api/auth/login';
        }
        return Promise.reject(error);
      }
    );
  }

  setSession(sessionId: string): void {
    this.sessionId = sessionId;
    localStorage.setItem('session_id', sessionId);
  }

  getSessionId(): string | null {
    return this.sessionId;
  }

  clearSession(): void {
    this.sessionId = null;
    localStorage.removeItem('session_id');
  }

  // Generic HTTP methods for flexibility
  async get<T = any>(url: string, config?: any): Promise<{ data: T }> {
    const response = await this.client.get<T>(url, config);
    return { data: response.data };
  }

  async post<T = any>(url: string, data?: any, config?: any): Promise<{ data: T }> {
    const response = await this.client.post<T>(url, data, config);
    return { data: response.data };
  }

  async put<T = any>(url: string, data?: any, config?: any): Promise<{ data: T }> {
    const response = await this.client.put<T>(url, data, config);
    return { data: response.data };
  }

  async delete<T = any>(url: string, config?: any): Promise<{ data: T }> {
    const response = await this.client.delete<T>(url, config);
    return { data: response.data };
  }

  // Authentication endpoints
  async validateSession(): Promise<SessionResponse> {
    const response = await this.client.get<SessionResponse>('/api/auth/session', {
      params: { session_id: this.sessionId }
    });
    return response.data;
  }

  async logout(): Promise<void> {
    try {
      await this.client.post('/api/auth/logout');
    } finally {
      this.clearSession();
    }
  }

  getLoginUrl(): string {
    return `${API_BASE_URL}/api/auth/login`;
  }

  // Container endpoints
  async listContainers(): Promise<ContainerListResponse> {
    const response = await this.client.get<ContainerListResponse>('/api/container/list');
    return response.data;
  }

  async startContainer(desktopType: string): Promise<ContainerStartResponse> {
    const response = await this.client.post<ContainerStartResponse>(
      `/api/container/start?desktop_type=${encodeURIComponent(desktopType)}`
    );
    return response.data;
  }

  async stopContainer(desktopType: string): Promise<ApiResponse<void>> {
    const response = await this.client.post<ApiResponse<void>>('/api/container/stop', {
      desktop_type: desktopType
    });
    return response.data;
  }

  async checkContainerHealth(desktopType: string): Promise<ContainerHealthResponse> {
    const response = await this.client.get<ContainerHealthResponse>(
      `/api/container/health?desktop_type=${encodeURIComponent(desktopType)}`
    );
    return response.data;
  }

  async getAvailableDesktopTypes(): Promise<DesktopTypesResponse> {
    const response = await this.client.get<DesktopTypesResponse>('/api/container/available-types');
    return response.data;
  }

  // Admin endpoints
  async getAllContainers(): Promise<{ success: boolean; containers: Container[]; error?: string }> {
    const response = await this.client.get<{ success: boolean; containers: Container[] }>(
      '/api/admin/containers'
    );
    return response.data;
  }

  async stopAdminContainer(containerId: string): Promise<ApiResponse<void>> {
    const response = await this.client.post<ApiResponse<void>>(
      `/api/admin/container/${containerId}/stop`
    );
    return response.data;
  }

  async removeAdminContainer(containerId: string): Promise<ApiResponse<void>> {
    const response = await this.client.delete<ApiResponse<void>>(
      `/api/admin/container/${containerId}/remove`
    );
    return response.data;
  }

  async stopAllContainers(): Promise<{ success: boolean; stopped_count: number; error?: string }> {
    const response = await this.client.post<{ success: boolean; stopped_count: number }>(
      '/api/admin/containers/stop-all'
    );
    return response.data;
  }

  // Theme endpoints
  async getTheme(): Promise<{ success: boolean; theme: any; error?: string }> {
    const response = await this.client.get<{ success: boolean; theme: any }>('/api/theme');
    return response.data;
  }

  async updateTheme(settings: any, favicon?: string, appName?: string, appIcon?: string): Promise<{ success: boolean; theme: any; error?: string }> {
    const response = await this.client.put<{ success: boolean; theme: any }>(
      '/api/theme',
      { settings, favicon, app_name: appName, app_icon: appIcon }
    );
    return response.data;
  }

  async exportTheme(): Promise<{ success: boolean; theme: any; error?: string }> {
    const response = await this.client.get<{ success: boolean; theme: any }>('/api/theme/export');
    return response.data;
  }

  async importTheme(themeData: any): Promise<{ success: boolean; theme: any; error?: string }> {
    const response = await this.client.post<{ success: boolean; theme: any }>(
      '/api/theme/import',
      themeData
    );
    return response.data;
  }

  async resetTheme(): Promise<{ success: boolean; theme: any; error?: string }> {
    const response = await this.client.post<{ success: boolean; theme: any }>('/api/theme/reset');
    return response.data;
  }

  async uploadFavicon(faviconData: string): Promise<{ success: boolean; favicon: string; error?: string }> {
    const response = await this.client.post<{ success: boolean; favicon: string }>(
      '/api/theme/favicon',
      { favicon: faviconData }
    );
    return response.data;
  }
}

// Export singleton instance
export const apiService = new ApiService();
export default apiService;
