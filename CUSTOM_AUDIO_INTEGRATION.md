# Custom Audio Integration Summary

## ✅ What was done:

### 1. Modified dockerfile-kasm-core
- **Line 80-82**: Replaced Kasm native audio with custom audio installation
- **Line 134-137**: Added custom audio server files (audio_websocket_server.py, start_audio.sh)
- **Line 192**: Made start_audio.sh executable

### 2. Modified vnc_startup.sh
- **start_audio_out_websocket()**: Now calls our custom `start_audio.sh` instead of Kasm's kasm_audio_out-linux
- **start_audio_out()**: Disabled (our script handles everything)

### 3. Created low-latency audio configuration
**Location**: `/dockerstartup/start_audio.sh` (inside container)

**Low latency optimizations:**
```bash
# Fragment size: 512 (was 2000) - reduces buffering
PULSEAUDIO_FRAGMENT_SIZE=512

# ffmpeg flags:
-probesize 32           # Fast audio stream detection
-fflags nobuffer        # No buffering
-flags low_delay        # Low delay mode
-flush_packets 1        # Immediate packet flush
-muxdelay 0.001         # Minimal mux delay
```

**Expected latency**: ~25-50ms (vs 100-200ms with default settings)

## 🚀 How it starts automatically:

1. Container launches → vnc_startup.sh runs
2. vnc_startup.sh calls `start_audio_out_websocket()` (line 583)
3. Our function calls `/dockerstartup/start_audio.sh`
4. start_audio.sh:
   - Starts PulseAudio
   - Starts Python WebSocket server (port 4901)
   - Starts ffmpeg with low-latency encoding

## 📊 Audio Pipeline:

```
Application Audio Output
        ↓
    PulseAudio
        ↓
    ffmpeg (MP2 encoding, 512 fragment size)
        ↓
    HTTP POST → localhost:8081/audio
        ↓
    Python WebSocket Server (aiohttp)
        ↓
    WebSocket → wss://audio-{proxy}.hub.mdg-hamburg.de/
        ↓
    Frontend jsmpeg Player
        ↓
    Browser Audio Output
```

## 🔧 Build and Deploy:

```bash
cd /root/iserv-remote-desktop/images/core-images
./build-core.sh
```

This builds: `custom-ubuntu-desktop:latest`

Update desktop type in admin panel to use this image.

## 🎛️ Tuning Latency:

### Lower latency (more CPU):
Set environment variable in container:
```bash
PULSEAUDIO_FRAGMENT_SIZE=256
```

### Higher quality (more latency):
```bash
PULSEAUDIO_FRAGMENT_SIZE=1024
```

### Change bitrate:
Edit start_audio.sh, line 38:
```bash
-b:a 96k   # Lower quality, less bandwidth
-b:a 192k  # Higher quality, more bandwidth
```

## ✅ Verification:

After creating a container, check logs:
```bash
docker logs <container-name> | grep -i audio
```

Should see:
```
Starting custom audio streaming...
Starting PulseAudio...
Starting WebSocket server on port 4901...
Starting ffmpeg audio encoding (low latency mode)...
Audio streaming started (WebSocket: XXXX, ffmpeg: YYYY)
Low latency mode: fragment_size=512
```
