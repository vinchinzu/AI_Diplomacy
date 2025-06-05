#!/bin/bash
# Chrome launcher with restart capability

while true; do
    echo "Starting Chrome browser..."
    
    # Set PulseAudio environment for Chrome
    export PULSE_RUNTIME_PATH=/tmp/pulse
    export PULSE_SERVER=unix:/tmp/pulse/native
    
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
      --window-size=1600,900 --window-position=0,0 \
      --kiosk \
      --autoplay-policy=no-user-gesture-required \
      --disable-features=AudioServiceSandbox,RendererCodeIntegrity,IsolateOrigins \
      --disable-site-isolation-trials \
      --use-fake-ui-for-media-stream \
      --enable-usermedia-screen-capturing \
      --enable-gpu \
      --use-gl=angle \
      --use-angle=gl \
      --disable-gpu-vsync \
      --disable-gpu-sandbox \
      --enable-accelerated-2d-canvas \
      --enable-accelerated-video-decode=false \
      --force-device-scale-factor=1 \
      --disable-web-security \
      --disable-features=VizDisplayCompositor \
      --enable-features=NetworkService \
      --disable-background-networking \
      --disable-background-mode \
      --disable-client-side-phishing-detection \
      --disable-component-update \
      --disable-default-apps \
      --disable-domain-reliability \
      --disable-features=AudioServiceOutOfProcess \
      --disable-hang-monitor \
      --disable-popup-blocking \
      --disable-prompt-on-repost \
      --disable-sync \
      --metrics-recording-only \
      --no-default-browser-check \
      --no-pings \
      --password-store=basic \
      --use-mock-keychain \
      --force-color-profile=srgb \
      --disable-features=Translate \
      --disable-features=BlinkGenPropertyTrees \
      --max_old_space_size=512 \
      --js-flags="--max-old-space-size=512" \
      "http://diplomacy:4173"
    
    echo "Chrome exited with code $?. Restarting in 5 seconds..."
    sleep 5
done