#!/usr/bin/env bash
set -e

# Create runtime directory for PulseAudio
mkdir -p /tmp/pulse
export PULSE_RUNTIME_PATH=/tmp/pulse

# Kill any existing pulseaudio instances
pulseaudio --kill 2>/dev/null || true

# Start pulseaudio with a dummy sink for capturing
pulseaudio --start \
  --exit-idle-time=-1 \
  --disallow-module-loading=false \
  --disallow-exit=true \
  --log-target=stderr \
  --load="module-null-sink sink_name=dummy_sink sink_properties=device.description='Dummy_Output'" \
  --load="module-native-protocol-unix auth-anonymous=1 socket=/tmp/pulse/native"

# Wait for PulseAudio to be ready
for i in {1..10}; do
  if pactl info >/dev/null 2>&1; then
    echo "PulseAudio started successfully"
    break
  fi
  echo "Waiting for PulseAudio to start... ($i/10)"
  sleep 1
done

# Set the dummy sink as default
pactl set-default-sink dummy_sink || true
pactl set-default-source dummy_sink.monitor || true

echo "PulseAudio virtual audio setup complete"
