import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
// @ts-ignore
import JSMpeg from '@cycjimmy/jsmpeg-player';

/**
 * Viewer page that combines VNC desktop and audio in single tab
 */
export const Viewer: React.FC = () => {
  const { proxyPath } = useParams<{ proxyPath: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  
  const [audioEnabled, setAudioEnabled] = useState(false);
  const [audioError, setAudioError] = useState<string | null>(null);
  const audioPlayerRef = useRef<any>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Get VNC URL
  const containerPrefix = process.env.REACT_APP_CONTAINER_PREFIX || 'test-desktop';
  const vncUrl = `https://${containerPrefix}-${proxyPath}.hub.mdg-hamburg.de/`;

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
    <div style={{ 
      position: 'fixed', 
      top: 0, 
      left: 0, 
      right: 0, 
      bottom: 0, 
      display: 'flex', 
      flexDirection: 'column',
      backgroundColor: '#1a1a1a'
    }}>
      {/* Control bar */}
      <div style={{ 
        height: '50px', 
        backgroundColor: '#2d2d2d', 
        display: 'flex', 
        alignItems: 'center', 
        padding: '0 20px',
        gap: '15px',
        borderBottom: '1px solid #444'
      }}>
        <button
          onClick={() => navigate('/dashboard')}
          style={{
            padding: '8px 16px',
            backgroundColor: '#444',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          ← {t('common.back') || 'Back'}
        </button>
        
        <button
          onClick={() => setAudioEnabled(!audioEnabled)}
          style={{
            padding: '8px 16px',
            backgroundColor: audioEnabled ? '#28a745' : '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '16px'
          }}
          title={audioEnabled ? t('audio.disable') : t('audio.enable')}
        >
          {audioEnabled ? '🔊' : '🔇'} Audio
        </button>

        {audioError && (
          <span style={{ color: '#dc3545', fontSize: '14px' }}>
            {audioError}
          </span>
        )}

        <span style={{ color: '#999', fontSize: '14px', marginLeft: 'auto' }}>
          {proxyPath}
        </span>
      </div>

      {/* VNC iframe */}
      <iframe
        src={vncUrl}
        style={{
          flex: 1,
          border: 'none',
          width: '100%',
          height: 'calc(100vh - 50px)'
        }}
        title="Desktop"
      />
    </div>
  );
};

export default Viewer;
