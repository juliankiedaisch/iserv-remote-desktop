/**
 * WebRTC service for direct UDP connections to containers
 * 
 * This service handles WebRTC peer connections with TURN/STUN support,
 * allowing direct UDP connections when in local network and TURN relay
 * when accessed from external networks.
 */

interface ICEServer {
  urls: string | string[];
  username?: string;
  credential?: string;
}

interface WebRTCConfig {
  success: boolean;
  enabled: boolean;
  ice_servers: ICEServer[];
  local_network_cidrs?: string[];
}

interface NetworkCheckResult {
  success: boolean;
  is_local_network: boolean;
  client_ip: string;
  local_networks: string[];
}

class WebRTCService {
  private peerConnection: RTCPeerConnection | null = null;
  private dataChannel: RTCDataChannel | null = null;
  private iceServers: RTCIceServer[] = [];
  private isEnabled: boolean = false;
  private isLocalNetwork: boolean = false;
  
  /**
   * Initialize WebRTC service with configuration from backend
   */
  async initialize(): Promise<boolean> {
    try {
      // Check if WebRTC is enabled in frontend config
      const frontendEnabled = (window as any).REACT_APP_WEBRTC_ENABLED === 'true' || 
                             (typeof process !== 'undefined' && process.env?.REACT_APP_WEBRTC_ENABLED === 'true');
      if (!frontendEnabled) {
        console.log('WebRTC disabled in frontend configuration');
        return false;
      }
      
      // Get WebRTC configuration from backend
      const config = await this.fetchWebRTCConfig();
      if (!config.success || !config.enabled) {
        console.log('WebRTC not enabled on backend');
        return false;
      }
      
      // Convert ICE servers to RTCIceServer format
      this.iceServers = config.ice_servers.map(server => ({
        urls: server.urls,
        username: server.username,
        credential: server.credential
      }));
      
      // Check network location
      const networkCheck = await this.checkNetworkLocation();
      if (networkCheck.success) {
        this.isLocalNetwork = networkCheck.is_local_network;
        console.log(`Network location: ${this.isLocalNetwork ? 'Local' : 'External'}`);
      }
      
      this.isEnabled = true;
      return true;
    } catch (error) {
      console.error('Failed to initialize WebRTC:', error);
      return false;
    }
  }
  
  /**
   * Fetch WebRTC configuration from backend
   */
  private async fetchWebRTCConfig(): Promise<WebRTCConfig> {
    const response = await fetch('/api/webrtc/config', {
      credentials: 'include'
    });
    
    if (!response.ok) {
      throw new Error(`Failed to fetch WebRTC config: ${response.statusText}`);
    }
    
    return await response.json();
  }
  
  /**
   * Check if client is in local network
   */
  private async checkNetworkLocation(): Promise<NetworkCheckResult> {
    const response = await fetch('/api/webrtc/network/check', {
      credentials: 'include'
    });
    
    if (!response.ok) {
      throw new Error(`Failed to check network location: ${response.statusText}`);
    }
    
    return await response.json();
  }
  
  /**
   * Create peer connection for WebRTC
   */
  async createPeerConnection(): Promise<RTCPeerConnection> {
    if (this.peerConnection) {
      this.closePeerConnection();
    }
    
    // RTCPeerConnection configuration
    const config: RTCConfiguration = {
      iceServers: this.iceServers,
      iceTransportPolicy: this.isLocalNetwork ? 'all' : 'relay'
    };
    
    this.peerConnection = new RTCPeerConnection(config);
    
    // Log ICE candidates for debugging
    this.peerConnection.onicecandidate = (event) => {
      if (event.candidate) {
        console.log('ICE candidate:', event.candidate);
      } else {
        console.log('ICE gathering complete');
      }
    };
    
    // Log connection state changes
    this.peerConnection.onconnectionstatechange = () => {
      console.log('Connection state:', this.peerConnection?.connectionState);
    };
    
    this.peerConnection.oniceconnectionstatechange = () => {
      console.log('ICE connection state:', this.peerConnection?.iceConnectionState);
    };
    
    return this.peerConnection;
  }
  
  /**
   * Create data channel for communication
   */
  createDataChannel(label: string = 'audio'): RTCDataChannel {
    if (!this.peerConnection) {
      throw new Error('Peer connection not initialized');
    }
    
    this.dataChannel = this.peerConnection.createDataChannel(label, {
      ordered: false, // Allow out-of-order delivery for lower latency
      maxRetransmits: 0 // Don't retransmit for real-time audio
    });
    
    this.dataChannel.onopen = () => {
      console.log('Data channel opened');
    };
    
    this.dataChannel.onclose = () => {
      console.log('Data channel closed');
    };
    
    this.dataChannel.onerror = (error) => {
      console.error('Data channel error:', error);
    };
    
    return this.dataChannel;
  }
  
  /**
   * Close peer connection
   */
  closePeerConnection(): void {
    if (this.dataChannel) {
      this.dataChannel.close();
      this.dataChannel = null;
    }
    
    if (this.peerConnection) {
      this.peerConnection.close();
      this.peerConnection = null;
    }
  }
  
  /**
   * Check if WebRTC is available and enabled
   */
  isAvailable(): boolean {
    return this.isEnabled && 'RTCPeerConnection' in window;
  }
  
  /**
   * Check if client is in local network
   */
  isInLocalNetwork(): boolean {
    return this.isLocalNetwork;
  }
  
  /**
   * Get current peer connection
   */
  getPeerConnection(): RTCPeerConnection | null {
    return this.peerConnection;
  }
  
  /**
   * Get current data channel
   */
  getDataChannel(): RTCDataChannel | null {
    return this.dataChannel;
  }
}

// Export singleton instance
export const webrtcService = new WebRTCService();
export default webrtcService;
