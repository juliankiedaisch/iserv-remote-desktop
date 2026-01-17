#!/bin/bash
# Custom Audio Streaming Startup Script
# Starts PulseAudio, ffmpeg encoder, and WebSocket server

set -e

echo "Starting custom audio streaming..."

# Start PulseAudio if not running
if ! pgrep -x pulseaudio > /dev/null; then
    echo "Starting PulseAudio..."
    HOME=/var/run/pulse pulseaudio --start --exit-idle-time=-1
    sleep 1
fi

# Start WebSocket server in background
echo "Starting WebSocket server on port 4901..."
python3 /app/audio_websocket_server.py &
AUDIO_SERVER_PID=$!
sleep 1

# Start ffmpeg encoding with LOW LATENCY settings
echo "Starting ffmpeg audio encoding (low latency mode)..."
# Low latency settings:
# - fragment_size: 512 (lower = less latency, was 2000)
# - probesize: 32 (faster detection)
# - fflags: nobuffer (no buffering)
# - flush_packets: 1 (immediate flush)
FRAGMENT_SIZE=${PULSEAUDIO_FRAGMENT_SIZE:-512}
ffmpeg \
    -f pulse \
    -fragment_size ${FRAGMENT_SIZE} \
    -probesize 32 \
    -fflags nobuffer \
    -flags low_delay \
    -ar 44100 \
    -i default \
    -f mpegts \
    -correct_ts_overflow 0 \
    -codec:a mp2 \
    -b:a 128k \
    -ac 1 \
    -muxdelay 0.001 \
    -flush_packets 1 \
    http://127.0.0.1:8081/audio &
FFMPEG_PID=$!

echo "Audio streaming started (WebSocket: $AUDIO_SERVER_PID, ffmpeg: $FFMPEG_PID)"
echo "Low latency mode: fragment_size=${FRAGMENT_SIZE}"

# Wait for processes
wait $AUDIO_SERVER_PID $FFMPEG_PID
