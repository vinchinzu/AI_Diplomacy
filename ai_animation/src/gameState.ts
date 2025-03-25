import * as THREE from "three"
import { type Province, type CoordinateData, CoordinateDataSchema, PowerENUM } from "./types/map"
import type { GameSchemaType } from "./types/gameState";
import { GameSchema } from "./types/gameState";
import { prevBtn, nextBtn, playBtn, speedSelector, mapView } from "./domElements";
import { createChatWindows } from "./domElements/chatWindows";
import { logger } from "./logger";
import { OrbitControls } from "three/examples/jsm/Addons.js";
import { displayInitialPhase } from "./phase";
import { Tween, Group as TweenGroup } from "@tweenjs/tween.js";

//FIXME: This whole file is a mess. Need to organize and format
//
// NEW: Add a lock for text-to-speech
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

// Export these variables to be used throughout the application
export let isSpeaking = false;   // Lock to pause game flow while TTS is active
export let currentPhaseIndex = 0; // Track the current phase index
export const currentPower = getRandomPower(); // Randomly selected power for the player
export const currentPowerUpper = currentPower.toUpperCase();


class GameState {
  boardState: CoordinateData
  gameData: GameSchemaType | null
  phaseIndex: number
  boardName: string

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
    this.gameData = null
    this.boardName = boardName
    // State locks
    this.isSpeaking = false
    this.isPlaying = false
    this.isAnimating = false
    this.messagesPlaying = false
    this.nextPhaseScheduled = false

    this.scene = new THREE.Scene()
    this.unitMeshes = []
    this.unitAnimations = []
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
  initScene = () => {
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
