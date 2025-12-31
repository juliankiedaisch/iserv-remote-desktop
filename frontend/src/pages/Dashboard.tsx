import React, { useCallback, useState } from 'react';
import { Header, DesktopCard, Loading, Alert } from '../components';
import { useAuth } from '../hooks/useAuth';
import { useContainers } from '../hooks/useContainers';
import './Dashboard.css';

export const Dashboard: React.FC = () => {
  const { user, isAdmin, logout, loading: authLoading } = useAuth();
  const {
    desktopTypes,
    loading,
    error,
    starting,
    stopping,
    startContainer,
    stopContainer,
    getContainerByType,
  } = useContainers();

  const [startError, setStartError] = useState<string | null>(null);
  const [startingProgress, setStartingProgress] = useState<string | null>(null);

  const handleStart = useCallback(async (desktopType: string) => {
    setStartError(null);
    setStartingProgress('Creating container...');
    
    try {
      const url = await startContainer(desktopType);
      if (url) {
        setStartingProgress('Opening desktop...');
        window.open(url, '_blank');
        setStartingProgress(null);
      } else {
        setStartError('Failed to start container');
        setStartingProgress(null);
      }
    } catch (error: any) {
      setStartError(error.message || 'Failed to start container');
      setStartingProgress(null);
    }
  }, [startContainer]);

  const handleStop = useCallback(async (desktopType: string) => {
    setStartError(null);
    await stopContainer(desktopType);
  }, [stopContainer]);

  const handleOpen = useCallback((url: string) => {
    window.open(url, '_blank');
  }, []);

  if (authLoading) {
    return (
      <div className="container">
        <Loading message="Checking session..." />
      </div>
    );
  }

  return (
    <div className="container">
      <Header
        title="🖥️ Remote Desktop"
        user={user}
        isAdmin={isAdmin}
        onLogout={logout}
      />

      {startError && (
        <Alert 
          type="error" 
          message={startError} 
          onDismiss={() => setStartError(null)} 
        />
      )}

      {error && (
        <Alert 
          type="error" 
          message={error} 
        />
      )}

      {startingProgress && (
        <div className="loading-overlay">
          <div className="loading-content">
            <Loading message={startingProgress} />
          </div>
        </div>
      )}

      {loading ? (
        <Loading message="Loading desktops..." />
      ) : (
        <div className="desktop-grid">
          {desktopTypes.length > 0 ? (
            desktopTypes.map((dt) => (
              <DesktopCard
                key={dt.name}
                desktopType={dt}
                container={getContainerByType(dt.name)}
                onStart={handleStart}
                onStop={handleStop}
                onOpen={handleOpen}
                isStarting={starting === dt.name}
                isStopping={stopping === dt.name}
              />
            ))
          ) : (
            <div className="empty-state">
              <p>No desktop types available for your account</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Dashboard;
