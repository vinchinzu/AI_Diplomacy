/**
 * Debug tool for enabling instant mode across all animations and timings
 * Provides a toggle to skip all animations, speech, and delays
 */

import { config } from '../config';
import { DebugMenu } from './debugMenu';


/**
 * Initializes the instant mode debug tool
 * @param debugMenu - The debug menu instance to add this tool to
 */
export function initInstantChatTool(debugMenu: DebugMenu): void {
  const content = `
    <div style="margin-bottom: 10px;">
      <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
        <input type="checkbox" id="instant-mode-toggle" style="margin: 0;">
        <span>Instant Mode</span>
      </label>
      <div style="font-size: 12px; color: #666; margin-top: 4px;">
        Skip all animations, speech, and delays for instant game progression
      </div>
    </div>
  `;

  debugMenu.addDebugTool('Game Controls', content);

  // Set up event listener for the toggle
  const toggleElement = document.getElementById('instant-mode-toggle') as HTMLInputElement;
  if (toggleElement) {
    // Set initial state
    toggleElement.checked = config.isInstantMode;

    // Handle toggle changes
    toggleElement.addEventListener('change', (e) => {
      const target = e.target as HTMLInputElement;
      config.setInstantMode(target.checked);
    });
  }
}
