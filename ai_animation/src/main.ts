import * as THREE from "three";
import "./style.css"
import { initMap } from "./map/create";
import { gameState } from "./gameState";
import { logger } from "./logger";
import { loadBtn, prevBtn, nextBtn, speedSelector, fileInput, playBtn, mapView, loadGameBtnFunction } from "./domElements";
import { updateChatWindows } from "./domElements/chatWindows";
import { initStandingsBoard, hideStandingsBoard, showStandingsBoard } from "./domElements/standingsBoard";
import { displayPhaseWithAnimation, advanceToNextPhase, resetToPhase, nextPhase, previousPhase, togglePlayback } from "./phase";
import { config } from "./config";
import { Tween, Group, Easing } from "@tweenjs/tween.js";
import { initRotatingDisplay, updateRotatingDisplay } from "./components/rotatingDisplay";
import { closeTwoPowerConversation, showTwoPowerConversation } from "./components/twoPowerConversation";
import { PowerENUM } from "./types/map";
import { debugMenuInstance } from "./debug/debugMenu";
import { sineWave } from "./utils/timing";

//TODO: Create a function that finds a suitable unit location within a given polygon, for placing units better 
//  Currently the location for label, unit, and SC are all the same manually picked location

const isStreamingMode = import.meta.env.VITE_STREAMING_MODE === 'True' || import.meta.env.VITE_STREAMING_MODE === 'true'

// --- INITIALIZE SCENE ---
function initScene() {
  gameState.createThreeScene()
  
  // Enable audio on first user interaction (to comply with browser autoplay policies)
  let audioEnabled = false;
  const enableAudio = () => {
    if (!audioEnabled) {
      console.log('User interaction detected, audio enabled');
      audioEnabled = true;
      // Create and play a silent audio to unlock audio context
      const silentAudio = new Audio();
      silentAudio.volume = 0;
      silentAudio.play().catch(() => {});
      
      // Remove the listener after first interaction
      document.removeEventListener('click', enableAudio);
      document.removeEventListener('keydown', enableAudio);
    }
  };
  
  document.addEventListener('click', enableAudio);
  document.addEventListener('keydown', enableAudio);


  // Initialize standings board
  initStandingsBoard();

  // Load coordinate data, then build the map
  gameState.loadBoardState().then(() => {
    initMap(gameState.scene).then(() => {
      // Update info panel with initial power information
      logger.updateInfoPanel();

      // Initialize rotating display
      initRotatingDisplay('leaderboard');

      // Only show standings board at startup if no game is loaded
      if (!gameState.gameData || !gameState.gameData.phases || gameState.gameData.phases.length === 0) {
        showStandingsBoard();
      }

      gameState.cameraPanAnim = createCameraPan()

      // Load default game file if in debug mode
      if (config.isDebugMode || isStreamingMode) {
        gameState.loadGameFile(0);

        // Initialize info panel
        logger.updateInfoPanel();
      }

      // Initialize debug menu if in debug mode
      if (config.isDebugMode) {
        debugMenuInstance.show();
      }
      if (isStreamingMode) {
        setTimeout(() => {
          togglePlayback()
        }, 5000) // Increased delay to 5 seconds for Chrome to stabilize
      }
    })
  }).catch(err => {
    // Use console.error instead of logger.log to avoid updating the info panel
    console.error(`Error loading coords: ${err.message}`);
  });

  // Handle resizing
  window.addEventListener('resize', onWindowResize);

  // Kick off animation loop
  requestAnimationFrame(animate);

}

function createCameraPan(): Group {
  // Create a target object to store the desired camera position
  const cameraStart = { x: gameState.camera.position.x, y: gameState.camera.position.y, z: gameState.camera.position.z };

  // Move from the starting camera position to the left side of the map
  let moveToStartSweepAnim = new Tween(cameraStart).to({
    x: -400,
    y: 500,
    z: 1000
  }, 8000).onUpdate((target) => {
    // Use smooth interpolation to avoid jumps
    gameState.camera.position.lerp(new THREE.Vector3(target.x, target.y, target.z), 0.1);
  });

  let cameraSweepOperation = new Tween({ timeStep: 0 })
    .to({
      timeStep: Math.PI
    }, 20000)
    .onUpdate((tweenObj) => {
      let radius = 2200;
      // Calculate the target position
      const targetX = radius * Math.sin(tweenObj.timeStep / 2) - 400;
      const targetY = 500 + 200 * Math.sin(tweenObj.timeStep);
      const targetZ = 1000 + 900 * Math.sin(tweenObj.timeStep);

      gameState.camera.position.set(targetX, targetY, targetZ);
    })
    .easing(Easing.Quadratic.InOut).yoyo(true).repeat(Infinity);

  moveToStartSweepAnim.chain(cameraSweepOperation);
  moveToStartSweepAnim.start();
  return new Group(moveToStartSweepAnim, cameraSweepOperation);
}

// --- ANIMATION LOOP ---
/*
 * Main animation loop that runs continuously
 * Handles camera movement, animations, and game state transitions
 */
let lastTime = 0;
function animate(currentTime: number = 0) {
  // Calculate delta time in seconds
  let deltaTime = lastTime ? (currentTime - lastTime) / 1000 : 0;
  lastTime = currentTime;
  
  // Clamp delta time to prevent animation jumps when tab loses focus
  deltaTime = Math.min(deltaTime, config.animation.maxDeltaTime);
  
  // Update global timing in gameState
  gameState.deltaTime = deltaTime;
  gameState.globalTime = currentTime / 1000; // Store in seconds

  requestAnimationFrame(animate);
  if (gameState.isPlaying) {
    // Update the camera angle with delta time
    // Pass currentTime to update() to fix the Tween.js bug properly
    gameState.cameraPanAnim.update(currentTime);

  } else {
    // Manual camera controls when not in playback mode
    gameState.camControls.update();
  }

  // Check if all animations are complete
  if (gameState.unitAnimations.length > 0) {
    // Filter out completed animations
    const previousCount = gameState.unitAnimations.length;
    gameState.unitAnimations = gameState.unitAnimations.filter(anim => anim.isPlaying());

    // Log when animations complete
    if (previousCount > 0 && gameState.unitAnimations.length === 0) {
      console.log("All unit animations have completed");
    }

    // Call update on each active animation with current time
    gameState.unitAnimations.forEach((anim) => anim.update(currentTime))

  }

  // If all animations are complete and we're in playback mode
  if (gameState.unitAnimations.length === 0 && gameState.isPlaying && !gameState.messagesPlaying && !gameState.isSpeaking && !gameState.nextPhaseScheduled) {
    // Schedule next phase after a pause delay
    console.log(`Scheduling next phase in ${config.effectivePlaybackSpeed}ms`);
    gameState.nextPhaseScheduled = true;
    gameState.playbackTimer = setTimeout(() => {
      try {
        advanceToNextPhase()
      } catch {
        // FIXME: This is a dumb patch for us not being able to find the unit we expect to find.
        //    We should instead bee figuring out why units aren't where we expect them to be when the engine has said that is a valid move
        nextPhase()
        gameState.nextPhaseScheduled;
      }
    }, config.effectivePlaybackSpeed);
  }
  // Update any pulsing or wave animations on supply centers or units
  if (gameState.scene.userData.animatedObjects) {
    gameState.scene.userData.animatedObjects.forEach(obj => {
      if (obj.userData.pulseAnimation) {
        const anim = obj.userData.pulseAnimation;
        // Use delta time for consistent animation speed regardless of frame rate
        anim.time += anim.speed * deltaTime;
        if (obj.userData.glowMesh) {
          const pulseValue = sineWave(config.animation.supplyPulseFrequency, anim.time, anim.intensity, 0.5);
          obj.userData.glowMesh.material.opacity = 0.2 + (pulseValue * 0.3);
          const scale = 1 + (pulseValue * 0.1);
          obj.userData.glowMesh.scale.set(scale, scale, scale);
        }
        // Subtle bobbing up/down
        obj.position.y = 2 + sineWave(config.animation.supplyPulseFrequency, anim.time, 0.5);
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







// --- EVENT HANDLERS ---
loadBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', e => {
  const file = e.target.files[0];
  if (file) {
    loadGameBtnFunction(file);
    // Explicitly hide standings board after loading game
    hideStandingsBoard();
    // Update rotating display and relationship popup with game data
    if (gameState.gameData) {
      updateRotatingDisplay(gameState.gameData, gameState.phaseIndex, gameState.currentPower);
    }
  }
});

prevBtn.addEventListener('click', () => {
  previousPhase()
});
nextBtn.addEventListener('click', () => {
  // FIXME: Need to have this wait until all animations are complete, trying to click next when still animating results in not finding units where they should be.
  nextPhase()
});

playBtn.addEventListener('click', togglePlayback);

speedSelector.addEventListener('change', e => {
  config.playbackSpeed = parseInt(e.target.value);
  // If we're currently playing, restart the timer with the new speed
  if (gameState.isPlaying && gameState.playbackTimer) {
    clearTimeout(gameState.playbackTimer);
    gameState.playbackTimer = setTimeout(() => advanceToNextPhase(), config.effectivePlaybackSpeed);
  }
});


// --- BOOTSTRAP ON PAGE LOAD ---
window.addEventListener('load', initScene);




