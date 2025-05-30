/**
 * Speech Toggle Debug Tool
 * Allows toggling text-to-speech functionality on/off
 */

import { config } from "../config";
import type { DebugMenu } from "./debugMenu";

/**
 * Initializes the speech toggle debug tool
 * @param debugMenu - The debug menu instance to add this tool to
 */
export function initSpeechToggleTool(debugMenu: DebugMenu): void {
  const content = `
    <div style="margin: 8px 0;">
      <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
        <input type="checkbox" id="speech-toggle-checkbox" ${config.speechEnabled ? 'checked' : ''}>
        <span>Enable Text-to-Speech</span>
      </label>
      <small style="color: #666; margin-top: 4px; display: block;">
        Controls whether phase summaries are spoken aloud
      </small>
    </div>
  `;

  debugMenu.addDebugTool('Speech Control', content);

  // Add event listener for the checkbox
  const checkbox = document.getElementById('speech-toggle-checkbox') as HTMLInputElement;
  if (checkbox) {
    checkbox.addEventListener('change', (event) => {
      const target = event.target as HTMLInputElement;
      config.speechEnabled = target.checked;
      console.log(`Speech ${config.speechEnabled ? 'enabled' : 'disabled'}`);
    });
  }
}