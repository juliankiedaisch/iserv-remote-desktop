import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Container, DesktopType } from '../types';
import { apiService } from '../services/api';
import './DesktopCard.css';

interface DesktopCardProps {
  desktopType: DesktopType;
  container?: Container;
  onStart: (desktopType: string) => void;
  onStop: (desktopType: string) => void;
  onOpen: (proxyPath: string) => void;
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
  
  const [showResetModal, setShowResetModal] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);

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
    if (container?.proxy_path) {
      onOpen(container.proxy_path);
    }
  };

  const handleResetConfig = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowResetModal(true);
    setResetError(null);
  };

  const confirmResetConfig = async () => {
    if (!desktopType.docker_image) {
      setResetError('Desktop image not found');
      return;
    }

    setIsResetting(true);
    setResetError(null);

    try {
      const result = await apiService.resetConfig(desktopType.docker_image);
      if (result.success) {
        setShowResetModal(false);
        // Show success message (you may want to add a toast notification here)
        alert(t('desktopCard.configResetSuccess'));
      } else {
        setResetError(result.error || t('desktopCard.configResetFailed'));
      }
    } catch (error: any) {
      setResetError(error.message || t('desktopCard.configResetFailed'));
    } finally {
      setIsResetting(false);
    }
  };

  const cancelResetConfig = () => {
    setShowResetModal(false);
    setResetError(null);
  };

  return (
    <>
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
            <>
              <button 
                className="btn btn-primary" 
                onClick={handleStart}
                disabled={isLoading}
              >
                {isStarting ? t('common.starting') : t('common.start')}
              </button>
              <button 
                className="btn btn-secondary" 
                onClick={handleResetConfig}
                disabled={isLoading}
                title={t('desktopCard.resetConfig')}
              >
                {t('desktopCard.resetConfig')}
              </button>
            </>
          )}
        </div>
      </div>

      {showResetModal && (
        <div className="modal-overlay" onClick={cancelResetConfig}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>{t('desktopCard.resetConfigTitle')}</h3>
            <p>{t('desktopCard.resetConfigMessage')}</p>
            <p className="warning">{t('desktopCard.resetConfigWarning')}</p>
            {resetError && (
              <div className="alert alert-danger">{resetError}</div>
            )}
            <div className="modal-actions">
              <button 
                className="btn btn-secondary" 
                onClick={cancelResetConfig}
                disabled={isResetting}
              >
                {t('common.cancel')}
              </button>
              <button 
                className="btn btn-danger" 
                onClick={confirmResetConfig}
                disabled={isResetting}
              >
                {isResetting ? t('common.processing') : t('common.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default DesktopCard;
