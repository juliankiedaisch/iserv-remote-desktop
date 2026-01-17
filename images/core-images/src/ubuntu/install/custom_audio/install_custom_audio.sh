#!/usr/bin/env bash
### Install custom audio streaming solution
set -ex

echo "Installing custom audio streaming dependencies..."

# Install PulseAudio and ffmpeg
apt-get update
apt-get install -y \
    curl \
    pulseaudio \
    pulseaudio-utils \
    ffmpeg \
    python3-pip \
    python3-aiohttp

# Clean up
apt-get clean
rm -rf /var/lib/apt/lists/*

# Configure PulseAudio
mkdir -p /var/run/pulse
sed -i 's/^; exit-idle-time =.*/exit-idle-time = -1/' /etc/pulse/daemon.conf || true

echo "Custom audio streaming installed successfully"
