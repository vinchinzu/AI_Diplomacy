#!/usr/bin/env bash
# X display can put a lock in, that sometimes will stay in the container. Nuke it as it isn't needed
rm -f /tmp/.X99-lock /tmp/.X1-lock
set -e
# Check if STREAM_KEY is empty
if [ -z "$STREAM_KEY" ]; then
  echo "Error: STREAM_KEY is not set or empty"
  exit 1
fi
# Start PulseAudio (virtual audio) in the background
/twitch-streamer/pulse-virtual-audio.sh &

# Start Xvfb (the in-memory X server) in the background with optimizations
Xvfb $DISPLAY -screen 0 1600x900x24 -ac -nolisten tcp &
echo "Display is ${DISPLAY}"

# Give Xvfb a moment to start
sleep 2

mkdir -p /home/chrome

# Launch Chrome with restart capability
/twitch-streamer/chrome-launcher.sh &

sleep 10 # let the page load or animations start

# Simulate multiple clicks to enable audio and move mouse to corner
echo "Simulating clicks for audio autoplay..."
# Click on the play button area
xdotool mousemove 960 540  # Move to center
sleep 1
xdotool click 1           # Left click
sleep 0.5
# Click multiple times to ensure audio starts
xdotool click 1           # Second click
sleep 0.2
xdotool click 1           # Third click
sleep 0.2
# Try clicking on chat area in case it helps
xdotool mousemove 300 300
xdotool click 1
sleep 0.5
xdotool mousemove 1599 899  # Move to bottom right corner

# Set PulseAudio environment
export PULSE_RUNTIME_PATH=/tmp/pulse
export PULSE_SERVER=unix:/tmp/pulse/native
export PULSE_SINK=dummy_sink

# Start streaming with FFmpeg.
#  - For video: x11grab at 30fps
#  - For audio: pulse from the dummy sink monitor
exec ffmpeg -y \
  -f x11grab -video_size 1600x900 -framerate 15 -thread_queue_size 4096 -i $DISPLAY \
  -f pulse -thread_queue_size 1024 -i dummy_sink.monitor \
  -c:v libx264 -preset ultrafast -tune zerolatency -b:v 1000k -maxrate 1500k -bufsize 300k -profile:v baseline -level 3.0 -crf 32 -threads 1 -x264-params "nal-hrd=cbr:force-cfr=1:keyint=30" \
  -g 40 -keyint_min 20 \
  -pix_fmt yuv420p \
  -c:a aac -b:a 128k \
  -vsync cfr \
  -f flv "rtmp://ingest.global-contribute.live-video.net/app/$STREAM_KEY"

# 'exec' ensures ffmpeg catches any SIGTERM and stops gracefully,
# which will then terminate the container once ffmpeg ends.
