#!/bin/bash

# Script to show conversation between two powers in a specific phase
# Usage: ./show_conversation.sh <power1> <power2> <phase> [game_file]

if [ $# -lt 3 ]; then
  echo "Usage: $0 <power1> <power2> <phase> [game_file]"
  echo "Example: $0 FRANCE ENGLAND S1901M"
  echo "Example: $0 FRANCE ENGLAND S1901M public/games/0/game.json"
  exit 1
fi

POWER1="$1"
POWER2="$2"
PHASE="$3"
GAME_FILE="${4:-public/default_game_formatted.json}"

# Check if game file exists
if [ ! -f "$GAME_FILE" ]; then
  echo "Error: Game file '$GAME_FILE' not found"
  exit 1
fi

# Check if jq is installed
if ! command -v jq &>/dev/null; then
  echo "Error: jq is required but not installed"
  exit 1
fi

echo "=== Conversation between $POWER1 and $POWER2 in phase $PHASE ==="
echo "Game file: $GAME_FILE"
echo ""

# Extract messages between the two powers in the specified phase, sorted by time
jq -r --arg power1 "$POWER1" --arg power2 "$POWER2" --arg phase "$PHASE" '
  .phases[] |
  select(.name == $phase) |
  .messages[] |
  select(
    (.sender == $power1 and .recipient == $power2) or
    (.sender == $power2 and .recipient == $power1)
  ) |
  . as $msg |
  "\($msg.time_sent) \($msg.sender) -> \($msg.recipient): \($msg.message)\n"
' "$GAME_FILE" | sort -n #| sed 's/^[0-9]* //'

# Check if any messages were found
if [ ${PIPESTATUS[0]} -eq 0 ]; then
  message_count=$(jq --arg power1 "$POWER1" --arg power2 "$POWER2" --arg phase "$PHASE" '
      .phases[] |
      select(.name == $phase) |
      .messages[] |
      select(
        (.sender == $power1 and .recipient == $power2) or
        (.sender == $power2 and .recipient == $power1)
      )
    ' "$GAME_FILE" | jq -s 'length')

  echo ""
  echo "Found $message_count messages in phase $PHASE between $POWER1 and $POWER2"
else
  echo "No messages found between $POWER1 and $POWER2 in phase $PHASE"
fi

