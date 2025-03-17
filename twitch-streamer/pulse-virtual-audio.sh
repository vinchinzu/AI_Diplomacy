#!/usr/bin/env bash
set -e

# Start pulseaudio with a null sink so we can capture audio
pulseaudio -D --exit-idle-time=-1 --disable-shm=true --system=false

# The above automatically loads module-null-sink by default in most distros,
# but if you need it explicitly, you can do something like:
#   pactl load-module module-null-sink sink_name=MySink
#   pactl set-default-sink MySink
# For many cases, the default config is enough.

# Just sleep forever to keep the container from stopping if we ran only this script
sleep infinity
