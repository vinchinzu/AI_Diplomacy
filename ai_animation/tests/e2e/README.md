# End-to-End Tests for AI Diplomacy Animation

This directory contains Playwright end-to-end tests for the AI Diplomacy Animation application.

## Test Overview

The tests verify that:

1. **Complete Game Playthrough** - Games play all the way through to completion, show victory messages, and transition to the next game
2. **Victory Message Timing** - The victory popup/message appears when games end and stays visible for an appropriate duration
3. **Next Game Transition** - After a victory message is shown, the application automatically loads and starts the next game
4. **Basic UI Functionality** - Core UI elements load and function correctly
5. **Manual Phase Navigation** - Users can manually advance through game phases

## Test Files

- `game-playthrough.spec.ts` - Main test suite containing all game flow tests
- `test-helpers.ts` - Utility functions for common test operations
- `README.md` - This documentation file

## Running Tests

### Prerequisites

Ensure the development server can start and that there are test games available in debug mode.

### Commands

```bash
# Run all e2e tests
npm run test:e2e

# Run tests with UI (visual test runner)
npm run test:e2e:ui

# Run tests in debug mode
npm run test:e2e:debug

# Run only the basic smoke test
npx playwright test "game loads and basic UI elements are present"

# Run only the complete playthrough test
npx playwright test "complete game playthrough"
```

## Test Configuration

Tests are configured to:
- Start the dev server automatically on `http://localhost:5173`
- Run across Chromium, Firefox, and WebKit browsers
- Have appropriate timeouts for game completion (up to 3 minutes for full playthroughs)
- Wait for the app to fully load before starting tests

## Key Test Scenarios

### 1. Complete Game Playthrough
- Starts automatic game playback
- Monitors for victory messages in the news banner
- Measures how long victory messages are visible
- Detects when the next game starts (via game ID changes or message replacement)

### 2. Manual Advancement
- Stops automatic playback
- Uses the "Next" button to advance through phases manually
- Provides more control over game progression for testing

### 3. Victory Message Detection
- Looks for patterns like "GAME OVER", "WINS", "VICTORIOUS", or trophy emojis (🏆)
- Monitors the `#news-banner-content` element for these messages
- Tracks timing from when victory is detected until the message disappears

## Important DOM Elements

The tests rely on these DOM element IDs:
- `#play-btn` - Play/Pause button
- `#next-btn` - Manual next phase button  
- `#prev-btn` - Manual previous phase button
- `#news-banner-content` - News banner where victory messages appear
- `#phase-display` - Current phase/era display
- `#game-id-display` - Current game ID display
- `canvas` - Three.js rendering canvas

## Test Helpers

The `test-helpers.ts` file provides reusable functions:

- `waitForGameReady()` - Waits for app to load and game to be ready
- `startGamePlayback()` / `stopGamePlayback()` - Control game playback
- `measureVictoryTiming()` - Comprehensive victory detection and timing measurement
- `checkForVictoryMessage()` - Simple victory message detection
- `advanceGameManually()` - Manual game progression
- `getCurrentGameId()` - Get current game ID
- `isGamePlaying()` - Check if game is currently playing

## Expected Game Flow

1. Game loads with initial phase displayed
2. When "Play" is clicked, game begins automatic progression
3. Messages appear and disappear, units animate between phases
4. When the final phase is reached, a victory message appears in the news banner
5. The victory message should remain visible for some time
6. After the victory message, the next game should automatically load
7. The game ID should increment, and the new game should be ready to play

## Troubleshooting

- If tests fail to start, ensure the dev server starts correctly with `npm run dev`
- If games don't auto-load, check that debug mode is enabled in the configuration
- If victory messages aren't detected, verify the game files contain complete games that reach victory conditions
- For timing issues, check the `config.ts` file for debug mode and instant mode settings that affect display duration