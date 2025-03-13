import * as THREE from "three";
import "./style.css"
import { UnitMesh } from "./types/units";
import { initMap } from "./map/create";
import { createTweenAnimations, proccessUnitAnimationWithTween } from "./units/animate";
import type { UnitAnimation } from "./units/animate";
import { gameState } from "./gameState";
import { logger } from "./logger";
import { loadBtn, prevBtn, nextBtn, speedSelector, fileInput, playBtn, mapView, loadGameBtnFunction, phaseDisplay } from "./domElements";
import { updateLeaderboard, updateMapOwnership, updateSupplyCenterOwnership } from "./map/state";

//TODO: Create a function that finds a suitable unit location within a given polygon, for placing units better 
//  Currently the location for label, unit, and SC are all the same manually picked location

//const isDebugMode = process.env.NODE_ENV === 'development' || localStorage.getItem('debug') === 'true';
const isDebugMode = true;

// --- CORE VARIABLES ---
let unitMeshes: UnitMesh[] = []; // To store references for units + supply center 3D objects
let playbackSpeed = 500; // Default speed in ms
let playbackTimer = null; // Timer reference for playback
let unitAnimations: UnitAnimation[] = []; // Track ongoing unit animations

let cameraPanTime = 0;   // Timer that drives the camera panning
const cameraPanSpeed = 0.0005; // Smaller = slower

// --- INITIALIZE SCENE ---
function initScene() {
  gameState.initScene()

  // Lighting (keep it simple)
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
  gameState.scene.add(ambientLight);

  const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
  dirLight.position.set(300, 400, 300);
  gameState.scene.add(dirLight);



  // Load coordinate data, then build the fallback map
  gameState.loadBoardState().then(() => {
    initMap(gameState.scene).then(() => {
      // Load default game file if in debug mode
      if (isDebugMode) {
        loadDefaultGameFile();
      }
    })
  }).catch(err => {
    console.error("Error loading coordinates:", err);
    logger.log(`Error loading coords: ${err.message}`)
  });

  // Handle resizing
  window.addEventListener('resize', onWindowResize);
  // Kick off animation loop
  animate();

  // Initialize info panel
  logger.updateInfoPanel();

}

// --- ANIMATION LOOP ---
function animate() {
  requestAnimationFrame(animate);


  if (gameState.isPlaying) {
    // Pan camera slowly in playback mode
    cameraPanTime += cameraPanSpeed;
    const angle = 0.9 * Math.sin(cameraPanTime) + 1.2;
    const radius = 1300;
    gameState.camera.position.set(
      radius * Math.cos(angle),
      650 + 80 * Math.sin(cameraPanTime * 0.5),
      100 + radius * Math.sin(angle)
    );

    // If messages are done playing but we haven't started unit animations yet
    if (!gameState.messagesPlaying && !gameState.isSpeaking && unitAnimations.length === 0 && gameState.isPlaying) {
      if (gameState.gameData && gameState.gameData.phases) {
        const prevIndex = gameState.phaseIndex > 0 ? gameState.phaseIndex - 1 : gameState.gameData.phases.length - 1;
        unitAnimations = createTweenAnimations(
          unitMeshes,
          gameState.gameData.phases[gameState.phaseIndex],
          gameState.gameData.phases[prevIndex]
        );
      }
    }
  } else {
    gameState.camControls.update();
  }

  // Process unit movement animations
  if (unitAnimations && unitAnimations.length > 0) {

    unitAnimations.forEach((anim: UnitAnimation, index) => {
      let isFinished = proccessUnitAnimationWithTween(anim)
      // Animation complete, remove from active animations
      if (isFinished) {
        unitAnimations.splice(index, 1);
      }

    });
    // >>> MODIFIED: Check if messages are still playing before advancing
    if (unitAnimations.length === 0 && gameState.isPlaying && !gameState.messagesPlaying) {
      // Schedule next phase after a pause delay
      playbackTimer = setTimeout(() => advanceToNextPhase(), playbackSpeed);
    }
  }

  // Update any pulsing or wave animations on supply centers or units
  if (gameState.scene.userData.animatedObjects) {
    gameState.scene.userData.animatedObjects.forEach(obj => {
      if (obj.userData.pulseAnimation) {
        const anim = obj.userData.pulseAnimation;
        anim.time += anim.speed;
        if (obj.userData.glowMesh) {
          const pulseValue = Math.sin(anim.time) * anim.intensity + 0.5;
          obj.userData.glowMesh.material.opacity = 0.2 + (pulseValue * 0.3);
          obj.userData.glowMesh.scale.set(
            1 + (pulseValue * 0.1),
            1 + (pulseValue * 0.1),
            1 + (pulseValue * 0.1)
          );
        }
        // Subtle bobbing up/down
        obj.position.y = 2 + Math.sin(anim.time) * 0.5;
      }
    });
  }

  gameState.camControls.update();
  gameState.renderer.render(gameState.scene, gameState.camera);
}


// --- RESIZE HANDLER ---
function onWindowResize() {
  gameState.camera.aspect = mapView.clientWidth / mapView.clientHeight;
  gameState.camera.updateProjectionMatrix();
  gameState.renderer.setSize(mapView.clientWidth, mapView.clientHeight);
}

// Load a default game if we're running debug
function loadDefaultGameFile() {
  console.log("Loading default game file for debug mode...");

  // Path to the default game file
  const defaultGameFilePath = './assets/default_game.json';

  fetch(defaultGameFilePath)
    .then(response => {
      if (!response.ok) {
        throw new Error(`Failed to load default game file: ${response.status}`);
      }
      return response.text();
    })
    .then(data => {
      gameState.loadGameData(data);
      console.log("Default game file loaded successfully");
    })
    .catch(error => {
      console.error("Error loading default game file:", error);
      logger.log(`Error loading default game: ${error.message}`)
    });
}


// --- PLAYBACK CONTROLS ---
function togglePlayback() {
  if (!gameState.gameData || gameState.gameData.phases.length <= 1) return;

  // NEW: If we're speaking, don't allow toggling playback
  if (isSpeaking) return;

  isPlaying = !isPlaying;

  if (isPlaying) {
    playBtn.textContent = "⏸ Pause";
    prevBtn.disabled = true;
    nextBtn.disabled = true;

    // First, show the messages of the current phase if it's the initial playback
    const phase = gameState.gameData.phases[gameState.phaseIndex];
    if (phase.messages && phase.messages.length) {
      // Show messages with stepwise animation
      updateChatWindows(phase, true);
    } else {
      // No messages, go straight to unit animations
      displayPhaseWithAnimation(gameState.phaseIndex);
    }
  } else {
    playBtn.textContent = "▶ Play";
    if (playbackTimer) {
      clearTimeout(playbackTimer);
      playbackTimer = null;
    }
    unitAnimations = [];
    messagesPlaying = false;
    prevBtn.disabled = false;
    nextBtn.disabled = false;
  }
}

// --- MODIFIED: Update news banner before TTS ---
async function advanceToNextPhase() {
  // Only show a summary if we have at least started the first phase
  // and only if the just-ended phase has a "summary" property.
  if (gameState.gameData && gameState.gameData.phases && gameState.phaseIndex >= 0) {
    const justEndedPhase = gameState.gameData.phases[gameState.phaseIndex];
    if (justEndedPhase.summary && justEndedPhase.summary.trim() !== '') {
      // UPDATED: First update the news banner with full summary
      addToNewsBanner(`(${justEndedPhase.name}) ${justEndedPhase.summary}`);

      // Then speak the summary (will be truncated internally)
      await speakSummary(justEndedPhase.summary);
    }
  }

  // If we've reached the end, loop back to the beginning
  if (gameState.phaseIndex >= gameState.gameData.phases.length - 1) {
    gameState.phaseIndex = 0;
  } else {
    gameState.phaseIndex++;
  }

  // Display the new phase with animation
  displayPhaseWithAnimation(gameState.phaseIndex);
}

function displayPhaseWithAnimation(index) {
  if (!gameState.gameData || !gameState.gameData.phases || index < 0 || index >= gameState.gameData.phases.length) {
    logger.log("Invalid phase index.")
    return;
  }

  const prevIndex = index > 0 ? index - 1 : gameState.gameData.phases.length - 1;
  const currentPhase = gameState.gameData.phases[index];
  const previousPhase = gameState.gameData.phases[prevIndex];

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

  unitAnimations = createTweenAnimations(unitMeshes, currentPhase, previousPhase);
  let msg = `Phase: ${currentPhase.name}\nSCs: ${JSON.stringify(currentPhase.state.centers)} \nUnits: ${currentPhase.state?.units ? JSON.stringify(currentPhase.state.units) : 'None'} `
  // Panel

  // Add: Update info panel
  logger.updateInfoPanel();

}

// --- EVENT HANDLERS ---
loadBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', e => {
  const file = e.target.files[0];
  if (file) {
    loadGameBtnFunction(file);
  }
});

prevBtn.addEventListener('click', () => {
  if (gameState.phaseIndex > 0) {
    gameState.phaseIndex--;
    displayPhaseWithAnimation(gameState.phaseIndex);
  }
});
nextBtn.addEventListener('click', () => {
  if (gameState.gameData && gameState.phaseIndex < gameState.gameData.phases.length - 1) {
    gameState.phaseIndex++;
    displayPhaseWithAnimation(gameState.phaseIndex);
  }
});

playBtn.addEventListener('click', togglePlayback);

speedSelector.addEventListener('change', e => {
  playbackSpeed = parseInt(e.target.value);
  // If we're currently playing, restart the timer with the new speed
  if (gameState.isPlaying && playbackTimer) {
    clearTimeout(playbackTimer);
    playbackTimer = setTimeout(() => advanceToNextPhase(), playbackSpeed);
  }
});

// --- BOOTSTRAP ON PAGE LOAD ---
window.addEventListener('load', initScene);

// Utility functions for color manipulation
function lightenColor(hex, percent) {
  return colorShift(hex, percent);
}

function darkenColor(hex, percent) {
  return colorShift(hex, -percent);
}

function colorShift(hex, percent) {
  // Convert hex to RGB
  let r = parseInt(hex.substr(1, 2), 16);
  let g = parseInt(hex.substr(3, 2), 16);
  let b = parseInt(hex.substr(5, 2), 16);

  // Shift color by percentage
  r = Math.min(255, Math.max(0, r + Math.floor(r * percent / 100)));
  g = Math.min(255, Math.max(0, g + Math.floor(g * percent / 100)));
  b = Math.min(255, Math.max(0, b + Math.floor(b * percent / 100)));

  // Convert back to hex
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')} `;
}



