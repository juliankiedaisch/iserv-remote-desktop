import { useState, useEffect, useCallback, useRef } from 'react';
import { Container, DesktopType, ContainerStatusUpdate, ContainerCreatedEvent, ContainerErrorEvent } from '../types';
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
  // Start container with health polling
  const startContainer = useCallback(async (desktopType: string): Promise<string | null> => {
    setState(prev => ({ ...prev, starting: desktopType, error: null }));

    try {
      const response = await apiService.startContainer(desktopType);
      
      if (!response.success) {
        throw new Error(response.error || 'Failed to start container');
      }

      // Check if response is queued (HTTP 202)
      if (response.status === 'queued') {
        console.log('Container creation queued, waiting for WebSocket notification...');
        
        // Wait for container_created or container_error event via WebSocket
        const containerCreated = await new Promise<{ container_id: string; container_name: string }>((resolve, reject) => {
          const timeout = setTimeout(() => {
            unsubscribe();
            reject(new Error('Timeout waiting for container creation'));
          }, 120000); // 2 minute timeout

          const unsubscribe = wsService.onMessage((message) => {
            if (message.type === 'container_created' && message.data.desktop_type === desktopType) {
              clearTimeout(timeout);
              unsubscribe();
              resolve(message.data);
            } else if (message.type === 'container_error' && message.data.desktop_type === desktopType) {
              clearTimeout(timeout);
              unsubscribe();
              reject(new Error(message.data.error || 'Container creation failed'));
            }
          });
        });

        // Small delay to ensure container status is fully updated in backend
        await new Promise(resolve => setTimeout(resolve, 500));

        // Reload containers to get updated status
        await loadContainers();

        // Get the container URL
        const container = getContainerByType(desktopType);
        if (!container || !container.proxy_path) {
          throw new Error('Container created but proxy path not available');
        }

        // Poll for container readiness
        const maxAttempts = 30;
        let attempts = 0;
        let ready = false;

        // Initial wait: Docker containers need time to start their services.
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

        // Construct the URL from the proxy path
        const containerPrefix = process.env.REACT_APP_CONTAINER_PREFIX || 'desktop';
        const url = `https://${containerPrefix}-${container.proxy_path}.hub.mdg-hamburg.de`;
        return url;
      }

      // Handle immediate response (legacy mode)
      if (!response.url) {
        throw new Error(response.error || 'Failed to start container');
      }

      // Small delay to ensure container status is fully updated in backend
      await new Promise(resolve => setTimeout(resolve, 500));

      // Reload containers to get updated status
      await loadContainers();

      // Poll for container readiness
      const maxAttempts = 30;
      let attempts = 0;
      let ready = false;

      // Initial wait: Docker containers need time to start their services.
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
  }, [loadContainers, getContainerByType]);

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
