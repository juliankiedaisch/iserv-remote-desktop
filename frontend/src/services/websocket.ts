import { io, Socket } from 'socket.io-client';
import { ContainerStatusUpdate, WebSocketMessage } from '../types';
import { apiService } from './api';

type StatusUpdateCallback = (update: ContainerStatusUpdate) => void;
type MessageCallback = (message: WebSocketMessage) => void;
type ConnectionCallback = (connected: boolean) => void;
type ImagePullCallback = (event: string, data: any) => void;

class WebSocketService {
  private socket: Socket | null = null;
  private statusUpdateCallbacks: Set<StatusUpdateCallback> = new Set();
  private messageCallbacks: Set<MessageCallback> = new Set();
  private connectionCallbacks: Set<ConnectionCallback> = new Set();
  private imagePullCallbacks: Set<ImagePullCallback> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  connect(): void {
    if (this.socket?.connected) {
      return;
    }

    const sessionId = apiService.getSessionId();
    if (!sessionId) {
      console.warn('WebSocket: No session ID available, connection aborted. Please ensure you are logged in.');
      return;
    }

    // Get WebSocket URL from environment or default to current origin
    const wsUrl = process.env.REACT_APP_WS_URL || window.location.origin;

    this.socket = io(wsUrl, {
      path: '/ws',
      auth: {
        session_id: sessionId
      },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.reconnectDelay,
      reconnectionDelayMax: 5000,
    });

    this.setupEventHandlers();
  }

  private setupEventHandlers(): void {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.notifyConnectionChange(true);
    });

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      this.notifyConnectionChange(false);
    });

    this.socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      this.reconnectAttempts++;
      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.error('WebSocket: Max reconnection attempts reached');
      }
    });

    // Container status updates
    this.socket.on('container_status', (data: ContainerStatusUpdate) => {
      this.statusUpdateCallbacks.forEach(callback => callback(data));
    });

    // Generic message handler
    this.socket.on('message', (message: WebSocketMessage) => {
      this.messageCallbacks.forEach(callback => callback(message));
    });

    // Container created event
    this.socket.on('container_created', (data: any) => {
      const message: WebSocketMessage = {
        type: 'container_created',
        data,
        timestamp: new Date().toISOString()
      };
      this.messageCallbacks.forEach(callback => callback(message));
    });

    // Container stopped event
    this.socket.on('container_stopped', (data: any) => {
      const message: WebSocketMessage = {
        type: 'container_stopped',
        data,
        timestamp: new Date().toISOString()
      };
      this.messageCallbacks.forEach(callback => callback(message));
    });

    // Error event
    this.socket.on('error', (data: any) => {
      const message: WebSocketMessage = {
        type: 'error',
        data,
        timestamp: new Date().toISOString()
      };
      this.messageCallbacks.forEach(callback => callback(message));
    });

    // Image pull events
    this.socket.on('image_pull_started', (data: any) => {
      this.imagePullCallbacks.forEach(callback => callback('started', data));
    });

    this.socket.on('image_pull_progress', (data: any) => {
      this.imagePullCallbacks.forEach(callback => callback('progress', data));
    });

    this.socket.on('image_pull_completed', (data: any) => {
      this.imagePullCallbacks.forEach(callback => callback('completed', data));
    });

    this.socket.on('image_pull_error', (data: any) => {
      this.imagePullCallbacks.forEach(callback => callback('error', data));
    });
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.notifyConnectionChange(false);
  }

  onStatusUpdate(callback: StatusUpdateCallback): () => void {
    this.statusUpdateCallbacks.add(callback);
    return () => this.statusUpdateCallbacks.delete(callback);
  }

  onMessage(callback: MessageCallback): () => void {
    this.messageCallbacks.add(callback);
    return () => this.messageCallbacks.delete(callback);
  }

  onConnectionChange(callback: ConnectionCallback): () => void {
    this.connectionCallbacks.add(callback);
    return () => this.connectionCallbacks.delete(callback);
  }

  onImagePull(callback: ImagePullCallback): () => void {
    this.imagePullCallbacks.add(callback);
    return () => this.imagePullCallbacks.delete(callback);
  }

  private notifyConnectionChange(connected: boolean): void {
    this.connectionCallbacks.forEach(callback => callback(connected));
  }

  isConnected(): boolean {
    return this.socket?.connected ?? false;
  }

  // Subscribe to a specific container's updates
  subscribeToContainer(containerId: string): void {
    if (this.socket?.connected) {
      this.socket.emit('subscribe', { container_id: containerId });
    }
  }

  // Unsubscribe from a container's updates
  unsubscribeFromContainer(containerId: string): void {
    if (this.socket?.connected) {
      this.socket.emit('unsubscribe', { container_id: containerId });
    }
  }
}

// Export singleton instance
export const wsService = new WebSocketService();
export default wsService;
