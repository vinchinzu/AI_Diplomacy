import * as THREE from "three";
import "./style.css"
import { initMap } from "./map/create";
import { gameState } from "./gameState";
import { logger } from "./logger";
import { loadBtn, prevBtn, nextBtn, speedSelector, fileInput, playBtn, mapView, loadGameBtnFunction } from "./domElements";
import { updateChatWindows } from "./domElements/chatWindows";
import { initStandingsBoard, hideStandingsBoard, showStandingsBoard } from "./domElements/standingsBoard";
import { displayPhaseWithAnimation, advanceToNextPhase, resetToPhase, nextPhase, previousPhase } from "./phase";
import { config } from "./config";
import { Tween, Group, Easing } from "@tweenjs/tween.js";
import { initRotatingDisplay, updateRotatingDisplay } from "./components/rotatingDisplay";
import { closeTwoPowerConversation, showTwoPowerConversation } from "./components/twoPowerConversation";
import { PowerENUM } from "./types/map";
import { debugMenuInstance } from "./debug/debugMenu";

//TODO: Create a function that finds a suitable unit location within a given polygon, for placing units better 
//  Currently the location for label, unit, and SC are all the same manually picked location

const isStreamingMode = import.meta.env.VITE_STREAMING_MODE

// --- INITIALIZE SCENE ---
function initScene() {
  gameState.createThreeScene()


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
        }, 2000)
      }
    })
  }).catch(err => {
    // Use console.error instead of logger.log to avoid updating the info panel
    console.error(`Error loading coords: ${err.message}`);
  });

  // Handle resizing
  window.addEventListener('resize', onWindowResize);

  // Kick off animation loop
  animate();

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
function animate() {

  requestAnimationFrame(animate);
  if (gameState.isPlaying) {
    // Update the camera angle
    // FIXME: This has to call the update functino twice inorder to avoid a bug in Tween.js, see here  https://github.com/tweenjs/tween.js/issues/677
    gameState.cameraPanAnim.update();
    gameState.cameraPanAnim.update();

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

    // Call update on each active animation
    gameState.unitAnimations.forEach((anim) => anim.update())

    // If all animations are complete and we're in playback mode
    if (gameState.unitAnimations.length === 0 && gameState.isPlaying && !gameState.messagesPlaying && !gameState.isSpeaking) {
      // Schedule next phase after a pause delay
      console.log(`Scheduling next phase in ${config.playbackSpeed}ms`);
      gameState.playbackTimer = setTimeout(() => advanceToNextPhase(), config.playbackSpeed);
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




// --- PLAYBACK CONTROLS ---
function togglePlayback() {
  // If the game doesn't have any data, or there are no phases, return;
  if (!gameState.gameData || gameState.gameData.phases.length <= 0) {
    alert("This game file appears to be broken. Please reload the page and load a different game.")
    throw Error("Bad gameState, exiting.")
  };

  // TODO: Likely not how we want to handle the speaking section of this. 
  //   Should be able to pause the other elements while we're speaking
  if (gameState.isSpeaking) return;

  gameState.isPlaying = !gameState.isPlaying;

  if (gameState.isPlaying) {
    playBtn.textContent = "⏸ Pause";
    prevBtn.disabled = true;
    nextBtn.disabled = true;
    logger.log("Starting playback...");

    if (gameState.cameraPanAnim) gameState.cameraPanAnim.getAll()[1].start()
    // Hide standings board when playback starts
    hideStandingsBoard();

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
      updateRelationshipPopup();
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
    gameState.playbackTimer = setTimeout(() => advanceToNextPhase(), config.playbackSpeed);
  }
});


// --- BOOTSTRAP ON PAGE LOAD ---
window.addEventListener('load', initScene);




