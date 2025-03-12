import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { FontLoader } from 'three/addons/loaders/FontLoader.js';
import { SVGLoader } from 'three/addons/loaders/SVGLoader.js';
import { addMapMouseEvents } from "./map/mouseMovement"
import { createLabel } from "./map/labels"
import "./style.css"

// --- NEW: ElevenLabs TTS helper function ---
const ELEVENLABS_API_KEY = import.meta.env.VITE_ELEVENLABS_API_KEY || "";
const VOICE_ID = "onwK4e9ZLuTAKqWW03F9";
const MODEL_ID = "eleven_multilingual_v2";

/**
 * Call ElevenLabs TTS to speak out loud. Returns a promise that
 * resolves only after the audio finishes playing (or fails).
 * Now accepts only the first 100 characters for brevity.
 */
async function speakSummary(summaryText) {
  if (!ELEVENLABS_API_KEY) {
    console.warn("No ElevenLabs API key found. Skipping TTS.");
    return;
  }

  // Set the speaking flag to block other animations/transitions
  isSpeaking = true;

  try {
    // Truncate text to first 100 characters for ElevenLabs
    const truncatedText = summaryText.substring(0, 100);
    if (truncatedText.length < summaryText.length) {
      console.log(`TTS text truncated from ${summaryText.length} to 100 characters`);
    }

    // Hit ElevenLabs TTS endpoint with the truncated text
    const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}`, {
      method: "POST",
      headers: {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
      },
      body: JSON.stringify({
        text: truncatedText,
        model_id: MODEL_ID,
        // Optional fine-tuning parameters
        // voice_settings: { stability: 0.3, similarity_boost: 0.8 },
      })
    });

    if (!response.ok) {
      throw new Error(`ElevenLabs TTS error: ${response.statusText}`);
    }

    // Convert response into a playable blob
    const audioBlob = await response.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    
    // Play the audio, pause until finished
    return new Promise((resolve, reject) => {
      const audio = new Audio(audioUrl);
      audio.play().then(() => {
        audio.onended = () => {
          // Clear the speaking flag when audio finishes
          isSpeaking = false;
          resolve();
        };
      }).catch(err => {
        console.error("Audio playback error", err);
        // Make sure to clear the flag even if there's an error
        isSpeaking = false;
        reject(err);
      });
    });

  } catch (err) {
    console.error("Failed to generate TTS from ElevenLabs:", err);
    // Make sure to clear the flag if there's any exception
    isSpeaking = false;
  }
}

//const isDebugMode = process.env.NODE_ENV === 'development' || localStorage.getItem('debug') === 'true';
const isDebugMode = false;

// Move these definitions BEFORE they're used
const ALL_POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY'];
function getRandomPower() {
  const idx = Math.floor(Math.random() * ALL_POWERS.length);
  return ALL_POWERS[idx];
}

// --- CORE VARIABLES ---
let scene, camera, renderer, controls;
let gameData = null;
let currentPhaseIndex = 0;
let coordinateData = null;
let unitMeshes = []; // To store references for units + supply center 3D objects
let mapPlane = null; // The fallback map plane
let isPlaying = false; // Track playback state
let playbackSpeed = 500; // Default speed in ms
let playbackTimer = null; // Timer reference for playback
let animationDuration = 1500; // Duration of unit movement animation in ms
let unitAnimations = []; // Track ongoing unit animations
let territoryTransitions = []; // Track territory color transitions
let chatWindows = {}; // Store chat window elements by power
let currentPower = getRandomPower(); // Now randomly selected

// >>> ADDED: Camera pan and message playback variables
let cameraPanTime = 0;   // Timer that drives the camera panning
const cameraPanSpeed = 0.0005; // Smaller = slower
let messagesPlaying = false;    // Lock to let messages animate before next phase
let faceIconCache = {}; // Cache for generated face icons
// NEW: Add a lock for text-to-speech
let isSpeaking = false;   // Lock to pause game flow while TTS is active

// --- DOM ELEMENTS ---
const loadBtn = document.getElementById('load-btn');
const fileInput = document.getElementById('file-input');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');
const playBtn = document.getElementById('play-btn');
const speedSelector = document.getElementById('speed-selector');
const phaseDisplay = document.getElementById('phase-display');
const infoPanel = document.getElementById('info-panel');
const mapView = document.getElementById('map-view');
const leaderboard = document.getElementById('leaderboard');

// Add roundRect polyfill for browsers that don't support it
if (!CanvasRenderingContext2D.prototype.roundRect) {
  CanvasRenderingContext2D.prototype.roundRect = function (x, y, width, height, radius) {
    if (typeof radius === 'undefined') {
      radius = 5;
    }
    this.beginPath();
    this.moveTo(x + radius, y);
    this.lineTo(x + width - radius, y);
    this.arcTo(x + width, y, x + width, y + radius, radius);
    this.lineTo(x + width, y + height - radius);
    this.arcTo(x + width, y + height, x + width - radius, y + height, radius);
    this.lineTo(x + radius, y + height);
    this.arcTo(x, y + height, x, y + height - radius, radius);
    this.lineTo(x, y + radius);
    this.arcTo(x, y, x + radius, y, radius);
    this.closePath();
    return this;
  };
}

// --- INITIALIZE SCENE ---
function initScene() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x87CEEB);

  // Camera
  camera = new THREE.PerspectiveCamera(
    60,
    mapView.clientWidth / mapView.clientHeight,
    1,
    3000
  );
  camera.position.set(0, 800, 900); // MODIFIED: Increased z-value to account for map shift

  // Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(mapView.clientWidth, mapView.clientHeight);
  renderer.setPixelRatio(window.devicePixelRatio);
  mapView.appendChild(renderer.domElement);

  // Controls
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.screenSpacePanning = true;
  controls.minDistance = 100;
  controls.maxDistance = 2000;
  controls.maxPolarAngle = Math.PI / 2; // Limit so you don't flip under the map
  controls.target.set(0, 0, 100); // ADDED: Set control target to new map center

  // Lighting (keep it simple)
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
  scene.add(ambientLight);

  const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
  dirLight.position.set(300, 400, 300);
  scene.add(dirLight);



  // Load coordinate data, then build the fallback map
  loadCoordinateData()
    .then(() => {
      drawMap();  // Create the map plane from the start
      // target the center of the map
      controls.target = new THREE.Vector3(800, 0, 800)
    })
    .catch(err => {
      console.error("Error loading coordinates:", err);
    });

  // Handle resizing
  window.addEventListener('resize', onWindowResize);
  addMapMouseEvents(mapView)
  // Kick off animation loop
  animate();

  // Initialize info panel
  updateInfoPanel();
}

// --- ANIMATION LOOP ---
function animate() {
  requestAnimationFrame(animate);

  const currentTime = Date.now();

  if (isPlaying) {
    // Pan camera slowly in playback mode
    cameraPanTime += cameraPanSpeed;
    const angle = 0.9 * Math.sin(cameraPanTime) + 1.2;
    const radius = 1300;
    camera.position.set(
      radius * Math.cos(angle),
      650 + 80 * Math.sin(cameraPanTime * 0.5),
      100 + radius * Math.sin(angle)
    );

    // If messages are done playing but we haven't started unit animations yet
    if (!messagesPlaying && !isSpeaking && unitAnimations.length === 0 && isPlaying) {
      if (gameData && gameData.phases) {
        const prevIndex = currentPhaseIndex > 0 ? currentPhaseIndex - 1 : gameData.phases.length - 1;
        animateUnitsForPhase(
          gameData.phases[currentPhaseIndex],
          gameData.phases[prevIndex]
        );
      }
    }
  } else {
    controls.update();
  }

  // Process unit movement animations
  if (unitAnimations.length > 0) {
    unitAnimations.forEach((anim, index) => {
      // Calculate progress (0 to 1)
      const elapsed = currentTime - anim.startTime;
      const progress = Math.min(1, elapsed / anim.duration);

      // Apply movement
      if (progress < 1) {
        // Apply easing for more natural movement - ease in and out
        const easedProgress = easeInOutCubic(progress);

        // Update position
        anim.object.position.x = anim.startPos.x + (anim.endPos.x - anim.startPos.x) * easedProgress;
        anim.object.position.z = anim.startPos.z + (anim.endPos.z - anim.startPos.z) * easedProgress;

        // Subtle bobbing up and down during movement
        anim.object.position.y = 10 + Math.sin(progress * Math.PI * 2) * 5;

        // For fleets (ships), add a gentle rocking motion
        if (anim.object.userData.type === 'F') {
          anim.object.rotation.z = Math.sin(progress * Math.PI * 3) * 0.05;
          anim.object.rotation.x = Math.sin(progress * Math.PI * 2) * 0.05;
        }
      } else {
        // Animation complete, remove from active animations
        unitAnimations.splice(index, 1);

        // Set final position
        anim.object.position.x = anim.endPos.x;
        anim.object.position.z = anim.endPos.z;
        anim.object.position.y = 10; // Reset height

        // Reset rotation for ships
        if (anim.object.userData.type === 'F') {
          anim.object.rotation.z = 0;
          anim.object.rotation.x = 0;
        }

        // >>> MODIFIED: Check if messages are still playing before advancing
        if (unitAnimations.length === 0 && isPlaying && !messagesPlaying && !isSpeaking) {
          // Schedule next phase after a pause delay
          playbackTimer = setTimeout(() => {
            // Call the async function without awaiting it here
            advanceToNextPhase();
          }, playbackSpeed);
        }
      }
    });
  }

  // Process territory color transitions
  if (territoryTransitions.length > 0) {
    territoryTransitions.forEach((transition, index) => {
      const elapsed = currentTime - transition.startTime;
      const progress = Math.min(1, elapsed / transition.duration);

      if (progress < 1) {
        // Interpolate colors
        const easedProgress = easeInOutCubic(progress);
        transition.canvas.style.opacity = easedProgress;
      } else {
        // Transition complete
        territoryTransitions.splice(index, 1);
        transition.canvas.style.opacity = 1;
      }
    });
  }

  // Update any pulsing or wave animations on supply centers or units
  if (scene.userData.animatedObjects) {
    scene.userData.animatedObjects.forEach(obj => {
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

  controls.update();
  renderer.render(scene, camera);
}

// Easing function for smooth animations
function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

// --- RESIZE HANDLER ---
function onWindowResize() {
  camera.aspect = mapView.clientWidth / mapView.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(mapView.clientWidth, mapView.clientHeight);
}

// --- LOAD COORDINATE DATA ---
function loadCoordinateData() {
  return new Promise((resolve, reject) => {
    fetch('./assets/maps/standard/standard_coords.json')
      .then(response => {
        if (!response.ok) {
          // Try an alternate path if desired
          return fetch('../assets/maps/standard_coords.json');
        }
        return response;
      })
      .then(response => {
        if (!response.ok) {
          // Another fallback path
          return fetch('/diplomacy/animation/assets/maps/standard_coords.json');
        }
        return response;
      })
      .then(response => {
        if (!response.ok) {
          throw new Error(`Failed to load coordinates: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        coordinateData = data;
        resolve(coordinateData);
      })
      .catch(error => {
        console.error(error);
        reject(error);
      });
  });
}

// --- CREATE THE FALLBACK MAP AS A PLANE ---
function drawMap() {
  const loader = new SVGLoader();
  loader.load('assets/maps/standard/standard.svg',
    function (data) {
      fetch('assets/maps/standard/standard_styles.json')
        .then(resp => resp.json())
        .then(map_styles => {
          const paths = data.paths;
          const group = new THREE.Group();
          const textGroup = new THREE.Group();

          for (let i = 0; i < paths.length; i++) {
            let fillColor = ""
            const path = paths[i];
            // The "standard" map has keys like _mos, so remove that then send them to caps
            let provinceKey = path.userData.node.id.substring(1).toUpperCase();


            if (map_styles[path.userData.node.classList[0]] === undefined) {
              // If there is no style in the map_styles, skip drawing the shape
              continue
            } else if (provinceKey && coordinateData.provinces[provinceKey] && coordinateData.provinces[provinceKey].owner) {
              fillColor = getPowerHexColor(coordinateData.provinces[provinceKey].owner)
            }
            else {
              fillColor = map_styles[path.userData.node.classList[0]].fill;
            }

            const material = new THREE.MeshBasicMaterial({
              color: fillColor,
              side: THREE.DoubleSide,
              depthWrite: false
            });

            const shapes = SVGLoader.createShapes(path);

            for (let j = 0; j < shapes.length; j++) {

              const shape = shapes[j];
              const geometry = new THREE.ShapeGeometry(shape);
              const mesh = new THREE.Mesh(geometry, material);

              mesh.rotation.x = Math.PI / 2;
              if (provinceKey && coordinateData.provinces[provinceKey] && coordinateData.provinces[provinceKey].owner) {
                coordinateData.provinces[provinceKey].mesh = mesh
              }
              group.add(mesh);


              // Create an edges geometry from the shape geometry.
              const edges = new THREE.EdgesGeometry(geometry);
              // Create a line material with black color for the border.
              const lineMaterial = new THREE.LineBasicMaterial({ color: 0x000000, linewidth: 2 });
              // Create the line segments object to display the border.
              const line = new THREE.LineSegments(edges, lineMaterial);
              // Add the border as a child of the mesh.
              mesh.add(line);
            }
          }

          // Load all the labels for each map position
          const fontLoader = new FontLoader();
          fontLoader.load('assets/fonts/helvetiker_regular.typeface.json', function (font) {
            for (const [key, value] of Object.entries(coordinateData.provinces)) {

              textGroup.add(createLabel(font, key, value))
            }
          })
          // This rotates the SVG the "correct" way round, and scales it down
          group.scale.set(1, -1, 1)
          textGroup.rotation.x = Math.PI / 2;
          textGroup.scale.set(1, -1, 1)

          // After adding all meshes to the group, update its matrix:
          group.updateMatrixWorld(true);
          textGroup.updateMatrixWorld(true);

          // Compute the bounding box of the group:
          const box = new THREE.Box3().setFromObject(group);
          const center = new THREE.Vector3();
          box.getCenter(center);


          scene.add(group);
          scene.add(textGroup);

          // Set the camera's target to the center of the map
          controls.target = center
          camera.position.set(center.x, 1400, 1100)
        })
        .catch(error => {
          console.error('Error loading map styles:', error);
        });
    },
    // Progress function
    undefined,
    function (error) { console.log(error) })

  return
}



// Get color for a power
function getPowerHexColor(power) {
  const powerColors = {
    'AUSTRIA': '#c40000',
    'ENGLAND': '#00008B',
    'FRANCE': '#0fa0d0',
    'GERMANY': '#444444',
    'ITALY': '#008000',
    'RUSSIA': '#cccccc',
    'TURKEY': '#e0c846'
  };
  return powerColors[power] || '#b19b69'; // fallback to neutral
}


// --- 3D SUPPLY CENTERS ---
function displaySupplyCenters() {
  if (!coordinateData || !coordinateData.provinces) return;
  for (const [province, data] of Object.entries(coordinateData.provinces)) {
    if (data.isSupplyCenter && coordinateData.provinces[province]) {
      const pos = getProvincePosition(province);

      // Build a small pillar + star in 3D
      const scGroup = new THREE.Group();

      const baseGeom = new THREE.CylinderGeometry(12, 12, 3, 16);
      const baseMat = new THREE.MeshStandardMaterial({ color: 0x333333 });
      const base = new THREE.Mesh(baseGeom, baseMat);
      base.position.y = 1.5;
      scGroup.add(base);

      const pillarGeom = new THREE.CylinderGeometry(2.5, 2.5, 12, 8);
      const pillarMat = new THREE.MeshStandardMaterial({ color: 0xcccccc });
      const pillar = new THREE.Mesh(pillarGeom, pillarMat);
      pillar.position.y = 7.5;
      scGroup.add(pillar);

      // We'll just do a cone star for simplicity
      const starGeom = new THREE.ConeGeometry(6, 10, 5);
      const starMat = new THREE.MeshStandardMaterial({ color: 0xFFD700 });
      const starMesh = new THREE.Mesh(starGeom, starMat);
      starMesh.rotation.x = Math.PI; // point upwards
      starMesh.position.y = 14;
      scGroup.add(starMesh);

      // Optionally add a glow disc
      const glowGeom = new THREE.CircleGeometry(15, 32);
      const glowMat = new THREE.MeshBasicMaterial({ color: 0xFFFFAA, transparent: true, opacity: 0.3, side: THREE.DoubleSide });
      const glowMesh = new THREE.Mesh(glowGeom, glowMat);
      glowMesh.rotation.x = -Math.PI / 2;
      glowMesh.position.y = 2;
      scGroup.add(glowMesh);

      // Store userData for ownership changes
      scGroup.userData = {
        province,
        isSupplyCenter: true,
        owner: null,
        starMesh,
        glowMesh
      };

      scGroup.position.set(pos.x, 2, pos.z);
      scene.add(scGroup);
      unitMeshes.push(scGroup);
    }
  }
}

function updateSupplyCenterOwnership(centers) {
  if (!centers) return;
  const ownershipMap = {};
  // centers is typically { "AUSTRIA":["VIE","BUD"], "FRANCE":["PAR","MAR"], ... }
  for (const [power, provinces] of Object.entries(centers)) {
    provinces.forEach(p => {
      // No messages, animate units immediately
      ownershipMap[p.toUpperCase()] = power.toUpperCase();
    });
  }

  unitMeshes.forEach(obj => {
    if (obj.userData && obj.userData.isSupplyCenter) {
      const prov = obj.userData.province;
      const owner = ownershipMap[prov];
      if (owner) {
        const c = getPowerHexColor(owner);
        obj.userData.starMesh.material.color.setHex(c);

        // Add a pulsing animation
        if (!obj.userData.pulseAnimation) {
          obj.userData.pulseAnimation = {
            speed: 0.003 + Math.random() * 0.002,
            intensity: 0.3,
            time: Math.random() * Math.PI * 2
          };
          if (!scene.userData.animatedObjects) scene.userData.animatedObjects = [];
          scene.userData.animatedObjects.push(obj);
        }
      } else {
        // Neutral
        obj.userData.starMesh.material.color.setHex(0xFFD700);
        // remove pulse
        obj.userData.pulseAnimation = null;
      }
    }
  });
}

// --- UNITS ---
function displayUnit(unitData) {
  const color = getPowerHexColor(unitData.power);

  let group = new THREE.Group();
  // Minimal shape difference for armies vs fleets
  if (unitData.type === 'A') {
    // Army: a block + small head for soldier-like appearance
    const body = new THREE.Mesh(
      new THREE.BoxGeometry(15, 20, 10),
      new THREE.MeshStandardMaterial({ color })
    );
    body.position.y = 10;
    group.add(body);

    // Head
    const head = new THREE.Mesh(
      new THREE.SphereGeometry(4, 12, 12),
      new THREE.MeshStandardMaterial({ color })
    );
    head.position.set(0, 24, 0);
    group.add(head);
  } else {
    // Fleet: a rectangle + a mast and sail
    const hull = new THREE.Mesh(
      new THREE.BoxGeometry(30, 8, 15),
      new THREE.MeshStandardMaterial({ color: 0x8B4513 })
    );
    hull.position.y = 4;
    group.add(hull);

    // Mast
    const mast = new THREE.Mesh(
      new THREE.CylinderGeometry(1, 1, 30, 8),
      new THREE.MeshStandardMaterial({ color: 0x000000 })
    );
    mast.position.y = 15;
    group.add(mast);

    // Sail
    const sail = new THREE.Mesh(
      new THREE.PlaneGeometry(20, 15),
      new THREE.MeshStandardMaterial({ color, side: THREE.DoubleSide })
    );
    sail.rotation.y = Math.PI / 2;
    sail.position.set(0, 15, 0);
    group.add(sail);
  }

  // Position
  const pos = getProvincePosition(unitData.location);
  group.position.set(pos.x, 10, pos.z);

  // Store meta
  group.userData = {
    power: unitData.power,
    type: unitData.type,
    location: unitData.location
  };

  scene.add(group);
  unitMeshes.push(group);
}

function getProvincePosition(loc) {
  // Convert e.g. "Spa/sc" to "SPA_SC" if needed
  const normalized = loc.toUpperCase().replace('/', '_');
  const base = normalized.split('_')[0];

  if (coordinateData && coordinateData.provinces) {
    if (coordinateData.provinces[normalized]) {
      return {
        "x": coordinateData.provinces[normalized].label.x,
        "y": 10,
        "z": coordinateData.provinces[normalized].label.y
      };
    }
    if (coordinateData.provinces[base]) {
      return coordinateData.provinces[base].label;
    }
  }

  // Fallback with offset
  const pos = hashStringToPosition(loc);
  return { x: pos.x, y: pos.y, z: pos.z + 100 };
}

function hashStringToPosition(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  const x = (hash % 800) - 400;
  const z = ((hash >> 8) % 800) - 400;
  return { x, y: 0, z };
}

// --- LOADING & DISPLAYING GAME PHASES ---
function loadGame(file) {
  const reader = new FileReader();
  reader.onload = e => {
    try {
      gameData = JSON.parse(e.target.result);
      currentPhaseIndex = 0;
      if (gameData.phases?.length) {
        prevBtn.disabled = false;
        nextBtn.disabled = false;
        playBtn.disabled = false;
        speedSelector.disabled = false;

        // Initialize chat windows
        createChatWindows();

        // Display initial phase but WITHOUT messages
        displayInitialPhase(currentPhaseIndex);
      }
      
      // Add: Update info panel
      updateInfoPanel();
    } catch (err) {
      console.error("Error parsing JSON:", err);
      infoPanel.textContent = "Error parsing JSON: " + err.message;
    }
  };
  reader.onerror = () => {
    infoPanel.textContent = "Error reading file.";
  };
  reader.readAsText(file);
}

// New function to display initial state without messages
function displayInitialPhase(index) {
  if (!gameData || !gameData.phases || index < 0 || index >= gameData.phases.length) {
    infoPanel.textContent = "Invalid phase index.";
    return;
  }

  // Clear any existing units
  const supplyCenters = unitMeshes.filter(m => m.userData && m.userData.isSupplyCenter);
  const oldUnits = unitMeshes.filter(m => m.userData && !m.userData.isSupplyCenter);
  oldUnits.forEach(m => scene.remove(m));
  unitMeshes = supplyCenters;

  const phase = gameData.phases[index];
  phaseDisplay.textContent = `Era: ${phase.name || 'Unknown Era'} (${index + 1}/${gameData.phases.length})`;

  // Show supply centers
  displaySupplyCenters();
  if (phase.state?.centers) {
    updateSupplyCenterOwnership(phase.state.centers);
  }

  // Show units
  if (phase.state?.units) {
    for (const [power, unitArr] of Object.entries(phase.state.units)) {
      unitArr.forEach(unitStr => {
        const match = unitStr.match(/^([AF])\s+(.+)$/);
        if (match) {
          displayUnit({
            power: power.toUpperCase(),
            type: match[1],
            location: match[2],
          });
        }
      });
    }
  }

  updateLeaderboard(phase);
  updateMapOwnership(phase)

  // DON'T show messages yet - skip updateChatWindows call

  // Add: Update info panel
  updateInfoPanel();
  
  drawMap()
}

// --- LEADERBOARD FUNCTION ---
function updateLeaderboard(phase) {
  // Get supply center counts
  const centerCounts = {};
  const unitCounts = {};

  // Count supply centers by power
  if (phase.state?.centers) {
    for (const [power, provinces] of Object.entries(phase.state.centers)) {
      centerCounts[power] = provinces.length;
    }
  }

  // Count units by power
  if (phase.state?.units) {
    for (const [power, units] of Object.entries(phase.state.units)) {
      unitCounts[power] = units.length;
    }
  }

  // Combine all powers from both centers and units
  const allPowers = new Set([
    ...Object.keys(centerCounts),
    ...Object.keys(unitCounts)
  ]);

  // Sort powers by supply center count (descending)
  const sortedPowers = Array.from(allPowers).sort((a, b) => {
    return (centerCounts[b] || 0) - (centerCounts[a] || 0);
  });

  // Build HTML for leaderboard
  let html = `<strong>Council Standings</strong><br/>`;

  sortedPowers.forEach(power => {
    const centers = centerCounts[power] || 0;
    const units = unitCounts[power] || 0;

    // Use CSS classes instead of inline styles for better contrast
    html += `<div style="margin: 5px 0; display: flex; justify-content: space-between;">
          <span class="power-${power.toLowerCase()}">${power}</span>
          <span>${centers} SCs, ${units} units</span>
        </div>`;
  });

  // Add victory condition reminder
  html += `<hr style="border-color: #555; margin: 8px 0;"/>
        <small>Victory: 18 supply centers</small>`;

  leaderboard.innerHTML = html;
}

// --- PLAYBACK CONTROLS ---
function togglePlayback() {
  if (!gameData || gameData.phases.length <= 1) return;

  // NEW: If we're speaking, don't allow toggling playback
  if (isSpeaking) return;

  isPlaying = !isPlaying;

  if (isPlaying) {
    playBtn.textContent = "⏸ Pause";
    prevBtn.disabled = true;
    nextBtn.disabled = true;

    // First, show the messages of the current phase if it's the initial playback
    const phase = gameData.phases[currentPhaseIndex];
    if (phase.messages && phase.messages.length) {
      // Show messages with stepwise animation
      updateChatWindows(phase, true);
    } else {
      // No messages, go straight to unit animations
      displayPhaseWithAnimation(currentPhaseIndex);
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
  if (gameData && gameData.phases && currentPhaseIndex >= 0) {
    const justEndedPhase = gameData.phases[currentPhaseIndex];
    if (justEndedPhase.summary && justEndedPhase.summary.trim() !== '') {
      // UPDATED: First update the news banner with full summary
      addToNewsBanner(`(${justEndedPhase.name}) ${justEndedPhase.summary}`);
      
      // Then speak the summary (will be truncated internally)
      await speakSummary(justEndedPhase.summary);
    }
  }

  // If we've reached the end, loop back to the beginning
  if (currentPhaseIndex >= gameData.phases.length - 1) {
    currentPhaseIndex = 0;
  } else {
    currentPhaseIndex++;
  }

  // Display the new phase with animation
  displayPhaseWithAnimation(currentPhaseIndex);
}

function displayPhaseWithAnimation(index) {
  if (!gameData || !gameData.phases || index < 0 || index >= gameData.phases.length) {
    infoPanel.textContent = "Invalid phase index.";
    return;
  }

  const prevIndex = index > 0 ? index - 1 : gameData.phases.length - 1;
  const currentPhase = gameData.phases[index];
  const previousPhase = gameData.phases[prevIndex];

  phaseDisplay.textContent = `Era: ${currentPhase.name || 'Unknown Era'} (${index + 1}/${gameData.phases.length})`;

  // Rebuild supply centers, remove old units
  const supplyCenters = unitMeshes.filter(m => m.userData && m.userData.isSupplyCenter);
  const oldUnits = unitMeshes.filter(m => m.userData && !m.userData.isSupplyCenter);
  oldUnits.forEach(m => scene.remove(m));
  unitMeshes = supplyCenters;

  // Ownership
  if (currentPhase.state?.centers) {
    updateSupplyCenterOwnership(currentPhase.state.centers);
  }

  // Update leaderboard
  updateLeaderboard(currentPhase);
  updateMapOwnership(currentPhase)


  // First show messages, THEN animate units after
  if (currentPhase.messages && currentPhase.messages.length) {
    // First show messages with stepwise animation
    updateChatWindows(currentPhase, true);

    // We'll animate units only after messages are done
    // This happens in the animation loop when messagesPlaying becomes false
  } else {
    // No messages, animate units immediately
    animateUnitsForPhase(currentPhase, previousPhase);
  }

  // Panel
  // Remove: infoPanel.textContent = `Phase: ${currentPhase.name}\nSCs: ${currentPhase.state?.centers ? JSON.stringify(currentPhase.state.centers) : 'None'}\nUnits: ${currentPhase.state?.units ? JSON.stringify(currentPhase.state.units) : 'None'}`;
  
  // Add: Update info panel
  updateInfoPanel();
  
  drawMap()
}

function updateMapOwnership(currentPhase) {

  for (const [power, unitArr] of Object.entries(currentPhase.state.units)) {
    unitArr.forEach(unitStr => {
      const match = unitStr.match(/^([AF])\s+(.+)$/);
      if (!match) return;
      const unitType = match[1];
      const location = match[2];
      const normalized = location.toUpperCase().replace('/', '_');
      const base = normalized.split('_')[0];
      if (coordinateData.provinces[base] === undefined) {
        console.log(base)
      }
      coordinateData.provinces[base].owner = power
    })
  }
  for (const [key, value] of Object.entries(coordinateData.provinces)) {
    let powerColor = getPowerHexColor(coordinateData.provinces[key].owner)
    powerColor = parseInt(powerColor.substring(1), 16);
    coordinateData.provinces[key].mesh?.material.color.setHex(powerColor)

  }
}

// New helper function to animate units for a phase
function animateUnitsForPhase(currentPhase, previousPhase) {
  // Prepare unit position maps
  const previousUnitPositions = {};
  if (previousPhase.state?.units) {
    for (const [power, unitArr] of Object.entries(previousPhase.state.units)) {
      unitArr.forEach(unitStr => {
        const match = unitStr.match(/^([AF])\s+(.+)$/);
        if (match) {
          const key = `${power}-${match[1]}-${match[2]}`;
          previousUnitPositions[key] = getProvincePosition(match[2]);
        }
      });
    }
  }

  // Animate new units from old positions (or spawn from below)
  unitAnimations = [];
  if (currentPhase.state?.units) {
    for (const [power, unitArr] of Object.entries(currentPhase.state.units)) {
      unitArr.forEach(unitStr => {
        const match = unitStr.match(/^([AF])\s+(.+)$/);
        if (!match) return;
        const unitType = match[1];
        const location = match[2];
        const key = `${power}-${unitType}-${location}`;
        const unitMesh = createUnitMesh({
          power: power.toUpperCase(),
          type: unitType,
          location
        });


        // Current final
        const currentPos = getProvincePosition(location);

        // Start pos
        let startPos;
        let matchFound = false;
        for (const prevKey in previousUnitPositions) {
          if (prevKey.startsWith(`${power}-${unitType}`)) {
            startPos = previousUnitPositions[prevKey];
            matchFound = true;
            delete previousUnitPositions[prevKey];
            break;
          }
        }
        if (!matchFound) {
          // New spawn
          startPos = { x: currentPos.x, y: -20, z: currentPos.z };
        }

        unitMesh.position.set(startPos.x, 10, startPos.z);
        scene.add(unitMesh);
        unitMeshes.push(unitMesh);

        // Animate
        unitAnimations.push({
          object: unitMesh,
          startPos,
          endPos: currentPos,
          startTime: Date.now(),
          duration: animationDuration
        });
      });
    }
  }
}
function createUnitMesh(unitData) {
  const color = getPowerHexColor(unitData.power);

  let group = new THREE.Group();
  // Minimal shape difference for armies vs fleets
  if (unitData.type === 'A') {
    // Army: a block + small head for soldier-like appearance
    const body = new THREE.Mesh(
      new THREE.BoxGeometry(15, 20, 10),
      new THREE.MeshStandardMaterial({ color })
    );
    body.position.y = 10;
    group.add(body);

    // Head
    const head = new THREE.Mesh(
      new THREE.SphereGeometry(4, 12, 12),
      new THREE.MeshStandardMaterial({ color })
    );
    head.position.set(0, 24, 0);
    group.add(head);
  } else {
    // Fleet: a rectangle + a mast and sail
    const hull = new THREE.Mesh(
      new THREE.BoxGeometry(30, 8, 15),
      new THREE.MeshStandardMaterial({ color: 0x8B4513 })
    );
    hull.position.y = 4;
    group.add(hull);

    // Mast
    const mast = new THREE.Mesh(
      new THREE.CylinderGeometry(1, 1, 30, 8),
      new THREE.MeshStandardMaterial({ color: 0x000000 })
    );
    mast.position.y = 15;
    group.add(mast);

    // Sail
    const sail = new THREE.Mesh(
      new THREE.PlaneGeometry(20, 15),
      new THREE.MeshStandardMaterial({ color, side: THREE.DoubleSide })
    );
    sail.rotation.y = Math.PI / 2;
    sail.position.set(0, 15, 0);
    group.add(sail);
  }

  // Store metadata
  group.userData = {
    power: unitData.power,
    type: unitData.type,
    location: unitData.location
  };

  return group;
}
// --- EVENT HANDLERS ---
loadBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', e => {
  const file = e.target.files[0];
  if (file) {
    loadGame(file);
  }
});

prevBtn.addEventListener('click', () => {
  if (currentPhaseIndex > 0) {
    currentPhaseIndex--;
    displayPhaseWithAnimation(currentPhaseIndex);
  }
});
nextBtn.addEventListener('click', () => {
  if (gameData && currentPhaseIndex < gameData.phases.length - 1) {
    currentPhaseIndex++;
    displayPhaseWithAnimation(currentPhaseIndex);
  }
});

playBtn.addEventListener('click', togglePlayback);

speedSelector.addEventListener('change', e => {
  playbackSpeed = parseInt(e.target.value);
  // If we're currently playing, restart the timer with the new speed
  if (isPlaying && playbackTimer) {
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
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

// --- CHAT WINDOW FUNCTIONS ---
function createChatWindows() {
  // Clear existing chat windows
  const chatContainer = document.getElementById('chat-container');
  chatContainer.innerHTML = '';
  chatWindows = {};

  // Create a chat window for each power (except the current power)
  const powers = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY'];

  // Filter out the current power for chat windows
  const otherPowers = powers.filter(power => power !== currentPower);

  // Add a GLOBAL chat window first
  createChatWindow('GLOBAL', true);

  // Create chat windows for each power except the current one
  otherPowers.forEach(power => {
    createChatWindow(power);
  });
}

// Modified to use 3D face icons properly
function createChatWindow(power, isGlobal = false) {
  const chatContainer = document.getElementById('chat-container');
  const chatWindow = document.createElement('div');
  chatWindow.className = 'chat-window';
  chatWindow.id = `chat-${power}`;
  chatWindow.style.position = 'relative'; // Add relative positioning for absolute child positioning

  // Create a slimmer header with appropriate styling
  const header = document.createElement('div');
  header.className = 'chat-header';

  // Adjust header to accommodate larger face icons
  header.style.display = 'flex';
  header.style.alignItems = 'center';
  header.style.padding = '4px 8px'; // Reduced vertical padding
  header.style.height = '24px'; // Explicit smaller height
  header.style.backgroundColor = 'rgba(78, 62, 41, 0.7)'; // Semi-transparent background
  header.style.borderBottom = '1px solid rgba(78, 62, 41, 1)'; // Solid bottom border

  // Create the title element
  const titleElement = document.createElement('span');
  if (isGlobal) {
    titleElement.style.color = '#ffffff';
    titleElement.textContent = 'GLOBAL';
  } else {
    titleElement.className = `power-${power.toLowerCase()}`;
    titleElement.textContent = power;
  }
  titleElement.style.fontWeight = 'bold'; // Make text more prominent
  titleElement.style.textShadow = '1px 1px 2px rgba(0,0,0,0.7)'; // Add text shadow for better readability
  header.appendChild(titleElement);

  // Create container for 3D face icon that floats over the header
  const faceHolder = document.createElement('div');
  faceHolder.style.width = '64px';
  faceHolder.style.height = '64px';
  faceHolder.style.position = 'absolute'; // Position absolutely
  faceHolder.style.right = '10px'; // From right edge
  faceHolder.style.top = '0px'; // ADJUSTED: Moved lower to align with the header
  faceHolder.style.cursor = 'pointer';
  faceHolder.style.borderRadius = '50%';
  faceHolder.style.overflow = 'hidden';
  faceHolder.style.boxShadow = '0 2px 5px rgba(0,0,0,0.5)';
  faceHolder.style.border = '2px solid #fff';
  faceHolder.style.zIndex = '10'; // Ensure it's above other elements
  faceHolder.id = `face-${power}`;

  // Generate the face icon and add it to the chat window (not header)
  generateFaceIcon(power).then(dataURL => {
    const img = document.createElement('img');
    img.src = dataURL;
    img.style.width = '100%';
    img.style.height = '100%';
    img.id = `face-img-${power}`; // Add ID for animation targeting

    img.id = `face-img-${power}`; // Add ID for animation targeting

    // Add subtle idle animation
    setInterval(() => {
      if (!img.dataset.animating && Math.random() < 0.1) {
        idleAnimation(img);
      }
    }, 3000);

    faceHolder.appendChild(img);
  });

  // Create messages container with extra top padding to avoid overlap with floating head

  header.appendChild(faceHolder);

  // Create messages container
  const messagesContainer = document.createElement('div');
  messagesContainer.className = 'chat-messages';
  messagesContainer.id = `messages-${power}`;
  messagesContainer.style.paddingTop = '8px'; // Add padding to prevent content being hidden under face

  // Add toggle functionality
  header.addEventListener('click', () => {
    chatWindow.classList.toggle('chat-collapsed');
  });

  // Assemble chat window - add faceHolder directly to chatWindow, not header
  chatWindow.appendChild(header);
  chatWindow.appendChild(faceHolder);
  chatWindow.appendChild(messagesContainer);

  // Add to container
  chatContainer.appendChild(chatWindow);

  // Store reference
  chatWindows[power] = {
    element: chatWindow,
    messagesContainer: messagesContainer,
    isGlobal: isGlobal,
    seenMessages: new Set()
  };
}

// Modified to accumulate messages instead of resetting and only animate for new messages
function updateChatWindows(phase, stepMessages = false) {
  if (!phase.messages || !phase.messages.length) {
    messagesPlaying = false;
    return;
  }

  const relevantMessages = phase.messages.filter(msg => {
    return (
      msg.sender === currentPower ||
      msg.recipient === currentPower ||
      msg.recipient === 'GLOBAL'
    );
  });
  relevantMessages.sort((a, b) => a.time_sent - b.time_sent);

  if (!stepMessages) {
    // Normal: show all at once
    relevantMessages.forEach(msg => {
      const isNew = addMessageToChat(msg, phase.name);
      if (isNew) {
        animateHeadNod(msg);
      }
    });
    messagesPlaying = false;
  } else {
    // Stepwise
    messagesPlaying = true;
    let index = 0;

    const showNext = () => {
      if (index >= relevantMessages.length) {
        messagesPlaying = false;
        if (unitAnimations.length === 0 && isPlaying && !isSpeaking) {
          // Call the async function without awaiting it here
          playbackTimer = setTimeout(() => advanceToNextPhase(), playbackSpeed);
        }
        return;
      }
      const msg = relevantMessages[index];
      const isNew = addMessageToChat(msg, phase.name);
      if (isNew && !isDebugMode) {
        animateHeadNod(msg);
      }
      index++;
      // Increase the delay between messages - 3x the playback speed gives more spacing
      // Remove the delay if we're developing
      if (isDebugMode) {
        showNext()
      } else {
        setTimeout(showNext, playbackSpeed * 3);
      }
    };

    // Start the message sequence
    showNext();
  }
}

// Modified to return whether this was a new message
function addMessageToChat(msg, phaseName) {
  // Determine which chat window to use
  let targetPower;
  if (msg.recipient === 'GLOBAL') {
    targetPower = 'GLOBAL';
  } else {
    targetPower = msg.sender === currentPower ? msg.recipient : msg.sender;
  }
  if (!chatWindows[targetPower]) return;

  // Create a unique ID for this message to avoid duplication
  const msgId = `${msg.sender}-${msg.recipient}-${msg.time_sent}-${msg.message}`;

  // Skip if we've already shown this message
  if (chatWindows[targetPower].seenMessages.has(msgId)) {
    return false; // Not a new message
  }

  // Mark as seen
  chatWindows[targetPower].seenMessages.add(msgId);

  const messagesContainer = chatWindows[targetPower].messagesContainer;
  const messageElement = document.createElement('div');

  // Style based on sender/recipient
  if (targetPower === 'GLOBAL') {
    // Global chat shows sender info
    const senderColor = msg.sender.toLowerCase();
    messageElement.className = 'chat-message message-incoming';
    messageElement.innerHTML = `
      <span style="font-weight: bold;" class="power-${senderColor}">${msg.sender}:</span>
      ${msg.message}
      <div class="message-time">${phaseName}</div>
    `;
  } else {
    // Private chat - outgoing or incoming style
    const isOutgoing = msg.sender === currentPower;
    messageElement.className = `chat-message ${isOutgoing ? 'message-outgoing' : 'message-incoming'}`;
    messageElement.innerHTML = `
      ${msg.message}
      <div class="message-time">${phaseName}</div>
    `;
  }

  // Add to container
  messagesContainer.appendChild(messageElement);

  // Scroll to bottom
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  return true; // This was a new message
}

// Animate a head nod when a message appears
function animateHeadNod(msg) {
  // Determine which chat window's head to animate
  let targetPower;
  if (msg.recipient === 'GLOBAL') {
    targetPower = 'GLOBAL';
  } else {
    targetPower = msg.sender === currentPower ? msg.recipient : msg.sender;
  }

  const chatWindow = chatWindows[targetPower]?.element;
  if (!chatWindow) return;

  // Find the face image and animate it
  const img = chatWindow.querySelector(`#face-img-${targetPower}`);
  if (!img) return;

  img.dataset.animating = 'true';

  // Choose a random animation type for variety
  const animationType = Math.floor(Math.random() * 4);

  let animation;

  switch (animationType) {
    case 0: // Nod animation
      animation = img.animate([
        { transform: 'rotate(0deg) scale(1)' },
        { transform: 'rotate(15deg) scale(1.1)' },
        { transform: 'rotate(-10deg) scale(1.05)' },
        { transform: 'rotate(5deg) scale(1.02)' },
        { transform: 'rotate(0deg) scale(1)' }
      ], {
        duration: 600,
        easing: 'ease-in-out'
      });
      break;

    case 1: // Bounce animation
      animation = img.animate([
        { transform: 'translateY(0) scale(1)' },
        { transform: 'translateY(-8px) scale(1.15)' },
        { transform: 'translateY(3px) scale(0.95)' },
        { transform: 'translateY(-2px) scale(1.05)' },
        { transform: 'translateY(0) scale(1)' }
      ], {
        duration: 700,
        easing: 'ease-in-out'
      });
      break;

    case 2: // Shake animation
      animation = img.animate([
        { transform: 'translate(0, 0) rotate(0deg)' },
        { transform: 'translate(-5px, -3px) rotate(-5deg)' },
        { transform: 'translate(5px, 2px) rotate(5deg)' },
        { transform: 'translate(-5px, 1px) rotate(-3deg)' },
        { transform: 'translate(0, 0) rotate(0deg)' }
      ], {
        duration: 500,
        easing: 'ease-in-out'
      });
      break;

    case 3: // Pulse animation
      animation = img.animate([
        { transform: 'scale(1)', boxShadow: '0 0 0 0 rgba(255,255,255,0.7)' },
        { transform: 'scale(1.2)', boxShadow: '0 0 0 10px rgba(255,255,255,0)' },
        { transform: 'scale(1)', boxShadow: '0 0 0 0 rgba(255,255,255,0)' }
      ], {
        duration: 800,
        easing: 'ease-out'
      });
      break;
  }

  animation.onfinish = () => {
    img.dataset.animating = 'false';
  };

  // Trigger random snippet
  playRandomSoundEffect();
}

// Generate a 3D face icon for chat windows with higher contrast
async function generateFaceIcon(power) {
  if (faceIconCache[power]) {
    return faceIconCache[power];
  }

  // Even larger renderer size for better quality
  const offWidth = 192, offHeight = 192; // Increased from 128x128 to 192x192
  const offRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  offRenderer.setSize(offWidth, offHeight);
  offRenderer.setPixelRatio(1);

  // Scene
  const offScene = new THREE.Scene();
  offScene.background = null;

  // Camera
  const offCamera = new THREE.PerspectiveCamera(45, offWidth / offHeight, 0.1, 1000);
  offCamera.position.set(0, 0, 50);

  // Power-specific colors with higher contrast/saturation
  const colorMap = {
    'GLOBAL': 0xf5f5f5, // Brighter white
    'AUSTRIA': 0xff0000, // Brighter red
    'ENGLAND': 0x0000ff, // Brighter blue
    'FRANCE': 0x00bfff, // Brighter cyan
    'GERMANY': 0x1a1a1a, // Darker gray for better contrast
    'ITALY': 0x00cc00, // Brighter green
    'RUSSIA': 0xe0e0e0, // Brighter gray
    'TURKEY': 0xffcc00  // Brighter yellow
  };
  const headColor = colorMap[power] || 0x808080;

  // Larger head geometry
  const headGeom = new THREE.BoxGeometry(20, 20, 20); // Increased from 16x16x16
  const headMat = new THREE.MeshStandardMaterial({ color: headColor });
  const headMesh = new THREE.Mesh(headGeom, headMat);
  offScene.add(headMesh);

  // Create outline for better visibility (a slightly larger black box behind)
  const outlineGeom = new THREE.BoxGeometry(22, 22, 19);
  const outlineMat = new THREE.MeshBasicMaterial({ color: 0x000000 });
  const outlineMesh = new THREE.Mesh(outlineGeom, outlineMat);
  outlineMesh.position.z = -2; // Place it behind the head
  offScene.add(outlineMesh);

  // Larger eyes with better contrast
  const eyeGeom = new THREE.BoxGeometry(3.5, 3.5, 3.5); // Increased from 2.5x2.5x2.5
  const eyeMat = new THREE.MeshStandardMaterial({ color: 0x000000 });
  const leftEye = new THREE.Mesh(eyeGeom, eyeMat);
  leftEye.position.set(-4.5, 2, 10); // Adjusted position
  offScene.add(leftEye);
  const rightEye = new THREE.Mesh(eyeGeom, eyeMat);
  rightEye.position.set(4.5, 2, 10); // Adjusted position
  offScene.add(rightEye);

  // Add a simple mouth
  const mouthGeom = new THREE.BoxGeometry(8, 1.5, 1);
  const mouthMat = new THREE.MeshBasicMaterial({ color: 0x000000 });
  const mouth = new THREE.Mesh(mouthGeom, mouthMat);
  mouth.position.set(0, -3, 10);
  offScene.add(mouth);

  // Brighter lighting for better contrast
  const light = new THREE.DirectionalLight(0xffffff, 1.2); // Increased intensity
  light.position.set(0, 20, 30);
  offScene.add(light);

  // Add more lights for better definition
  const fillLight = new THREE.DirectionalLight(0xffffff, 0.5);
  fillLight.position.set(-20, 0, 20);
  offScene.add(fillLight);

  offScene.add(new THREE.AmbientLight(0xffffff, 0.4)); // Slightly brighter ambient

  // Slight head rotation
  headMesh.rotation.y = Math.PI / 6; // More pronounced angle

  // Render to a texture
  const renderTarget = new THREE.WebGLRenderTarget(offWidth, offHeight);
  offRenderer.setRenderTarget(renderTarget);
  offRenderer.render(offScene, offCamera);

  // Get pixels
  const pixels = new Uint8Array(offWidth * offHeight * 4);
  offRenderer.readRenderTargetPixels(renderTarget, 0, 0, offWidth, offHeight, pixels);

  // Convert to canvas
  const canvas = document.createElement('canvas');
  canvas.width = offWidth;
  canvas.height = offHeight;
  const ctx = canvas.getContext('2d');
  const imageData = ctx.createImageData(offWidth, offHeight);
  imageData.data.set(pixels);

  // Flip image (WebGL coordinate system is inverted)
  flipImageDataVertically(imageData, offWidth, offHeight);
  ctx.putImageData(imageData, 0, 0);

  // Get data URL
  const dataURL = canvas.toDataURL('image/png');
  faceIconCache[power] = dataURL;

  // Cleanup
  offRenderer.dispose();
  renderTarget.dispose();

  return dataURL;
}

// Add a subtle idle animation for faces
function idleAnimation(img) {
  if (img.dataset.animating === 'true') return;

  img.dataset.animating = 'true';

  const animation = img.animate([
    { transform: 'rotate(0deg) scale(1)' },
    { transform: 'rotate(-2deg) scale(0.98)' },
    { transform: 'rotate(0deg) scale(1)' }
  ], {
    duration: 1500,
    easing: 'ease-in-out'
  });

  animation.onfinish = () => {
    img.dataset.animating = 'false';
  };
}

// Helper to flip image data vertically
function flipImageDataVertically(imageData, width, height) {
  const bytesPerRow = width * 4;
  const temp = new Uint8ClampedArray(bytesPerRow);
  for (let y = 0; y < height / 2; y++) {
    const topOffset = y * bytesPerRow;
    const bottomOffset = (height - y - 1) * bytesPerRow;
    temp.set(imageData.data.slice(topOffset, topOffset + bytesPerRow));
    imageData.data.set(imageData.data.slice(bottomOffset, bottomOffset + bytesPerRow), topOffset);
    imageData.data.set(temp, bottomOffset);
  }
}

// --- NEW: Function to play a random sound effect ---
function playRandomSoundEffect() {
  // List all the sound snippet filenames in assets/sounds
  const soundEffects = [
    'snippet_2.mp3',
    'snippet_3.mp3',
    'snippet_4.mp3',
    'snippet_9.mp3',
    'snippet_10.mp3',
    'snippet_11.mp3',
    'snippet_12.mp3',
    'snippet_13.mp3',
    'snippet_14.mp3',
    'snippet_15.mp3',
    'snippet_16.mp3',
    'snippet_17.mp3',
  ];
  // Pick one at random
  const chosen = soundEffects[Math.floor(Math.random() * soundEffects.length)];

  // Create an <audio> and play
  const audio = new Audio(`assets/sounds/${chosen}`);
  audio.play().catch(err => {
    // In case of browser auto-play restrictions, you may see warnings in console
    console.warn("Audio play was interrupted:", err);
  });
}

/**
 * Appends text to the scrolling news banner.
 * If the banner is at its default text or empty, replace it entirely.
 * Otherwise, just append " | " + newText.
 */
function addToNewsBanner(newText) {
  const bannerEl = document.getElementById('news-banner-content');
  if (!bannerEl) return;

  // If the banner only has the default text or is empty, replace it
  if (
    bannerEl.textContent.trim() === 'Diplomatic actions unfolding...' ||
    bannerEl.textContent.trim() === ''
  ) {
    bannerEl.textContent = newText;
  } else {
    // Otherwise append with a separator
    bannerEl.textContent += '  |  ' + newText;
  }
}

// New function to update info panel with useful information
function updateInfoPanel() {
  const totalPhases = gameData?.phases?.length || 0;
  const currentPhaseNumber = currentPhaseIndex + 1;
  const phaseName = gameData?.phases?.[currentPhaseIndex]?.name || 'Unknown';

  infoPanel.innerHTML = `
    <div><strong>Power:</strong> <span class="power-${currentPower.toLowerCase()}">${currentPower}</span></div>
    <div><strong>Current Phase:</strong> ${phaseName} (${currentPhaseNumber}/${totalPhases})</div>
    <hr/>
    <h4>All-Time Leaderboard</h4>
    <ul style="list-style:none;padding-left:0;margin:0;">
      <li>Austria: 0</li>
      <li>England: 0</li>
      <li>France: 0</li>
      <li>Germany: 0</li>
      <li>Italy: 0</li>
      <li>Russia: 0</li>
      <li>Turkey: 0</li>
    </ul>
  `;
}
