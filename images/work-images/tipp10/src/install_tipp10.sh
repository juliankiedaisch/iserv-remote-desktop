#!/usr/bin/env bash
set -ex

# Set Qt to use German locale
export QT_LOCALE_FILTER=de_DE
export LANG=de_DE.UTF-8

# Install tipp10
apt-get update
apt-get -y install tipp10



# Pre-configure tipp10 with German language
mkdir -p $HOME/.config/TIPP10
cat > $HOME/.config/TIPP10/TIPP10.conf << 'EOF'
[general]
language_gui=de
language_layout=de_qwertz_win
language_lesson=de_de_qwertz
check_illustration=true

[main]
language_gui=de
language_layout=de_qwertz_win
language_lesson=de_de_qwertz

[support]
check_border=true
check_helpers=true
check_path=true
check_selection=true
check_selection_start=true
check_status=true
EOF

chown -R 1000:1000 $HOME/.config/TIPP10

# Cleanup for app layer
if [ -z ${SKIP_CLEAN+x} ]; then
  apt-get autoclean
  rm -rf \
    /var/lib/apt/lists/* \
    /var/tmp/* \
    /tmp/*
fi
