import { gameState } from "./gameState";
import { logger } from "./logger";
import { updatePhaseDisplay, playBtn, prevBtn, nextBtn } from "./domElements";
import { initUnits } from "./units/create";
import { updateSupplyCenterOwnership, updateLeaderboard, updateMapOwnership as _updateMapOwnership, updateMapOwnership } from "./map/state";
import { updateChatWindows, addToNewsBanner } from "./domElements/chatWindows";
import { createAnimationsForNextPhase } from "./units/animate";
import { speakSummary } from "./speech";
import { config } from "./config";
import { debugMenuInstance } from "./debug/debugMenu";
import { showTwoPowerConversation, closeTwoPowerConversation } from "./components/twoPowerConversation";
import { closeVictoryModal, showVictoryModal } from "./components/victoryModal";
import { notifyPhaseChange } from "./webhooks/phaseNotifier";
import { updateRotatingDisplay } from "./components/rotatingDisplay";

const MOMENT_THRESHOLD = 8.0
// If we're in debug mode or instant mode, show it quick, otherwise show it for 30 seconds
const MOMENT_DISPLAY_TIMEOUT_MS = config.isDebugMode || config.isInstantMode ? 100 : 30000

// FIXME: Going to previous phases is borked. Units do not animate properly, map doesn't update.
export function _setPhase(phaseIndex: number) {
  console.log(`[Phase] _setPhase called with index: ${phaseIndex}`);

  // Store the old phase index at the very beginning
  const oldPhaseIndex = gameState.phaseIndex;

  if (config.isDebugMode) {
    debugMenuInstance.updateTools()
  }
  const gameLength = gameState.gameData.phases.length
  // Validate that the phaseIndex is within the bounds of the game length.
  if (phaseIndex >= gameLength || phaseIndex < 0) {
    throw new Error(`Provided invalid phaseIndex, cannot setPhase to ${phaseIndex} - game has ${gameState.gameData.phases.length} phases`)
  }
  if (phaseIndex - gameState.phaseIndex != 1) {
    // We're moving more than one Phase forward, or any number of phases backward, to do so clear the board and reInit the units on the correct phase
    gameState.unitAnimations = [];
    initUnits(phaseIndex)
    gameState.phaseIndex = phaseIndex
    updateMapOwnership()
    updatePhaseDisplay()
  } else {
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

    if (phaseIndex === gameLength - 1) {
      displayFinalPhase()
    } else {
      displayPhase()
    }
    gameState.nextPhaseScheduled = false;
  }

  // Finally, update the gameState with the current phaseIndex
  gameState.phaseIndex = phaseIndex

  // Send webhook notification for phase change
  notifyPhaseChange(oldPhaseIndex, phaseIndex);
}

// --- PLAYBACK CONTROLS ---
export function togglePlayback(explicitSet: boolean) {
  // If the game doesn't have any data, or there are no phases, return;
  if (!gameState.gameData || gameState.gameData.phases.length <= 0) {
    alert("This game file appears to be broken. Please reload the page and load a different game.")
    throw Error("Bad gameState, exiting.")
  };

  // TODO: Likely not how we want to handle the speaking section of this. 
  //   Should be able to pause the other elements while we're speaking
  if (gameState.isSpeaking) return;

  gameState.isPlaying = !gameState.isPlaying;
  if (typeof explicitSet === "boolean") {
    gameState.isPlaying = explicitSet
  }

  if (gameState.isPlaying) {
    playBtn.textContent = "⏸ Pause";
    prevBtn.disabled = true;
    nextBtn.disabled = true;
    logger.log("Starting playback...");

    if (gameState.cameraPanAnim) gameState.cameraPanAnim.getAll()[1].start()

    // Update rotating display
    if (gameState.gameData) {
      updateRotatingDisplay(gameState.gameData, gameState.phaseIndex, gameState.currentPower);
    }

    // First, show the messages of the current phase if it's the initial playback
    const phase = gameState.gameData.phases[gameState.phaseIndex];
    if (phase.messages && phase.messages.length) {
      // Show messages with stepwise animation
      logger.log(`Playing ${phase.messages.length} messages from phase ${gameState.phaseIndex + 1}/${gameState.gameData.phases.length}`);
      updateChatWindows(phase, true);
    } else {
      // No messages, go straight to unit animations
      logger.log("No messages for this phase, proceeding to animations");
      displayPhaseWithAnimation();
    }
  } else {
    if (gameState.cameraPanAnim) gameState.cameraPanAnim.getAll()[0].pause();
    playBtn.textContent = "▶ Play";
    if (gameState.playbackTimer) {
      clearTimeout(gameState.playbackTimer);
      gameState.playbackTimer = null;
    }
    gameState.messagesPlaying = false;
    prevBtn.disabled = false;
    nextBtn.disabled = false;
  }
}


export function nextPhase() {
  if (!gameState.isDisplayingMoment && gameState.gameData && gameState.momentsData) {
    let moment = gameState.checkPhaseHasMoment(gameState.gameData.phases[gameState.phaseIndex].name)
    if (moment !== null && moment.interest_score >= MOMENT_THRESHOLD && moment.powers_involved.length >= 2) {
      moment.hasBeenDisplayed = true

      const power1 = moment.powers_involved[0];
      const power2 = moment.powers_involved[1];

      showTwoPowerConversation({
        power1: power1,
        power2: power2,
        moment: moment
      })
      if (gameState.isPlaying) {

        setTimeout(() => {
          closeTwoPowerConversation()
          _setPhase(gameState.phaseIndex + 1)
        }, MOMENT_DISPLAY_TIMEOUT_MS)
      } else {
        _setPhase(gameState.phaseIndex + 1)
      }
    } else {
      _setPhase(gameState.phaseIndex + 1)
    }
  } else {
    console.log("not moving")
  }
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
    logger.log("Displayed final phase.")
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
  const phaseBannerText = `Phase: ${currentPhase.name}: ${currentPhase.summary}`;
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
      // Don't create animations immediately if messages are still playing
      // The main loop will handle this when messages finish
      if (!gameState.messagesPlaying) {
        createAnimationsForNextPhase();
      }
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
    nextPhase()
  }

  if (!gameState.gameData || !gameState.gameData.phases || gameState.phaseIndex < 0) {
    logger.log("Cannot advance phase: invalid game state");
    return;
  }

  // Get current phase
  const currentPhase = gameState.gameData.phases[gameState.phaseIndex];

  console.log(`Current phase: ${currentPhase.name}, Has summary: ${Boolean(currentPhase.summary)}`);
  if (currentPhase.summary) {
    console.log(`Summary preview: "${currentPhase.summary.substring(0, 50)}..."`);
  }

  if (config.isDebugMode) {
    console.log(`Processing phase transition for ${currentPhase.name}`);
  }

  // In streaming mode, add extra delay before speech to ensure phase is fully displayed
  const isStreamingMode = import.meta.env.VITE_STREAMING_MODE === 'True' || import.meta.env.VITE_STREAMING_MODE === 'true';
  const speechDelay = isStreamingMode ? 2000 : 0; // 2 second delay in streaming mode
  
  // First show summary if available
  if (currentPhase.summary && currentPhase.summary.trim() !== '') {
    // Delay speech in streaming mode
    setTimeout(() => {
      // Speak the summary and advance after
      if (!gameState.isSpeaking) {
        speakSummary(currentPhase.summary)
          .then(() => {
            console.log("Speech completed successfully");
            if (gameState.isPlaying) {
              nextPhase();
            }
          })
          .catch((error) => {
            console.error("Speech failed with error:", error);
            if (gameState.isPlaying) {
              nextPhase();
            }
          }).finally(() => {
            // Any cleanup code here
          });
      } else {
        console.error("Attempted to start speaking when already speaking...");
      }
    }, speechDelay);
  } else {
    console.log("No summary available, skipping speech");
    // No summary to speak, advance immediately
    nextPhase();
  }

  // Reset the nextPhaseScheduled flag to allow scheduling the next phase
  gameState.nextPhaseScheduled = false;
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
    // Create final standings
    const finalStandings = Object.entries(finalPhase.state.centers)
      .map(([power, centers]) => ({
        power,
        centers: Array.isArray(centers) ? centers.length : 0
      }))
      .sort((a, b) => b.centers - a.centers);

    // Show victory modal
    showVictoryModal({
      winner,
      maxCenters,
      finalStandings,
      onClose: () => {
        // Only proceed to next game if in playing mode
        if (gameState.isPlaying) {
          gameState.loadNextGame();
        }
      }
    });
    //setTimeout(closeVictoryModal, 10000)

    // Log the victory
    logger.log(`Victory! ${winner} wins the game with ${maxCenters} supply centers.`);

    // Display final standings in console
    console.log("Final Standings:");
    finalStandings.forEach((entry, index) => {
      const medal = index === 0 ? "🥇" : index === 1 ? "🥈" : index === 2 ? "🥉" : "  ";
      console.log(`${medal} ${entry.power}: ${entry.centers} centers`);
    });

    // Show victory in info panel
    logger.updateInfoPanel(`🏆 ${winner} VICTORIOUS! 🏆\n\nFinal Score: ${maxCenters} supply centers\n\nCheck console for full standings.`);
  } else {
    logger.log("Could not determine game winner");
  }
}
