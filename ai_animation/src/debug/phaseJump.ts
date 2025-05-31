/**
 * Phase Jump Debug Tool
 * Allows jumping to any phase in the game by name
 */

import { gameState } from '../gameState';
import { _setPhase } from '../phase';
import { DebugMenu } from './debugMenu';

/**
 * Initializes the phase jump debug tool
 */
export function initPhaseJumpTool(debugMenu: DebugMenu): void {
  const content = `
    <div class="debug-tool">
      <select id="phase-jump-select" style="
        padding: 6px 10px;
        border: 2px solid #4f3b16;
        border-radius: 4px;
        background-color: #faf0d8;
        color: #2f260b;
        font-family: 'Book Antiqua', Palatino, serif;
        width: 160px;
        font-size: 12px;
        margin-right: 8px;
      ">
        <option value="">Select Phase...</option>
      </select>
      <button id="phase-jump-btn" style="
        padding: 6px 12px;
        background-color: #8d5a2b;
        color: #f0e6d2;
        border: 2px solid #2e1c10;
        border-radius: 4px;
        cursor: pointer;
        font-family: 'Book Antiqua', Palatino, serif;
        font-size: 12px;
        white-space: nowrap;
      ">Jump</button>
    </div>
    <div id="phase-jump-feedback" style="
      margin-top: 5px;
      font-size: 11px;
      min-height: 14px;
    "></div>
  `;

  debugMenu.addDebugTool('Phase Jump', content, 'Future Tools');

  // Initialize the tool after adding to DOM
  setTimeout(() => {
    setupPhaseJumpTool();
  }, 100);
}

/**
 * Sets up the phase jump tool functionality
 */
function setupPhaseJumpTool(): void {
  const select = document.getElementById('phase-jump-select') as HTMLSelectElement;
  const button = document.getElementById('phase-jump-btn') as HTMLButtonElement;
  const feedback = document.getElementById('phase-jump-feedback') as HTMLElement;

  if (!select || !button || !feedback) {
    console.error('Phase jump tool elements not found');
    return;
  }

  // Populate phase options
  updatePhaseOptions();

  // Handle jump button click
  button.addEventListener('click', () => {
    const selectedPhaseName = select.value;
    if (!selectedPhaseName) {
      showFeedback('Please select a phase first', 'error');
      return;
    }

    jumpToPhase(selectedPhaseName);
  });

  // Handle Enter key in select
  select.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      button.click();
    }
  });

  // Handle hover effects
  button.addEventListener('mouseenter', () => {
    button.style.backgroundColor = '#a4703a';
  });

  button.addEventListener('mouseleave', () => {
    button.style.backgroundColor = '#8d5a2b';
  });
}

/**
 * Updates the phase options in the select dropdown
 */
function updatePhaseOptions(): void {
  const select = document.getElementById('phase-jump-select') as HTMLSelectElement;
  if (!select) return;

  // Clear existing options except the first one
  while (select.children.length > 1) {
    select.removeChild(select.lastChild!);
  }

  if (!gameState.gameData?.phases) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'No game loaded';
    option.disabled = true;
    select.appendChild(option);
    return;
  }

  // Add all phase names as options
  gameState.gameData.phases.forEach((phase, index) => {
    const option = document.createElement('option');
    option.value = phase.name;
    option.textContent = `${index}: ${phase.name}`;
    
    // Highlight current phase
    if (index === gameState.phaseIndex) {
      option.textContent += ' (current)';
      option.style.fontWeight = 'bold';
    }
    
    select.appendChild(option);
  });

  // Set current phase as selected
  if (gameState.gameData.phases[gameState.phaseIndex]) {
    select.value = gameState.gameData.phases[gameState.phaseIndex].name;
  }
}

/**
 * Jumps to the specified phase by name
 */
function jumpToPhase(phaseName: string): void {
  if (!gameState.gameData?.phases) {
    showFeedback('No game data available', 'error');
    return;
  }

  // Find the phase index by name
  const phaseIndex = gameState.gameData.phases.findIndex(phase => phase.name === phaseName);
  
  if (phaseIndex === -1) {
    showFeedback(`Phase "${phaseName}" not found`, 'error');
    return;
  }

  if (phaseIndex === gameState.phaseIndex) {
    showFeedback(`Already at phase "${phaseName}"`, 'info');
    return;
  }

  try {
    // Use the existing _setPhase function to jump to the phase
    _setPhase(phaseIndex);
    showFeedback(`Jumped to phase "${phaseName}" (index ${phaseIndex})`, 'success');
    
    // Update the dropdown to reflect the new current phase
    setTimeout(updatePhaseOptions, 100);
    
  } catch (error) {
    showFeedback(`Error jumping to phase: ${error instanceof Error ? error.message : 'Unknown error'}`, 'error');
    console.error('Phase jump error:', error);
  }
}

/**
 * Shows feedback message to the user
 */
function showFeedback(message: string, type: 'success' | 'error' | 'info'): void {
  const feedback = document.getElementById('phase-jump-feedback');
  if (!feedback) return;

  const colors = {
    success: '#2e7d32',
    error: '#d32f2f', 
    info: '#1976d2'
  };

  feedback.textContent = message;
  feedback.style.color = colors[type];
  
  // Clear feedback after 3 seconds
  setTimeout(() => {
    if (feedback.textContent === message) {
      feedback.textContent = '';
    }
  }, 3000);
}

/**
 * Updates the phase options (called when game state changes)
 */
export function updatePhaseJumpOptions(): void {
  // Only update if the tool is present in the DOM
  if (document.getElementById('phase-jump-select')) {
    updatePhaseOptions();
  }
}