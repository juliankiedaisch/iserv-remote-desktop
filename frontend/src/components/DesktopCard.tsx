import React from 'react';
import { Container, DesktopType } from '../types';
import './DesktopCard.css';

interface DesktopCardProps {
  desktopType: DesktopType;
  container?: Container;
  onStart: (desktopType: string) => void;
  onStop: (desktopType: string) => void;
  onOpen: (url: string) => void;
  isStarting: boolean;
  isStopping: boolean;
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return Math.floor(seconds / 60) + ' minutes ago';
  if (seconds < 86400) return Math.floor(seconds / 3600) + ' hours ago';
  return Math.floor(seconds / 86400) + ' days ago';
}

export const DesktopCard: React.FC<DesktopCardProps> = ({
  desktopType,
  container,
  onStart,
  onStop,
  onOpen,
  isStarting,
  isStopping,
}) => {
  const isRunning = container?.status === 'running';
  const isLoading = isStarting || isStopping;

  const handleStart = () => {
    if (!isLoading) {
      onStart(desktopType.name);
    }
  };

  const handleStop = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isLoading) {
      onStop(desktopType.name);
    }
  };

  const handleOpen = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (container?.url) {
      onOpen(container.url);
    }
  };

  return (
    <div className={`desktop-card ${isRunning ? 'running' : 'stopped'}`}>
      <div className="desktop-icon">{desktopType.icon || '🖥️'}</div>
      <div className="desktop-name">{desktopType.name}</div>
      <div className="desktop-description">{desktopType.description || ''}</div>
      
      <div className="desktop-status">
        <span className={`status-indicator ${isRunning ? 'running' : 'stopped'}`}></span>
        <span>{isStarting ? 'Starting...' : isStopping ? 'Stopping...' : isRunning ? 'Running' : 'Stopped'}</span>
      </div>
      
      {container?.last_accessed && (
        <div className="desktop-meta">
          Last accessed: {formatRelativeTime(container.last_accessed)}
        </div>
      )}
      
      <div className="desktop-actions">
        {isRunning ? (
          <>
            <button 
              className="btn btn-primary" 
              onClick={handleOpen}
              disabled={isLoading}
            >
              Open
            </button>
            <button 
              className="btn btn-danger" 
              onClick={handleStop}
              disabled={isLoading}
            >
              {isStopping ? 'Stopping...' : 'Stop'}
            </button>
          </>
        ) : (
          <button 
            className="btn btn-primary" 
            onClick={handleStart}
            disabled={isLoading}
          >
            {isStarting ? 'Starting...' : 'Start'}
          </button>
        )}
      </div>
    </div>
  );
};

export default DesktopCard;
