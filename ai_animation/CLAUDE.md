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

## Code Style Preferences
- Use descriptive function and variable names
- Add JSDoc comments for all exported functions
- Log important state transitions to console
- Use TypeScript types for all parameters and return values