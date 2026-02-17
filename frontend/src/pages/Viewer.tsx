import React, { useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
// @ts-ignore
import JSMpeg from '@cycjimmy/jsmpeg-player';
import { wsService } from '../services/websocket';
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
  // quality=9 sets highest quality level (0-9 scale, 9 is best)
  // compression=0 disables compression for best quality
  // resize=scale enables client-side scaling for better quality on high-DPI displays
  // anti_aliasing=1 enables edge smoothing for crisp text and graphics
  const containerPrefix = import.meta.env.VITE_CONTAINER_PREFIX || 'desktop';
  
  const vncUrl = `https://${containerPrefix}-${proxyPath}.hub.mdg-hamburg.de/?resize=remote&autoconnect=true&reconnect=true&reconnect_delay=2000&show_control_bar=true&quality=9&compression=0&anti_aliasing=1&view_only=false`;

  // Auto-start audio connection with slight delay to prioritize VNC connection
  useEffect(() => {
    if (!proxyPath) return;

    const audioPrefix = containerPrefix === 'desktop' ? 'audio' : 'test-audio';
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const audioUrl = `${protocol}//${audioPrefix}-${proxyPath}.hub.mdg-hamburg.de/`;

    // Delay audio connection by 1 second to let VNC establish first
    const audioTimeout = setTimeout(() => {
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
    }, 1000); // 1 second delay

    // Cleanup
    return () => {
      clearTimeout(audioTimeout);
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

  // Send periodic heartbeat to keep container alive
  useEffect(() => {
    if (!proxyPath) return;

    // Ensure WebSocket is connected
    wsService.connect();

    // Send initial heartbeat
    wsService.sendContainerHeartbeat(proxyPath);
    console.log('Sent initial container heartbeat');

    // Send heartbeat every 60 seconds to update last_accessed timestamp
    const heartbeatInterval = setInterval(() => {
      wsService.sendContainerHeartbeat(proxyPath);
      console.log('Sent container heartbeat');
    }, 60000); // 60 seconds

    // Cleanup
    return () => {
      clearInterval(heartbeatInterval);
    };
  }, [proxyPath]);

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
