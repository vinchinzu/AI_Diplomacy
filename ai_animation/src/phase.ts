import * as THREE from "three";
import { gameState } from "./gameState";
import { logger } from "./logger";
import { phaseDisplay } from "./domElements";
import { createSupplyCenters } from "./units/create";
import { createUnitMesh } from "./units/create";
import { updateSupplyCenterOwnership, updateLeaderboard, updateMapOwnership } from "./map/state";
import { updateChatWindows, addToNewsBanner } from "./domElements/chatWindows";
import { createTweenAnimations } from "./units/animate";
import { speakSummary } from "./speech";
import { config } from "./config";
import { getProvincePosition } from "./map/utils";

// New function to display initial state without messages
export function displayInitialPhase() {
  let index = 0
  if (!gameState.gameData || !gameState.gameData.phases || index < 0 || index >= gameState.gameData.phases.length) {
    logger.log("Invalid phase index.")
    return;
  }

  // Clear any existing units
  const supplyCenters = gameState.unitMeshes.filter(m => m.userData && m.userData.isSupplyCenter);
  const oldUnits = gameState.unitMeshes.filter(m => m.userData && !m.userData.isSupplyCenter);
  oldUnits.forEach(m => gameState.scene.remove(m));
  gameState.unitMeshes = supplyCenters;

  const phase = gameState.gameData.phases[index];
  phaseDisplay.textContent = `Era: ${phase.name || 'Unknown Era'} (${index + 1}/${gameState.gameData.phases.length})`;

  // Show supply centers
  let newSCs = createSupplyCenters();
  newSCs.forEach((sc) => gameState.scene.add(sc))
  if (phase.state?.centers) {
    updateSupplyCenterOwnership(phase.state.centers);
  }

  // Show units
  if (phase.state?.units) {
    for (const [power, unitArr] of Object.entries(phase.state.units)) {
      unitArr.forEach(unitStr => {
        const match = unitStr.match(/^([AF])\s+(.+)$/);
        if (match) {
          let newUnit = createUnitMesh({
            power: power.toUpperCase(),
            type: match[1],
            province: match[2],
          });
          gameState.scene.add(newUnit)
          gameState.unitMeshes.push(newUnit)
        }
      });
    }
  }

  updateLeaderboard(phase);
  updateMapOwnership(phase)

  logger.log(`Phase: ${phase.name}\nSCs: ${phase.state?.centers ? JSON.stringify(phase.state.centers) : 'None'}\nUnits: ${phase.state?.units ? JSON.stringify(phase.state.units) : 'None'}`)

  // Add: Update info panel
  logger.updateInfoPanel();

}

export function displayPhaseWithAnimation(index) {
  if (!gameState.gameData || !gameState.gameData.phases || index < 0 || index >= gameState.gameData.phases.length) {
    logger.log("Invalid phase index.")
    return;
  }

  // Reset animation attempted flag for the new phase
  gameState.animationAttempted = false;

  // Handle the special case for the first phase (index 0)
  const isFirstPhase = index === 0;
  const currentPhase = gameState.gameData.phases[index];
  
  // Only get previous phase if not the first phase
  const prevIndex = isFirstPhase ? null : (index > 0 ? index - 1 : gameState.gameData.phases.length - 1);
  const previousPhase = isFirstPhase ? null : gameState.gameData.phases[prevIndex];

  phaseDisplay.textContent = `Era: ${currentPhase.name || 'Unknown Era'} (${index + 1}/${gameState.gameData.phases.length})`;

  // Rebuild supply centers, remove old units

  // First show messages, THEN animate units after
  // First show messages with stepwise animation
  updateChatWindows(currentPhase, true);

  // Ownership
  if (currentPhase.state?.centers) {
    updateSupplyCenterOwnership(currentPhase.state.centers);
  }

  // Update leaderboard
  updateLeaderboard(currentPhase);
  updateMapOwnership(currentPhase)

  // Only animate if not the first phase
  if (!isFirstPhase) {
    createTweenAnimations(currentPhase, previousPhase);
  } else {
    logger.log("First phase - no previous phase to animate from");
    // Since we're not animating, mark messages as done
    gameState.messagesPlaying = false;
  }
  
  let msg = `Phase: ${currentPhase.name}\nSCs: ${JSON.stringify(currentPhase.state.centers)} \nUnits: ${currentPhase.state?.units ? JSON.stringify(currentPhase.state.units) : 'None'} `
  // Panel

  // Add: Update info panel
  logger.updateInfoPanel();
}


/**
 * Advances to the next phase in the game sequence
 * Handles speaking summaries and transitioning to the next phase
 */
export function advanceToNextPhase() {
  if (!gameState.gameData || !gameState.gameData.phases || gameState.phaseIndex < 0) {
    logger.log("Cannot advance phase: invalid game state");
    return;
  }

  // Get current phase
  const currentPhase = gameState.gameData.phases[gameState.phaseIndex];
  
  if (config.isDebugMode) {
    console.log(`Processing phase transition for ${currentPhase.name}`);
  }

  // Reset animation attempted flag for the next phase
  gameState.animationAttempted = false;

  // First show summary if available
  if (currentPhase.summary && currentPhase.summary.trim() !== '') {
    // Update the news banner with full summary
    addToNewsBanner(`(${currentPhase.name}) ${currentPhase.summary}`);

    // Speak the summary and advance after
    speakSummary(currentPhase.summary)
      .then(() => {
        if (gameState.isPlaying) {
          moveToNextPhase();
        }
      })
      .catch(() => {
        if (gameState.isPlaying) {
          moveToNextPhase();
        }
      });
  } else {
    // No summary to speak, advance immediately
    moveToNextPhase();
  }
}

/**
 * Internal helper to handle the actual phase advancement
 */
function moveToNextPhase() {
  // Clear any existing animations to prevent overlap
  if (gameState.playbackTimer) {
    clearTimeout(gameState.playbackTimer);
  }
  gameState.unitAnimations = [];

  // Advance the phase index
  if (gameState.phaseIndex >= gameState.gameData.phases.length - 1) {
    gameState.phaseIndex = 0;
    logger.log("Reached end of game, looping back to start");
  } else {
    gameState.phaseIndex++;
  }

  if (config.isDebugMode) {
    console.log(`Moving to phase ${gameState.gameData.phases[gameState.phaseIndex].name}`);
  }

  // Display the next phase and start showing its messages
  displayPhaseWithAnimation(gameState.phaseIndex);
}
