#!/usr/bin/env python3
"""
Custom Audio WebSocket Server for PulseAudio streaming
Receives MP2 audio stream from ffmpeg and broadcasts to WebSocket clients
"""

import asyncio
import logging
import signal
import sys
from aiohttp import web
import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('audio_server')

class AudioWebSocketServer:
    def __init__(self, host='0.0.0.0', ws_port=4901, stream_port=8081):
        self.host = host
        self.ws_port = ws_port
        self.stream_port = stream_port
        self.clients = set()
        self.app = web.Application()
        self.app.router.add_route('GET', '/', self.websocket_handler)
        self.stream_buffer = bytearray()
        self.max_buffer_size = 1024 * 1024  # 1MB buffer
        
    async def websocket_handler(self, request):
        """Handle WebSocket client connections"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.clients.add(ws)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
        
        try:
            # Send buffered audio data to new client
            if self.stream_buffer:
                await ws.send_bytes(bytes(self.stream_buffer))
            
            # Keep connection alive and handle messages
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')
                    break
        except Exception as e:
            logger.error(f"Client error: {e}")
        finally:
            self.clients.discard(ws)
            logger.info(f"Client disconnected. Total clients: {len(self.clients)}")
        
        return ws
    
    async def stream_receiver(self):
        """Receive audio stream from ffmpeg on HTTP port"""
        async def handle_stream(request):
            logger.info("Receiving audio stream from ffmpeg")
            
            try:
                async for chunk in request.content.iter_chunked(8192):
                    if not chunk:
                        break
                    
                    # Add to buffer (keep last N bytes for new clients)
                    self.stream_buffer.extend(chunk)
                    if len(self.stream_buffer) > self.max_buffer_size:
                        self.stream_buffer = self.stream_buffer[-self.max_buffer_size:]
                    
                    # Broadcast to all connected clients
                    if self.clients:
                        dead_clients = set()
                        for client in self.clients:
                            try:
                                await client.send_bytes(chunk)
                            except Exception as e:
                                logger.warning(f"Failed to send to client: {e}")
                                dead_clients.add(client)
                        
                        # Remove dead connections
                        self.clients -= dead_clients
                
                return web.Response(text="Stream ended")
            
            except Exception as e:
                logger.error(f"Stream error: {e}")
                return web.Response(status=500, text=str(e))
        
        stream_app = web.Application()
        stream_app.router.add_route('POST', '/audio', handle_stream)
        stream_app.router.add_route('PUT', '/audio', handle_stream)
        
        runner = web.AppRunner(stream_app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.stream_port)
        await site.start()
        logger.info(f"Stream receiver listening on {self.host}:{self.stream_port}")
    
    async def start(self):
        """Start both WebSocket and stream receiver servers"""
        # Start stream receiver
        await self.stream_receiver()
        
        # Start WebSocket server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.ws_port)
        await site.start()
        logger.info(f"WebSocket server listening on {self.host}:{self.ws_port}")
        
        # Keep running
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            logger.info("Server shutting down")
    
    def stop(self):
        """Stop the server"""
        logger.info("Stopping audio server")
        for client in self.clients:
            asyncio.create_task(client.close())

async def main():
    server = AudioWebSocketServer()
    
    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    
    def signal_handler(sig):
        logger.info(f"Received signal {sig}")
        server.stop()
        loop.stop()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
    
    try:
        await server.start()
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down")
