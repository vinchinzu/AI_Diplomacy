# AI Diplomacy Animation Project

## Key Information
- This is a TypeScript project using Three.js for 3D visualization of Diplomacy game states
- The application shows animated conversations between AI players and unit movements
- It's built with Vite for fast development

## Common Commands
- `npm run dev` - Start the development server
- `npm run build` - Build for production
- `npm run lint` - Run TypeScript linting
- `npm test` - Run unit tests with Vitest
- `npm run test:ui` - Run tests with UI interface

## Project Structure
- `src/` - Source code
  - `main.ts` - Main entry point, handles game loop and UI events
  - `gameState.ts` - Central state management for the application
  - `config.ts` - Global configuration settings
  - `domElements/` - DOM manipulation and UI components
  - `map/` - Map rendering and manipulation
  - `units/` - Unit creation and animation
  - `types/` - TypeScript type definitions

## Game Flow
1. Load game data from JSON
2. Display initial phase
3. When Play is clicked:
   - Show messages sequentially, one word at a time
   - When all messages are displayed, animate unit movements
   - When animations complete, show phase summary (if available)
   - Advance to next phase and repeat

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

## Code Style Preferences
- Use descriptive function and variable names
- Add JSDoc comments for all exported functions
- Log important state transitions to console
- Use TypeScript types for all parameters and return values