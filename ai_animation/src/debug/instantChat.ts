/**
 * Debug tool for making all chat messages appear instantly
 * Provides a toggle to skip word-by-word animation during message playback
 */

import { config } from '../config';
import { DebugMenu } from './debugMenu';

// Flag to control instant chat behavior
let instantChatEnabled = false;

/**
 * Gets whether instant chat is currently enabled
 */
export function isInstantChatEnabled(): boolean {
  return instantChatEnabled;
}

/**
 * Initializes the instant chat debug tool
 * @param debugMenu - The debug menu instance to add this tool to
 */
export function initInstantChatTool(debugMenu: DebugMenu): void {
  const content = `
    <div style="margin-bottom: 10px;">
      <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
        <input type="checkbox" id="instant-chat-toggle" style="margin: 0;">
        <span>Instant Chat Display</span>
      </label>
      <div style="font-size: 12px; color: #666; margin-top: 4px;">
        Skip word-by-word animation and show all chat messages instantly
      </div>
    </div>
  `;

  debugMenu.addDebugTool('Chat Controls', content);

  // Set up event listener for the toggle
  const toggleElement = document.getElementById('instant-chat-toggle') as HTMLInputElement;
  if (toggleElement) {
    // Set initial state
    toggleElement.checked = instantChatEnabled;

    // Handle toggle changes
    toggleElement.addEventListener('change', (e) => {
      const target = e.target as HTMLInputElement;
      instantChatEnabled = target.checked;
      
      if (config.isDebugMode) {
        console.log(`Instant chat ${instantChatEnabled ? 'enabled' : 'disabled'}`);
      }
    });
  }
}