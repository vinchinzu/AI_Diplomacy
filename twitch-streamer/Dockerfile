# chrome-twitch/Dockerfile
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
  xvfb \
  ffmpeg \
  x11vnc \
  wget \
  gnupg \
  ca-certificates \
  fonts-liberation \
  pulseaudio \
  fluxbox \
  dbus dbus-x11 \
  xdotool \
  && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
  && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
  > /etc/apt/sources.list.d/google-chrome.list \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
  google-chrome-stable \
  && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group (chrome:chrome) 
# and add user to audio/video groups if needed
RUN groupadd --system chrome \
  && useradd --system --create-home --gid chrome --groups audio,video chrome

# Environment variables for the virtual display
ENV DISPLAY=:1
ENV SCREEN_GEOMETRY=1920x1080x24

# Copy PulseAudio and entrypoint scripts
RUN mkdir /twitch-streamer/
COPY pulse-virtual-audio.sh /twitch-streamer/pulse-virtual-audio.sh
COPY entrypoint.sh /twitch-streamer/entrypoint.sh
COPY chrome-launcher.sh /twitch-streamer/chrome-launcher.sh
RUN chmod +x /twitch-streamer/pulse-virtual-audio.sh /twitch-streamer/entrypoint.sh /twitch-streamer/chrome-launcher.sh
WORKDIR /twitch-streamer/

ENTRYPOINT ["/twitch-streamer/entrypoint.sh"]
