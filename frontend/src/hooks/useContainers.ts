import { useState, useEffect, useCallback, useRef } from 'react';
import { Container, DesktopType, ContainerStatusUpdate } from '../types';
import { apiService } from '../services/api';
import { wsService } from '../services/websocket';

interface ContainerState {
  containers: Container[];
  desktopTypes: DesktopType[];
  loading: boolean;
  error: string | null;
  starting: string | null; // desktop type currently being started
  stopping: string | null; // desktop type currently being stopped
}

export function useContainers() {
  const [state, setState] = useState<ContainerState>({
    containers: [],
    desktopTypes: [],
    loading: true,
    error: null,
    starting: null,
    stopping: null,
  });

  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Load desktop types
  const loadDesktopTypes = useCallback(async () => {
    try {
      const response = await apiService.getAvailableDesktopTypes();
      if (response.success) {
        setState(prev => ({
          ...prev,
          desktopTypes: response.desktop_types, // Use whatever the backend returns (empty array is valid)
        }));
      } else {
        setState(prev => ({
          ...prev,
          desktopTypes: [], // If API fails, show empty (no fallback)
        }));
      }
    } catch (error) {
      console.error('Failed to load desktop types:', error);
      setState(prev => ({
        ...prev,
        desktopTypes: [], // If error, show empty (no fallback)
      }));
    }
  }, []);

  // Load containers
  const loadContainers = useCallback(async () => {
    try {
      const response = await apiService.listContainers();
      if (response.success) {
        setState(prev => ({
          ...prev,
          containers: response.containers,
          loading: false,
          error: null,
        }));
      } else {
        throw new Error(response.error || 'Failed to load containers');
      }
    } catch (error: any) {
      console.error('Failed to load containers:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: error.message || 'Failed to load containers',
      }));
    }
  }, []);

  // Start container with health polling
  const startContainer = useCallback(async (desktopType: string): Promise<string | null> => {
    setState(prev => ({ ...prev, starting: desktopType, error: null }));

    try {
      const response = await apiService.startContainer(desktopType);
      
      if (!response.success || !response.url) {
        throw new Error(response.error || 'Failed to start container');
      }

      // Reload containers to get updated status
      await loadContainers();

      // Poll for container readiness
      const maxAttempts = 30;
      let attempts = 0;
      let ready = false;

      // Initial wait: Docker containers need time to start their services.
      // This delay allows the container to initialize before we start health checks.
      const CONTAINER_INIT_DELAY_MS = 3000;
      await new Promise(resolve => setTimeout(resolve, CONTAINER_INIT_DELAY_MS));

      while (attempts < maxAttempts && !ready) {
        attempts++;
        try {
          const health = await apiService.checkContainerHealth(desktopType);
          if (health.success && health.ready) {
            ready = true;
            break;
          }
        } catch (e) {
          console.log(`Health check attempt ${attempts} failed`);
        }
        await new Promise(resolve => setTimeout(resolve, 1000));
      }

      setState(prev => ({ ...prev, starting: null }));
      
      // Final small delay to ensure VNC is ready
      if (ready) {
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
      
      return response.url;
    } catch (error: any) {
      console.error('Failed to start container:', error);
      setState(prev => ({
        ...prev,
        starting: null,
        error: error.message || 'Failed to start container',
      }));
      return null;
    }
  }, [loadContainers]);

  // Stop container
  const stopContainer = useCallback(async (desktopType: string): Promise<boolean> => {
    setState(prev => ({ ...prev, stopping: desktopType, error: null }));

    try {
      const response = await apiService.stopContainer(desktopType);
      
      if (!response.success) {
        throw new Error(response.error || 'Failed to stop container');
      }

      await loadContainers();
      setState(prev => ({ ...prev, stopping: null }));
      return true;
    } catch (error: any) {
      console.error('Failed to stop container:', error);
      setState(prev => ({
        ...prev,
        stopping: null,
        error: error.message || 'Failed to stop container',
      }));
      return false;
    }
  }, [loadContainers]);

  // Get container by desktop type
  const getContainerByType = useCallback((desktopType: string): Container | undefined => {
    // Get all containers for this desktop type
    const matchingContainers = state.containers.filter(c => c.desktop_type === desktopType);
    
    if (matchingContainers.length === 0) {
      return undefined;
    }
    
    // Prefer running containers over stopped ones
    const runningContainer = matchingContainers.find(c => c.status === 'running');
    if (runningContainer) {
      return runningContainer;
    }
    
    // If no running container, return the most recently created one
    return matchingContainers.sort((a, b) => {
      const aTime = new Date(a.created_at || 0).getTime();
      const bTime = new Date(b.created_at || 0).getTime();
      return bTime - aTime; // Most recent first
    })[0];
  }, [state.containers]);

  // Handle WebSocket updates
  const handleStatusUpdate = useCallback((update: ContainerStatusUpdate) => {
    setState(prev => ({
      ...prev,
      containers: prev.containers.map(c => 
        c.id === update.container_id 
          ? { ...c, status: update.status as Container['status'], docker_status: update.docker_status }
          : c
      ),
    }));
  }, []);

  // Initialize
  useEffect(() => {
    // Connect to WebSocket
    wsService.connect();
    const unsubscribe = wsService.onStatusUpdate(handleStatusUpdate);

    // Load initial data
    loadDesktopTypes();
    loadContainers();

    // Set up refresh interval (30 seconds)
    refreshIntervalRef.current = setInterval(loadContainers, 30000);

    return () => {
      unsubscribe();
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [loadDesktopTypes, loadContainers, handleStatusUpdate]);

  return {
    ...state,
    loadContainers,
    startContainer,
    stopContainer,
    getContainerByType,
    refresh: loadContainers,
  };
}

export default useContainers;
