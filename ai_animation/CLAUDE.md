# AI Diplomacy Animation Project

## Key Information
- This is a TypeScript project using Three.js for 3D visualization of Diplomacy game states
- The application shows animated conversations between AI players and unit movements
- It's built with Vite for fast development

## Common Commands
- `npm run dev` - Start the development server
- `npm run build` - Build for production
- `npm run lint` - Run TypeScript linting (note: many false negatives due to JS->TS conversion)
- `npm test` - Run unit tests with Vitest
- `npm run test:ui` - Run tests with UI interface
- `npm run test:e2e` - Run end-to-end tests with Playwright
- `npm run test:e2e:ui` - Run e2e tests with visual test runner
- `npm run test:e2e:debug` - Run e2e tests in debug mode

## Project Structure
- `src/` - Source code
  - `main.ts` - Main entry point, handles game loop and UI events
  - `gameState.ts` - Central state management for the application
  - `config.ts` - Global configuration settings
  - `phase.ts` - Phase progression logic, game completion, and victory handling
  - `domElements.ts` - Core DOM element references and utilities
  - `domElements/` - DOM manipulation and UI components
    - `chatWindows.ts` - Message display and news banner management
    - `standingsBoard.ts` - Leaderboard and standings display
    - `relationshipPopup.ts` - Power relationship visualization
  - `map/` - Map rendering and manipulation
  - `units/` - Unit creation and animation
  - `components/` - Reusable UI components
    - `rotatingDisplay.ts` - Dynamic information display
    - `twoPowerConversation.ts` - Two-power conversation overlays
  - `utils/` - Utility functions
    - `powerNames.ts` - Power name display resolution
  - `types/` - TypeScript type definitions
  - `debug/` - Debug tools and menu system
- `tests/` - Test files
  - `e2e/` - End-to-end Playwright tests
  - `integration/` - Integration tests (empty)
  - `fixtures/` - Test fixtures (empty)
- `public/` - Static assets
  - `games/` - Game data files (JSON format)
  - `maps/` - Map data and SVG files
  - `sounds/` - Audio files for speech
  - `fonts/` - Three.js font files

## Game Flow
1. Load game data from JSON files located in `public/games/{gameId}/`
   - `game.json` - Main game data with phases, units, orders, messages
   - `moments.json` - High-interest moments and power model mappings
2. Display initial phase with units and supply centers
3. When Play is clicked:
   - Show messages sequentially, one word at a time
   - When all messages are displayed, animate unit movements
   - When animations complete, show phase summary (if available) via speech
   - Check for high-interest moments (score ≥8.0) and display two-power conversations
   - Advance to next phase and repeat
4. Game completion:
   - When final phase is reached, `displayFinalPhase()` is called
   - Victory message appears in news banner with winner and supply center count
   - `gameState.loadNextGame()` is called to transition to next game
   - Game ID increments and new game loads automatically

## Power Name Display System
The application now includes a dynamic power name display system:

1. **Model Names**: If a `moments.json` file exists with a `power_models` key, the UI will display AI model names instead of generic power names (e.g., "o3" instead of "FRANCE")
2. **Fallback**: If no model names are available, the system falls back to standard power names (AUSTRIA, ENGLAND, etc.)
3. **Utility Function**: `getPowerDisplayName(power)` resolves the appropriate display name for any power
4. **Game-Aware**: The system automatically adapts based on the currently loaded game's data

## Agent State Display
The game now includes agent state data that can be visualized:

1. **Goals and Relationships**: Each power has strategic goals and relationships with other powers
2. **Journal Entries**: Internal thoughts that help explain decision making

### JSON Format Expectations:
- Agent state is stored in the game JSON with the following structure:
  ```json
  {
    "powers": {
      "FRANCE": {
        "goals": ["Secure Belgium", "Form alliance with Italy"],
        "relationships": {
          "GERMANY": "Enemy",
          "ITALY": "Ally",
          "ENGLAND": "Neutral",
          "AUSTRIA": "Neutral",
          "RUSSIA": "Unfriendly",
          "TURKEY": "Neutral"
        },
        "journal": ["Suspicious of England's fleet movements"]
      }
    }
  }
  ```
- Relationship status must be one of: "Enemy", "Unfriendly", "Neutral", "Friendly", "Ally"
- The code handles case variations but the display should normalize to title case

## Known Issues
- Text-to-speech requires an ElevenLabs API key in `.env` file
- Unit animations sometimes don't fire properly after messages
- Debug mode may cause some animations to run too quickly

## Data Format Notes
- The game data's "orders" field can be either an array or an object in the JSON
- The schema automatically converts object-format orders to array format for use in the code
- When debugging order issues, check the format in the original JSON

## Debug Tools
The application includes a debug menu system (enabled when `config.isDebugMode` is true):

### Debug Menu Structure
- Located in `src/debug/` directory
- `DebugMenu` class (`debugMenu.ts`) manages the collapsible menu system
- Individual debug tools are implemented as separate modules and registered with the menu
- Menu does not close when clicking outside (for better UX during debugging)

### Available Debug Tools

#### Province Highlighting (`provinceHighlight.ts`)
- Allows highlighting specific provinces on the map by name
- Input validation with visual feedback for invalid province names
- Supports Enter key and button click to trigger highlighting

#### Next Moment Display (`nextMoment.ts`)
- Shows the next chronological moment that will occur in the game
- Displays current phase, next phase, and next moment information
- Uses phase name parsing to determine chronological order
- Finds the next moment across all phases, not just the immediate next phase
- Shows moment category, phase name, and interest score
- Color-coded by importance (red for high scores ≥9, blue for others)

### Phase Name Format
Phase names follow the format: `[Season][Year][Phase]`
- Seasons: Spring (S) → Fall (F) → Winter (W)
- Phases within each season: Move (M) → Retreat (R) → Adjustment (A)
- Example: `W1901R` = Winter 1901 Retreat phase
- Phase parsing logic is implemented in `types/moments.ts` with Zod schemas

### Adding New Debug Tools
1. Create a new file in `src/debug/` directory
2. Implement an init function that takes the DebugMenu instance
3. Use `debugMenu.addDebugTool(title, htmlContent, beforeSection?)` to add to menu
4. Register the tool in the DebugMenu's `initTools()` method
5. Add any update functions to `updateTools()` method if needed

## End-to-End Testing
The project includes comprehensive Playwright tests to verify game functionality:

### Test Coverage
- **Complete Game Playthrough**: Verifies games play through to victory and transition to next game
- **Victory Message Timing**: Ensures victory popups appear and stay visible for appropriate duration
- **Manual Phase Advancement with Conversation Detection**: Clicks through entire game manually while tracking two-power conversations
- **UI Element Loading**: Smoke tests for essential interface components
- **Manual Navigation**: Tests basic phase advancement controls

### Key DOM Elements
Tests rely on these element IDs:
- `#play-btn` - Play/Pause button
- `#next-btn`, `#prev-btn` - Manual phase navigation
- `#news-banner-content` - Victory messages and news updates
- `#phase-display` - Current phase/era information
- `#game-id-display` - Current game identifier
- `canvas` - Three.js rendering surface
- `.dialogue-overlay` - Two-power conversation dialog overlay

### Victory Detection
Tests monitor for victory patterns in the news banner:
- "GAME OVER.*WINS", "VICTORIOUS", "🏆.*WINS"
- Victory messages should appear when games complete
- Messages should remain visible until next game loads
- Game ID should increment when transitioning to next game

### Two-Power Conversation Detection
Tests can detect and track two-power conversation overlays:
- Conversations appear when moments have interest scores ≥8.0 and involve ≥2 powers
- Tests monitor for `.dialogue-overlay` elements during phase advancement
- Conversations auto-close after timeout or can be manually closed
- Manual advancement test tracks which phases trigger conversations

### Test Helpers
Located in `tests/e2e/test-helpers.ts`:
- `waitForGameReady()` - Ensures app loads completely and enables instant mode
- `measureVictoryTiming()` - Comprehensive victory detection and timing
- `advanceGameManually()` - Manual phase progression with optional two-power conversation tracking
- `isTwoPowerConversationOpen()` - Detects when two-power conversation dialogs are displayed
- `waitForTwoPowerConversationToClose()` - Waits for conversation dialogs to close
- `getCurrentPhaseName()` - Gets current phase name for tracking purposes

### Running Tests
```bash
npm run test:e2e           # Run all e2e tests
npm run test:e2e:ui        # Visual test runner
npm run test:e2e:debug     # Debug mode
```

### Configuration Notes
- Tests automatically enable instant mode (`VITE_INSTANT_MODE=true`) for faster execution
- Tests automatically enable debug mode (`VITE_DEBUG_MODE=true`) for auto-loading games
- Dev server starts automatically on `http://localhost:5173`
- Timeouts set appropriately (1-2 minutes for full playthroughs with instant mode)
- Cross-browser testing on Chromium, Firefox, and WebKit

## Game State Management
Central state is managed in `gameState.ts` with key properties:
- `gameData` - Current game's JSON data
- `momentsData` - High-interest moments and metadata
- `phaseIndex` - Current phase being displayed
- `currentPower` - Player's assigned power
- `isPlaying` - Automatic playback state
- `messagesPlaying` - Message animation state
- `unitAnimations` - Active unit movement animations

## Game Completion Flow
1. Final phase detection in `phase.ts:_setPhase()`
2. `displayFinalPhase()` calculates winner by supply center count
3. Victory message added to news banner via `addToNewsBanner()`
4. `gameState.loadNextGame()` increments game ID
5. New game file loaded from `public/games/{newGameId}/game.json`
6. Application resets to initial state with new game

## Code Style Preferences
- Use descriptive function and variable names
- Add JSDoc comments for all exported functions
- Log important state transitions to console
- Use TypeScript types for all parameters and return values