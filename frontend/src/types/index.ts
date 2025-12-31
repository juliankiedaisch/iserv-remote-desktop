// User and session types
export interface User {
  id: string;
  username: string;
  email: string;
  role: 'user' | 'admin' | 'teacher';
  groups: Group[];
  avatar_url?: string;
}

export interface Group {
  id: string;
  name: string;
}

export interface Session {
  id: string;
  expires_at: string;
}

export interface AuthState {
  session: Session | null;
  user: User | null;
  authenticated: boolean;
  loading: boolean;
  error: string | null;
}

// Desktop types
export interface DesktopType {
  id?: string;
  name: string;
  docker_image: string;
  description?: string;
  icon?: string;
}

export interface Container {
  id: string;
  user_id: string;
  session_id: string;
  container_id?: string;
  container_name: string;
  image_name: string;
  desktop_type: string;
  status: 'creating' | 'running' | 'stopped' | 'error';
  host_port?: number;
  container_port: number;
  proxy_path?: string;
  created_at: string;
  started_at?: string;
  stopped_at?: string;
  last_accessed?: string;
  url?: string;
  docker_status?: string;
  username?: string;
}

// API response types
export interface ApiResponse<T> {
  success: boolean;
  error?: string;
  message?: string;
  data?: T;
}

export interface SessionResponse {
  session: Session;
  user: User;
  authenticated: boolean;
}

export interface ContainerListResponse {
  success: boolean;
  containers: Container[];
  error?: string;
}

export interface ContainerStartResponse {
  success: boolean;
  message: string;
  container: Container;
  url: string;
  error?: string;
}

export interface DesktopTypesResponse {
  success: boolean;
  desktop_types: DesktopType[];
  error?: string;
}

export interface ContainerHealthResponse {
  success: boolean;
  ready: boolean;
  status?: string;
  container_id?: string;
  error?: string;
}

// WebSocket event types
export interface ContainerStatusUpdate {
  container_id: string;
  status: string;
  docker_status?: string;
  timestamp: string;
}

export interface WebSocketMessage {
  type: 'container_status' | 'container_created' | 'container_stopped' | 'error';
  data: any;
  timestamp: string;
}
