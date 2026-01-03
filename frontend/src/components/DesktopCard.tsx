import React from 'react';
import { useTranslation } from 'react-i18next';
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

function formatRelativeTime(dateString: string, t: any): string {
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  
  if (seconds < 60) return t('desktopCard.justNow');
  if (seconds < 3600) return t('desktopCard.minutesAgo', { count: Math.floor(seconds / 60) });
  if (seconds < 86400) return t('desktopCard.hoursAgo', { count: Math.floor(seconds / 3600) });
  return t('desktopCard.daysAgo', { count: Math.floor(seconds / 86400) });
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
  const { t } = useTranslation();
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
      <div className="desktop-icon">
        {desktopType.icon && desktopType.icon.startsWith('/api/') ? (
          <img src={desktopType.icon} alt={desktopType.name} className="icon-image" />
        ) : (
          <span>{desktopType.icon || '🖥️'}</span>
        )}
      </div>
      <div className="desktop-name">{desktopType.name}</div>
      <div className="desktop-description">{desktopType.description || ''}</div>
      
      <div className="desktop-status">
        <span className={`status-indicator ${isRunning ? 'running' : 'stopped'}`}></span>
        <span>
          {isStarting 
            ? t('common.starting')
            : isStopping 
            ? t('common.stopping')
            : isRunning 
            ? t('desktopCard.running')
            : t('desktopCard.stopped')}
        </span>
      </div>
      
      {container?.last_accessed && (
        <div className="desktop-meta">
          {t('desktopCard.lastAccessed')}: {formatRelativeTime(container.last_accessed, t)}
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
              {t('common.open')}
            </button>
            <button 
              className="btn btn-danger" 
              onClick={handleStop}
              disabled={isLoading}
            >
              {isStopping ? t('common.stopping') : t('common.stop')}
            </button>
          </>
        ) : (
          <button 
            className="btn btn-primary" 
            onClick={handleStart}
            disabled={isLoading}
          >
            {isStarting ? t('common.starting') : t('common.start')}
          </button>
        )}
      </div>
    </div>
  );
};

export default DesktopCard;
