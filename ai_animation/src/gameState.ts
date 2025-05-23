import * as THREE from "three"
import { updateRotatingDisplay } from "./components/rotatingDisplay";
import { updateRelationshipPopup } from "./domElements/relationshipPopup";
import { type CoordinateData, CoordinateDataSchema, PowerENUM } from "./types/map"
import type { GameSchemaType } from "./types/gameState";
import { GameSchema } from "./types/gameState";
import { prevBtn, nextBtn, playBtn, speedSelector, mapView } from "./domElements";
import { createChatWindows } from "./domElements/chatWindows";
import { logger } from "./logger";
import { OrbitControls } from "three/examples/jsm/Addons.js";
import { displayInitialPhase } from "./phase";
import { Tween, Group as TweenGroup } from "@tweenjs/tween.js";
import { hideStandingsBoard, } from "./domElements/standingsBoard";

//FIXME: This whole file is a mess. Need to organize and format

enum AvailableMaps {
  STANDARD = "standard"
}

/**
 * Return a random power from the PowerENUM for the player to control
 */
function getRandomPower(): PowerENUM {
  const values = Object.values(PowerENUM);
  const idx = Math.floor(Math.random() * values.length);
  return values[idx];
}



class GameState {
  boardState: CoordinateData
  gameId: number
  gameData: GameSchemaType
  phaseIndex: number
  boardName: string
  currentPower: PowerENUM

  // state locks
  messagesPlaying: boolean
  isPlaying: boolean
  isSpeaking: boolean
  isAnimating: boolean
  nextPhaseScheduled: boolean // Flag to prevent multiple phase transitions being scheduled

  //Scene for three.js
  scene: THREE.Scene

  // camera and controls
  camControls: OrbitControls
  camera: THREE.PerspectiveCamera
  renderer: THREE.WebGLRenderer

  unitMeshes: THREE.Group[]

  // Animations needed for this turn
  unitAnimations: Tween[]

  //
  playbackTimer: number

  // Camera Animation during playing
  cameraPanAnim: TweenGroup | undefined

  constructor(boardName: AvailableMaps) {
    this.phaseIndex = 0
    this.boardName = boardName
    this.currentPower = getRandomPower()
    this.gameId = 1
    // State locks
    this.isSpeaking = false
    this.isPlaying = false
    this.isAnimating = false
    this.messagesPlaying = false
    this.nextPhaseScheduled = false

    this.scene = new THREE.Scene()
    this.unitMeshes = []
    this.unitAnimations = []
    this.loadBoardState()
  }

  /**
   * Load game data from a JSON string and initialize the game state
   * @param gameDataString JSON string containing game data
   * @returns Promise that resolves when game is initialized or rejects if data is invalid
   */
  loadGameData = (gameDataString: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      try {
        // First parse the raw JSON
        const rawData = JSON.parse(gameDataString);

        // Log data structure for debugging
        console.log("Loading game data with structure:",
          `${rawData.phases?.length || 0} phases, ` +
          `orders format: ${rawData.phases?.[0]?.orders ? (Array.isArray(rawData.phases[0].orders) ? 'array' : 'object') : 'none'}`
        );

        // Show a sample of the first phase for diagnostic purposes
        if (rawData.phases && rawData.phases.length > 0) {
          console.log("First phase sample:", {
            name: rawData.phases[0].name,
            ordersCount: rawData.phases[0].orders ?
              (Array.isArray(rawData.phases[0].orders) ?
                rawData.phases[0].orders.length :
                Object.keys(rawData.phases[0].orders).length) : 0,
            ordersType: rawData.phases[0].orders ? typeof rawData.phases[0].orders : 'none',
            unitsCount: rawData.phases[0].units ? rawData.phases[0].units.length : 0
          });
        }

        // Parse the game data using Zod schema
        this.gameData = GameSchema.parse(rawData);
        logger.log(`Game data loaded: ${this.gameData.phases?.length || 0} phases found.`)

        // Reset phase index to beginning
        this.phaseIndex = 0;

        if (this.gameData.phases?.length) {
          // Enable UI controls
          prevBtn.disabled = false;
          nextBtn.disabled = false;
          playBtn.disabled = false;
          speedSelector.disabled = false;

          // Initialize chat windows for all powers
          createChatWindows();

          // Display the initial phase
          displayInitialPhase()
          resolve()
        } else {
          logger.log("Error: No phases found in game data");
          reject(new Error("No phases found in game data"))
        }
      } catch (error) {
        console.error("Error parsing game data:", error);
        if (error.errors) {
          // Format Zod validation errors more clearly
          const formattedErrors = error.errors.map(err =>
            `- Path ${err.path.join('.')}: ${err.message} (got ${err.received})`
          ).join('\n');
          logger.log(`Game data validation failed:\n${formattedErrors}`);
        } else {
          logger.log(`Error parsing game data: ${error.message}`);
        }
        reject(error);
      }
    })
  }

  loadBoardState = (): Promise<void> => {
    return new Promise((resolve, reject) => {
      fetch(`./maps/${this.boardName}/coords.json`)
        .then(response => {
          if (!response.ok) {
            throw new Error(`Failed to load coordinates: ${response.status}`);
          }
          return response.json()
        })
        .then((data) => {
          this.boardState = CoordinateDataSchema.parse(data)
          resolve()
        })
        .catch(error => {
          console.error(error);
          throw error
        });
    })
  }

  /**
   * Check if a power is present in the current game
   * @param power The power to check
   * @returns True if the power is present in the current phase
   */
  isPowerInGame = (power: string): boolean => {
    if (!this.gameData || !this.gameData.phases || this.phaseIndex < 0 || this.phaseIndex >= this.gameData.phases.length) {
      return false;
    }

    const currentPhase = this.gameData.phases[this.phaseIndex];

    // Check if power has units or centers in the current phase
    if (currentPhase.state?.units && power in currentPhase.state.units) {
      return true;
    }

    if (currentPhase.state?.centers && power in currentPhase.state.centers) {
      return true;
    }

    // Check if power has relationships defined
    if (currentPhase.agent_relationships && power in currentPhase.agent_relationships) {
      return true;
    }

    return false;
  }

  /*
   * Given a gameId, load that game's state into the GameState Object
   */
  loadGameFile = (gameId: number) => {

    // Clear any data that was already on the board, including messages, units, animations, etc.
    //clearGameData();

    // Path to the default game file
    const gameFilePath = `./default_game${gameId}.json`;

    fetch(gameFilePath)
      .then(response => {
        if (!response.ok) {
          throw new Error(`Failed to load default game file: ${response.status}`);
        }

        // Check content type to avoid HTML errors
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('text/html')) {
          throw new Error('Received HTML instead of JSON. Check the file path.');
        }

        return response.text();
      })
      .then(data => {
        // Check for HTML content as a fallback
        if (data.trim().startsWith('<!DOCTYPE') || data.trim().startsWith('<html')) {
          throw new Error('Received HTML instead of JSON. Check the file path.');
        }

        console.log("Loaded game file, attempting to parse...");
        return this.loadGameData(data);
      })
      .then(() => {
        console.log("Default game file loaded and parsed successfully");
        // Explicitly hide standings board after loading game
        hideStandingsBoard();
        // Update rotating display and relationship popup with game data
        if (this.gameData) {
          updateRotatingDisplay(this.gameData, this.phaseIndex, this.currentPower);
          updateRelationshipPopup();
        }
      })
      .catch(error => {
        // Use console.error instead of logger.log to avoid updating the info panel
        console.error(`Error loading game ${gameFilePath}: ${error.message}`);
      });
  }
  initScene = () => {
    if (mapView === null) {
      throw Error("Cannot find mapView element, unable to continue.")
    }
    this.scene.background = new THREE.Color(0x87CEEB);

    // Camera
    this.camera = new THREE.PerspectiveCamera(
      60,
      mapView.clientWidth / mapView.clientHeight,
      1,
      3000
    );
    this.camera.position.set(0, 800, 900); // MODIFIED: Increased z-value to account for map shift
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setSize(mapView.clientWidth, mapView.clientHeight);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    mapView.appendChild(this.renderer.domElement);

    // Controls
    this.camControls = new OrbitControls(this.camera, this.renderer.domElement);
    this.camControls.enableDamping = true;
    this.camControls.dampingFactor = 0.05;
    this.camControls.screenSpacePanning = true;
    this.camControls.minDistance = 100;
    this.camControls.maxDistance = 2000;
    this.camControls.maxPolarAngle = Math.PI / 2; // Limit so you don't flip under the map
    this.camControls.target.set(0, 0, 100); // ADDED: Set control target to new map center
  }
}


export let gameState = new GameState(AvailableMaps.STANDARD);
