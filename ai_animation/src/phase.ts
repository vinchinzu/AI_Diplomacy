import { gameState } from "./gameState";
import { logger } from "./logger";
import { updatePhaseDisplay } from "./domElements";
import { initUnits } from "./units/create";
import { updateSupplyCenterOwnership, updateLeaderboard, updateMapOwnership as _updateMapOwnership } from "./map/state";
import { updateChatWindows, addToNewsBanner } from "./domElements/chatWindows";
import { createAnimationsForNextPhase } from "./units/animate";
import { speakSummary } from "./speech";
import { config } from "./config";



// FIXME: Going to previous phases is borked. Units do not animate properly, map doesn't update.
function _setPhase(phaseIndex: number) {
  const gameLength = gameState.gameData.phases.length
  // Validate that the phaseIndex is within the bounds of the game length.
  if (phaseIndex >= gameLength || phaseIndex < 0) {
    throw new Error(`Provided invalid phaseIndex, cannot setPhase to ${phaseIndex} - game has ${gameState.gameData.phases.length} phases`)
  }
  if (phaseIndex - gameState.phaseIndex != 1) {
    // We're moving more than one Phase forward, or any number of phases backward, to do so clear the board and reInit the units on the correct phase
    gameState.unitAnimations = [];
    initUnits(phaseIndex)
    displayPhase()
  } else {

  }



  // Finally, update the gameState with the current phaseIndex
  gameState.phaseIndex = phaseIndex
  // If we're at the end of the game, don't attempt to animate. 
  if (phaseIndex === gameLength - 1) {

  } else {

    displayPhase()
  }
}

export function nextPhase() {
  _setPhase(gameState.phaseIndex + 1)
}

export function previousPhase() {
  _setPhase(gameState.phaseIndex - 1)
}

/**
 * Unified function to display a phase with proper transitions
 * Handles both initial display and animated transitions between phases
 * @param skipMessages Whether to skip message animations (used for initial load)
 */
export function displayPhase(skipMessages = false) {
  let index = gameState.phaseIndex
  if (index >= gameState.gameData.phases.length) {
    displayFinalPhase()
    logger.log("Displayed final phase, moving to next game.")
    gameState.loadNextGame()
    return;
  }
  if (!gameState.gameData || !gameState.gameData.phases ||
    index < 0) {
    logger.log("Invalid phase index.");
    return;
  }

  // Handle the special case for the first phase (index 0)
  const isFirstPhase = index === 0;
  const currentPhase = gameState.gameData.phases[index];

  // Only get previous phase if not the first phase
  const prevIndex = isFirstPhase ? null : (index > 0 ? index - 1 : null);
  const previousPhase = prevIndex !== null ? gameState.gameData.phases[prevIndex] : null;
  updatePhaseDisplay()



  // Update supply centers
  if (currentPhase.state?.centers) {
    updateSupplyCenterOwnership(currentPhase.state.centers);
  }


  // Update UI elements with smooth transitions
  updateLeaderboard(currentPhase);
  _updateMapOwnership();

  // Add phase info to news banner if not already there
  const phaseBannerText = `Phase: ${currentPhase.name}`;
  addToNewsBanner(phaseBannerText);

  // Log phase details to console only, don't update info panel with this
  const phaseInfo = `Phase: ${currentPhase.name}\nSCs: ${currentPhase.state?.centers ? JSON.stringify(currentPhase.state.centers) : 'None'}\nUnits: ${currentPhase.state?.units ? JSON.stringify(currentPhase.state.units) : 'None'}`;
  console.log(phaseInfo); // Use console.log instead of logger.log

  // Update info panel with power information
  logger.updateInfoPanel();

  // Show messages with animation or immediately based on skipMessages flag
  if (!skipMessages) {
    updateChatWindows(currentPhase, true);
  } else {
    gameState.messagesPlaying = false;
  }

  // Only animate if not the first phase and animations are requested
  if (!isFirstPhase && !skipMessages) {
    if (previousPhase) {
      createAnimationsForNextPhase();
    }
  } else {
    logger.log("No animations for this phase transition");
    gameState.messagesPlaying = false;
  }
}

/**
 * Display the initial phase without animations
 * Used when first loading a game
 */
export function displayInitialPhase() {
  gameState.phaseIndex = 0;
  initUnits(0);
  displayPhase(true);
}

/**
 * Display a phase with animations
 * Used during normal gameplay
 */
export function displayPhaseWithAnimation() {
  displayPhase(false);
}


/**
 * Advances to the next phase in the game sequence
 * Handles speaking summaries and transitioning to the next phase
 */
export function advanceToNextPhase() {
  // If we're not "playing" through the game, just skipping phases, move everything along
  if (!gameState.isPlaying) {
    moveToNextPhase()
  }

  if (!gameState.gameData || !gameState.gameData.phases || gameState.phaseIndex < 0) {
    logger.log("Cannot advance phase: invalid game state");
    return;
  }
  // Reset the nextPhaseScheduled flag to allow scheduling the next phase
  gameState.nextPhaseScheduled = false;

  // Get current phase
  const currentPhase = gameState.gameData.phases[gameState.phaseIndex];

  console.log(`Current phase: ${currentPhase.name}, Has summary: ${Boolean(currentPhase.summary)}`);
  if (currentPhase.summary) {
    console.log(`Summary preview: "${currentPhase.summary.substring(0, 50)}..."`);
  }

  if (config.isDebugMode) {
    console.log(`Processing phase transition for ${currentPhase.name}`);
  }

  // First show summary if available
  if (currentPhase.summary && currentPhase.summary.trim() !== '') {
    // Update the news banner with full summary
    addToNewsBanner(`(${currentPhase.name}) ${currentPhase.summary}`);
    console.log("Added summary to news banner, preparing to call speakSummary");

    // Speak the summary and advance after
    if (!gameState.isSpeaking) {
      speakSummary(currentPhase.summary)
        .then(() => {
          console.log("Speech completed successfully");
          if (gameState.isPlaying) {
            moveToNextPhase();
          }
        })
        .catch((error) => {
          console.error("Speech failed with error:", error);
          if (gameState.isPlaying) {
            moveToNextPhase();
          }
        });
    } else {
      console.error("Attempted to start speaking when already speaking...")
    }
  } else {
    console.log("No summary available, skipping speech");
    // No summary to speak, advance immediately
    moveToNextPhase();
  }
}

function displayFinalPhase() {
  if (!gameState.gameData || !gameState.gameData.phases || gameState.gameData.phases.length === 0) {
    return;
  }

  // Get the final phase to determine the winner
  const finalPhase = gameState.gameData.phases[gameState.gameData.phases.length - 1];

  if (!finalPhase.state?.centers) {
    logger.log("No supply center data available to determine winner");
    return;
  }

  // Find the power with the most supply centers
  let winner = '';
  let maxCenters = 0;

  for (const [power, centers] of Object.entries(finalPhase.state.centers)) {
    const centerCount = Array.isArray(centers) ? centers.length : 0;
    if (centerCount > maxCenters) {
      maxCenters = centerCount;
      winner = power;
    }
  }

  // Display victory message
  if (winner && maxCenters > 0) {
    const victoryMessage = `🏆 GAME OVER - ${winner} WINS with ${maxCenters} supply centers! 🏆`;

    // Add victory message to news banner with dramatic styling
    addToNewsBanner(victoryMessage);

    // Log the victory
    logger.log(`Victory! ${winner} wins the game with ${maxCenters} supply centers.`);

    // Display final standings in console
    const standings = Object.entries(finalPhase.state.centers)
      .map(([power, centers]) => ({
        power,
        centers: Array.isArray(centers) ? centers.length : 0
      }))
      .sort((a, b) => b.centers - a.centers);

    console.log("Final Standings:");
    standings.forEach((entry, index) => {
      const medal = index === 0 ? "🥇" : index === 1 ? "🥈" : index === 2 ? "🥉" : "  ";
      console.log(`${medal} ${entry.power}: ${entry.centers} centers`);
    });

    // Show victory in info panel
    logger.updateInfoPanel(`🏆 ${winner} VICTORIOUS! 🏆\n\nFinal Score: ${maxCenters} supply centers\n\nCheck console for full standings.`);
  } else {
    logger.log("Could not determine game winner");
  }
}

/**
 * Internal helper to handle the actual phase advancement
 */
function moveToNextPhase() {
  // Clear any existing animations to prevent overlap
  if (gameState.playbackTimer) {
    clearTimeout(gameState.playbackTimer);
    gameState.playbackTimer = 0;
  }

  // Reset animation state
  gameState.isAnimating = false;
  gameState.messagesPlaying = false;

  // Advance the phase index
  gameState.phaseIndex++;
  if (config.isDebugMode && gameState.gameData) {
    console.log(`Moving to phase ${gameState.gameData.phases[gameState.phaseIndex].name}`);
  }
  // Display the next phase and start showing its messages
  displayPhaseWithAnimation();
}
