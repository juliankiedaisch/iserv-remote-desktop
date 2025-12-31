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
          desktopTypes: response.desktop_types.length > 0 
            ? response.desktop_types 
            : getDefaultDesktopTypes(),
        }));
      } else {
        setState(prev => ({
          ...prev,
          desktopTypes: getDefaultDesktopTypes(),
        }));
      }
    } catch (error) {
      console.error('Failed to load desktop types:', error);
      setState(prev => ({
        ...prev,
        desktopTypes: getDefaultDesktopTypes(),
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

      // Initial wait
      await new Promise(resolve => setTimeout(resolve, 3000));

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
    return state.containers.find(c => c.desktop_type === desktopType);
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

// Default desktop types for backward compatibility
function getDefaultDesktopTypes(): DesktopType[] {
  return [
    {
      name: 'ubuntu-vscode',
      docker_image: 'kasmweb/vs-code:1.18.0',
      description: 'Full Ubuntu desktop with Visual Studio Code pre-installed',
      icon: '💻'
    },
    {
      name: 'ubuntu-desktop',
      docker_image: 'kasmweb/ubuntu-noble-desktop:1.18.0',
      description: 'Standard Ubuntu desktop environment',
      icon: '🖥️'
    }
  ];
}

export default useContainers;
