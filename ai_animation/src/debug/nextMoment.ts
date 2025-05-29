/**
 * Next Moment Debug Tool
 * Shows the next moment that should occur based on phase name parsing
 */

import { gameState } from '../gameState';
import { getNextPhaseName, parsePhase } from '../types/moments';

/**
 * Initializes the next moment debug tool
 * @param debugMenu - Debug menu instance to add the tool to
 */
export function initNextMomentTool(debugMenu: any) {
  // Add next moment display tool
  debugMenu.addDebugTool(
    'Next Moment',
    `
    <div class="debug-tool">
      <div>Current Phase: <span id="debug-current-phase">--</span></div>
      <div>Next Phase: <span id="debug-next-phase">--</span></div>
      <div>Next Moment: <span id="debug-next-moment">--</span></div>
      <button id="debug-refresh-moment">Refresh</button>
    </div>
    `,
    'Future Tools'
  );

  // Initialize the next moment display
  updateNextMomentDisplay();

  // Add refresh button functionality
  const refreshBtn = document.getElementById('debug-refresh-moment');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', updateNextMomentDisplay);
  }
}

/**
 * Updates the next moment display in the debug menu
 */
export function updateNextMomentDisplay() {
  const currentPhaseElement = document.getElementById('debug-current-phase');
  const nextPhaseElement = document.getElementById('debug-next-phase');
  const nextMomentElement = document.getElementById('debug-next-moment');

  if (!currentPhaseElement || !nextPhaseElement || !nextMomentElement) return;

  if (!gameState.gameData || !gameState.gameData.phases || gameState.phaseIndex < 0) {
    currentPhaseElement.textContent = 'No game loaded';
    nextPhaseElement.textContent = '--';
    nextMomentElement.textContent = '--';
    return;
  }

  const currentPhase = gameState.gameData.phases[gameState.phaseIndex];
  const currentPhaseName = currentPhase.name;
  
  currentPhaseElement.textContent = currentPhaseName;

  // Get next phase name using our parser
  const nextPhaseName = getNextPhaseName(currentPhaseName);
  nextPhaseElement.textContent = nextPhaseName || 'Unable to parse';

  // Find next moment across all phases
  if (gameState.momentsData) {
    const nextMoment = findNextMoment(currentPhaseName);
    if (nextMoment) {
      nextMomentElement.innerHTML = `<strong>${nextMoment.category}</strong><br/>Phase: ${nextMoment.phase}<br/>Score: ${nextMoment.interest_score}`;
      nextMomentElement.style.color = nextMoment.interest_score >= 9 ? '#ff6b6b' : '#4dabf7';
    } else {
      nextMomentElement.textContent = 'No future moments found';
      nextMomentElement.style.color = '#888';
    }
  } else {
    nextMomentElement.textContent = 'Moments data not loaded';
    nextMomentElement.style.color = '#888';
  }
}

/**
 * Finds the next moment chronologically after the current phase
 * @param currentPhaseName - Current phase name
 * @returns Next moment or null if none found
 */
function findNextMoment(currentPhaseName: string) {
  if (!gameState.momentsData?.moments) return null;

  const currentParsed = parsePhase(currentPhaseName);
  if (!currentParsed) return null;

  // Get all moments that come after the current phase
  const futureMoments = gameState.momentsData.moments
    .map(moment => ({
      ...moment,
      parsedPhase: parsePhase(moment.phase)
    }))
    .filter(moment => 
      moment.parsedPhase && 
      moment.parsedPhase.order > currentParsed.order
    )
    .sort((a, b) => a.parsedPhase!.order - b.parsedPhase!.order);

  return futureMoments.length > 0 ? futureMoments[0] : null;
}