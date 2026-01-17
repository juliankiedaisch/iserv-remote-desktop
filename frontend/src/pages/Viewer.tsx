import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
// @ts-ignore
import JSMpeg from '@cycjimmy/jsmpeg-player';
import './Viewer.css';

/**
 * Viewer page that combines VNC desktop and audio in single tab
 */
export const Viewer: React.FC = () => {
  const { proxyPath } = useParams<{ proxyPath: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [audioError, setAudioError] = useState<string | null>(null);
  const [menuCollapsed, setMenuCollapsed] = useState(true);
  const audioPlayerRef = useRef<any>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Set page title
  useEffect(() => {
    if (proxyPath) {
      document.title = `Desktop - ${proxyPath}`;
    }
    return () => {
      document.title = 'Remote Desktop';
    };
  }, [proxyPath]);

  // Get VNC URL with parameters for fullscreen scaling
  const containerPrefix = process.env.REACT_APP_CONTAINER_PREFIX || 'test-desktop';
  const vncUrl = `https://${containerPrefix}-${proxyPath}.hub.mdg-hamburg.de/?resize=remote&autoconnect=true&reconnect=true&reconnect_delay=2000`;

  // Audio connection
  useEffect(() => {
    if (!audioEnabled || !proxyPath) return;

    const audioPrefix = containerPrefix === 'desktop' ? 'audio' : 'test-audio';
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const audioUrl = `${protocol}//${audioPrefix}-${proxyPath}.hub.mdg-hamburg.de/`;

    console.log('Connecting to audio:', audioUrl);

    // Create hidden canvas for jsmpeg
    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas');
      canvasRef.current.style.display = 'none';
      document.body.appendChild(canvasRef.current);
    }

    try {
      audioPlayerRef.current = new JSMpeg.Player(audioUrl, {
        canvas: canvasRef.current,
        audio: true,
        video: false,
        autoplay: true,
        loop: false,
        protocols: [],
        // @ts-ignore
        onPlay: () => {
          console.log('Audio connected');
          setAudioError(null);
        },
        // @ts-ignore
        onError: (error: Error) => {
          console.error('Audio error:', error);
          setAudioError('Audio connection failed');
        },
      });
    } catch (error) {
      console.error('Failed to start audio:', error);
      setAudioError('Failed to initialize audio');
    }

    // Cleanup
    return () => {
      if (audioPlayerRef.current) {
        try {
          audioPlayerRef.current.destroy();
        } catch (e) {
          console.error('Error destroying audio player:', e);
        }
        audioPlayerRef.current = null;
      }
      if (canvasRef.current && canvasRef.current.parentNode) {
        canvasRef.current.parentNode.removeChild(canvasRef.current);
        canvasRef.current = null;
      }
    };
  }, [audioEnabled, proxyPath, containerPrefix]);

  return (
    <div className="viewer-container">
      {/* Toggle button - always visible, centered vertically */}
      <button
        onClick={() => setMenuCollapsed(!menuCollapsed)}
        className={`viewer-toggle-button ${!menuCollapsed ? 'expanded' : ''}`}
      >
        {menuCollapsed ? '►' : '◄'}
      </button>

      {/* Left sidebar menu */}
      <div className={`viewer-sidebar ${!menuCollapsed ? 'expanded' : ''}`}>
        {!menuCollapsed && (
          <>
            <button
              onClick={() => setAudioEnabled(!audioEnabled)}
              className={`viewer-button viewer-button-audio ${audioEnabled ? 'enabled' : ''}`}
              title={audioEnabled ? t('audio.disable') : t('audio.enable')}
            >
              {audioEnabled ? '🔊' : '🔇'} Audio
            </button>

            {audioError && (
              <div className="viewer-audio-error">
                {audioError}
              </div>
            )}

            <div className="viewer-proxy-info">
              {proxyPath}
            </div>
          </>
        )}
      </div>

      {/* VNC iframe */}
      <iframe
        src={vncUrl}
        className="viewer-iframe"
        title="Desktop"
      />
    </div>
  );
};

export default Viewer;
