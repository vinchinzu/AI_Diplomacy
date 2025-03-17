#!/usr/bin/env bash
# X display can put a lock in, that sometimes will stay in the container. Nuke it as it isn't needed
rm /tmp/.X99-lock
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
#   --app=... to open it as a single-window "app"
#   --no-sandbox / --disable-gpu often needed in Docker
#   --use-fake-device-for-media-stream / etc. if you need to simulate mic/cam
DISPLAY=$DISPLAY google-chrome \
  --disable-gpu \
  --disable-dev-shm-usage \
  --no-first-run \
  --disable-infobars \
  --user-data-dir=/home/chrome/chrome-data \
  --window-size=1920,1080 --window-position=0,0 \
  --kiosk \
  "http://diplomacy:4173" &

sleep 5 # let the page load or animations start

# Start streaming with FFmpeg.
#  - For video:  x11grab from DISPLAY
#  - For audio:  pulse from the "default" device
# Adjust your bitrate, resolution, frame rate, etc. as desired.
exec ffmpeg -y \
  -f x11grab -thread_queue_size 512 -r 30 -s 1920x1080 -i $DISPLAY \
  -f pulse -thread_queue_size 512 -i default \
  -c:v libx264 -preset veryfast -b:v 6000k -maxrate 6000k -bufsize 12000k \
  -pix_fmt yuv420p \
  -c:a aac -b:a 160k \
  -vsync 1 -async 1 \
  -f flv "rtmp://ingest.global-contribute.live-video.net/app/$STREAM_KEY"

# 'exec' ensures ffmpeg catches any SIGTERM and stops gracefully,
# which will then terminate the container once ffmpeg ends.
