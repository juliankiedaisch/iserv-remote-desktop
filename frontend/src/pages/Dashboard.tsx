import React, { useCallback, useState } from 'react';
import { Header, DesktopCard, Loading, Alert } from '../components';
import { useAuth } from '../hooks/useAuth';
import { useContainers } from '../hooks/useContainers';
import './Dashboard.css';

export const Dashboard: React.FC = () => {
  const { user, isAdmin, isTeacher, logout, loading: authLoading } = useAuth();
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
  const [showStopModal, setShowStopModal] = useState(false);
  const [containerToStop, setContainerToStop] = useState<string | null>(null);

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

  const handleStop = useCallback((desktopType: string) => {
    setContainerToStop(desktopType);
    setShowStopModal(true);
  }, []);

  const confirmStop = useCallback(async () => {
    if (containerToStop) {
      setStartError(null);
      setShowStopModal(false);
      await stopContainer(containerToStop);
      setContainerToStop(null);
    }
  }, [containerToStop, stopContainer]);

  const cancelStop = useCallback(() => {
    setShowStopModal(false);
    setContainerToStop(null);
  }, []);

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
        title="🖥️ MDG Remote Desktop"
        user={user}
        isAdmin={isAdmin}
        isTeacher={isTeacher}
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

      {/* Stop Confirmation Modal */}
      {showStopModal && containerToStop && (
        <div className="modal-overlay" onClick={cancelStop}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Stop Container</h2>
              <button className="modal-close" onClick={cancelStop}>✕</button>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to stop the <strong>{containerToStop}</strong> container?</p>
              <p className="modal-warning">This will close your active session.</p>
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={cancelStop}>
                Cancel
              </button>
              <button type="button" className="btn btn-danger" onClick={confirmStop}>
                Stop Container
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
