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

# Start Xvfb (the in-memory X server) in the background
Xvfb $DISPLAY -screen 0 1920x1080x24 &
echo "Display is ${DISPLAY}"

# Give Xvfb a moment to start
sleep 2

mkdir -p /home/chrome

# Launch Chrome in the background, pointing at your site.
#   --disable-background-timer-throttling & related flags to prevent fps throttling in headless/Xvfb
DISPLAY=$DISPLAY google-chrome \
  --remote-debugging-port=9222 \
  --no-sandbox \
  --disable-setuid-sandbox \
  --disable-dev-shm-usage \
  --no-first-run \
  --disable-background-timer-throttling \
  --disable-renderer-backgrounding \
  --disable-backgrounding-occluded-windows \
  --disable-features=TranslateUI \
  --disable-ipc-flooding-protection \
  --disable-frame-rate-limit \
  --enable-precise-memory-info \
  --max-gum-fps=30 \
  --user-data-dir=/home/chrome/chrome-data \
  --window-size=1920,1080 --window-position=0,0 \
  --kiosk \
  --autoplay-policy=no-user-gesture-required \
  --enable-gpu \
  --use-gl=swiftshader \
  --disable-gpu-vsync \
  --force-device-scale-factor=1 \
  "http://diplomacy:4173" &

sleep 5 # let the page load or animations start

# Set PulseAudio environment
export PULSE_RUNTIME_PATH=/tmp/pulse
export PULSE_SERVER=unix:/tmp/pulse/native

# Start streaming with FFmpeg.
#  - For video: x11grab at 30fps
#  - For audio: pulse from the dummy sink monitor
exec ffmpeg -y \
  -f x11grab -video_size 1920x1080 -framerate 30 -thread_queue_size 1024 -i $DISPLAY \
  -f pulse -thread_queue_size 1024 -i dummy_sink.monitor \
  -c:v libx264 -preset fast -tune animation -b:v 4500k -maxrate 4500k -bufsize 9000k \
  -g 60 -keyint_min 60 \
  -pix_fmt yuv420p \
  -c:a aac -b:a 128k \
  -vsync cfr \
  -f flv "rtmp://ingest.global-contribute.live-video.net/app/$STREAM_KEY"

# 'exec' ensures ffmpeg catches any SIGTERM and stops gracefully,
# which will then terminate the container once ffmpeg ends.
