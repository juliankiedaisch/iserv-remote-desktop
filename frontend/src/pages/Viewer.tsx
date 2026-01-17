import React, { useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
// @ts-ignore
import JSMpeg from '@cycjimmy/jsmpeg-player';
import './Viewer.css';

/**
 * Viewer page that embeds VNC desktop with native KasmVNC controls and auto-starts audio
 */
export const Viewer: React.FC = () => {
  const { proxyPath } = useParams<{ proxyPath: string }>();
  
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
  // Authentication is automatically handled by Apache (Basic Auth header injection)
  // IMPORTANT: show_control_bar=true parameter forces KasmVNC to display the control bar even when embedded in iframe
  // This overrides the default behavior where KasmVNC hides controls when (window.self !== window.top)
  const containerPrefix = process.env.REACT_APP_CONTAINER_PREFIX || 'test-desktop';
  const vncUrl = `https://${containerPrefix}-${proxyPath}.hub.mdg-hamburg.de/?resize=remote&autoconnect=true&reconnect=true&reconnect_delay=2000&show_control_bar=true`;

  // Auto-start audio connection
  useEffect(() => {
    if (!proxyPath) return;

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
        },
        // @ts-ignore
        onError: (error: Error) => {
          console.error('Audio error:', error);
        },
      });
    } catch (error) {
      console.error('Failed to start audio:', error);
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
  }, [proxyPath, containerPrefix]);

  return (
    <div className="viewer-container">
      {/* VNC iframe with native KasmVNC controls */}
      <iframe
        src={vncUrl}
        className="viewer-iframe"
        title="Desktop"
      />
    </div>
  );
};

export default Viewer;
