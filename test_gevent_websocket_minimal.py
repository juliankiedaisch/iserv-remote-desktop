#!/usr/bin/env python3
"""
Minimal test to understand how gevent-websocket works
"""
from flask import Flask, request
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
import sys

app = Flask(__name__)

@app.route('/ws')
def websocket_test():
    print("=" * 80, flush=True)
    print("ROUTE CALLED!", flush=True)
    print(f"Upgrade header: {request.headers.get('Upgrade')}", flush=True)
    print(f"wsgi.websocket: {request.environ.get('wsgi.websocket')}", flush=True)
    print("=" * 80, flush=True)
    sys.stdout.flush()
    
    ws = request.environ.get('wsgi.websocket')
    if ws is None:
        return "Not a WebSocket request", 400
    
    # Keep connection open
    print("WebSocket connected! Entering message loop...", flush=True)
    while not ws.closed:
        message = ws.receive()
        if message is not None:
            print(f"Received: {message}", flush=True)
            ws.send(f"Echo: {message}")
        else:
            break
    
    print("WebSocket closed", flush=True)
    return ""  # Never actually returned since we don't leave the loop

if __name__ == '__main__':
    server = pywsgi.WSGIServer(
        ('0.0.0.0', 5021),
        app,
        handler_class=WebSocketHandler
    )
    print("Minimal gevent-websocket test server on port 5021")
    print("Test with: curl -i -N -H 'Connection: Upgrade' -H 'Upgrade: websocket' -H 'Sec-WebSocket-Key: test' -H 'Sec-WebSocket-Version: 13' http://localhost:5021/ws")
    server.serve_forever()
