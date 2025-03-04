// ==============================================================================
// Copyright (C) 2023
//
//  This program is free software: you can redistribute it and/or modify it under
//  the terms of the GNU Affero General Public License as published by the Free
//  Software Foundation, either version 3 of the License, or (at your option) any
//  later version.
//
//  This program is distributed in the hope that it will be useful, but WITHOUT
//  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
//  FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
//  details.
//
//  You should have received a copy of the GNU Affero General Public License along
//  with this program.  If not, see <https://www.gnu.org/licenses/>.
// ==============================================================================

import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CoordinateMapper } from '../utils/CoordinateMapper.js';
import { UnitModels } from './UnitModels.js';
import { AnimationEffects } from './AnimationEffects.js';
import { OrderVisualizer } from './OrderVisualizer.js';

/**
 * Handles the 3D rendering for the animation system.
 * This class is responsible for setting up the Three.js environment,
 * rendering the map, and managing the game units and animations.
 */
export class MapRenderer {
  /**
   * Initialize the map renderer
   * @param {Object} options - Configuration options
   * @param {string} options.containerId - ID of the container element
   * @param {string} options.mapVariant - Map variant to use (standard, ancmed, etc.)
   * @param {CoordinateMapper} options.coordinateMapper - CoordinateMapper instance
   * @param {string} options.detailLevel - Detail level for unit models ('low', 'medium', 'high')
   * @param {boolean} options.debug - Whether to show debug elements
   */
  constructor(options) {
    this.containerId = options.containerId;
    this.container = document.getElementById(this.containerId);
    this.mapVariant = options.mapVariant || 'standard';
    this.coordinateMapper = options.coordinateMapper;
    this.detailLevel = options.detailLevel || 'medium';
    this.debug = options.debug || false;
    
    // Scene objects
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.lights = [];
    
    // Map and unit objects
    this.mapTexture = null;
    this.mapMesh = null;
    this.units = new Map();
    this.unitModels = null;
    
    // Animation related objects
    this.animationEffects = null;
    this.orderVisualizer = null;
    this.pendingAnimations = [];
    this.activeAnimations = [];
    
    // Animation settings
    this.animationSpeed = 1.0;
    this.easing = true;
    
    // Initialize everything
    this._init();
  }
  
  /**
   * Initialize the Three.js renderer
   * @private
   */
  _init() {
    // Create scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x87CEEB); // Sky blue background
    
    // Setup camera
    this.camera = new THREE.PerspectiveCamera(
      60, // Field of view
      this.container.clientWidth / this.container.clientHeight, // Aspect ratio
      1, // Near clipping plane
      5000 // Far clipping plane
    );
    this.camera.position.set(0, 500, 500);
    this.camera.lookAt(0, 0, 0);
    
    // Setup renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.shadowMap.enabled = true;
    this.container.appendChild(this.renderer.domElement);
    
    // Setup controls
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;
    this.controls.screenSpacePanning = false;
    this.controls.minDistance = 100;
    this.controls.maxDistance = 1500;
    this.controls.maxPolarAngle = Math.PI / 2;
    
    // Add a hemisphere light for ambient lighting
    const hemisphereLight = new THREE.HemisphereLight(0xFFFFFF, 0x202020, 1);
    this.scene.add(hemisphereLight);
    
    // Add a directional light for shadows and depth
    const directionalLight = new THREE.DirectionalLight(0xFFFFFF, 0.8);
    directionalLight.position.set(300, 400, 300);
    directionalLight.castShadow = true;
    directionalLight.shadow.mapSize.width = 2048;
    directionalLight.shadow.mapSize.height = 2048;
    directionalLight.shadow.camera.near = 100;
    directionalLight.shadow.camera.far = 1500;
    directionalLight.shadow.camera.left = -500;
    directionalLight.shadow.camera.right = 500;
    directionalLight.shadow.camera.top = 500;
    directionalLight.shadow.camera.bottom = -500;
    this.scene.add(directionalLight);
    this.lights.push(directionalLight);
    
    // Add a secondary directional light from the opposite direction
    const secondaryLight = new THREE.DirectionalLight(0xFFFFFF, 0.3);
    secondaryLight.position.set(-300, 200, -300);
    this.scene.add(secondaryLight);
    this.lights.push(secondaryLight);
    
    // Add ground grid for debugging
    if (this.debug) {
      const gridHelper = new THREE.GridHelper(1000, 20);
      this.scene.add(gridHelper);
      
      const axesHelper = new THREE.AxesHelper(500);
      this.scene.add(axesHelper);
    }
    
    // Initialize animation effects and order visualizer
    this.animationEffects = new AnimationEffects(this.scene);
    this.orderVisualizer = new OrderVisualizer(this.animationEffects, this.coordinateMapper);
    
    // Load map textures and models
    this._loadMapAssets();
    
    // Handle window resize
    window.addEventListener('resize', this._onWindowResize.bind(this));
    
    this.isInitialized = true;
  }
  
  /**
   * Load map textures and unit models
   * @private
   */
  _loadMapAssets() {
    // Load the map texture
    const textureLoader = new THREE.TextureLoader();
    const mapPath = `/diplomacy/animation/assets/maps/${this.mapVariant}_map.jpg`;
    
    textureLoader.load(
      mapPath,
      (texture) => {
        console.log(`[MapRenderer] Successfully loaded map texture: ${mapPath}`);
        this.mapTexture = texture;
        this._createMapMesh();
      },
      undefined, // Progress callback
      (error) => {
        console.warn(`[MapRenderer] Failed to load map texture: ${error.message}`);
        // If we failed to load the actual texture, create a placeholder
        this._createPlaceholderMap();
      }
    );
    
    // TODO: Load unit models in Phase 2
    // For now, we'll use simple shapes for units
    this.unitModels = new UnitModels({ detailLevel: this.detailLevel });
  }
  
  /**
   * Create placeholder map with a grid pattern
   * @private
   */
  _createPlaceholderMap() {
    console.log('[MapRenderer] Creating placeholder map');
    
    // Create a canvas for the placeholder texture
    const canvas = document.createElement('canvas');
    canvas.width = 2048;
    canvas.height = 2048;
    const ctx = canvas.getContext('2d');
    
    // Fill with base color for ocean
    ctx.fillStyle = '#8BAED8';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Get all province locations
    const allLocations = this.coordinateMapper.getAllLocations();
    
    // Draw provinces
    this._drawProvincesOnCanvas(ctx, allLocations, canvas.width, canvas.height);
    
    // Create a texture from the canvas
    this.mapTexture = new THREE.CanvasTexture(canvas);
    
    // Create the map mesh
    this._createMapMesh();
  }
  
  /**
   * Draw provinces on a canvas for the placeholder map
   * @param {CanvasRenderingContext2D} ctx - The canvas context
   * @param {string[]} locations - List of province locations
   * @param {number} width - Canvas width
   * @param {number} height - Canvas height
   * @private
   */
  _drawProvincesOnCanvas(ctx, locations, width, height) {
    // Track which provinces we've drawn
    const drawnProvinces = new Set();
    
    // First draw sea provinces (so land provinces appear on top)
    for (const location of locations) {
      const provinceInfo = this.coordinateMapper.getProvinceInfo(location);
      
      if (provinceInfo && provinceInfo.type === 'sea') {
        this._drawProvinceOnCanvas(ctx, location, width, height);
        drawnProvinces.add(location);
      }
    }
    
    // Then draw land provinces
    for (const location of locations) {
      if (!drawnProvinces.has(location)) {
        this._drawProvinceOnCanvas(ctx, location, width, height);
      }
    }
    
    // Draw borders between provinces
    this._drawProvinceBorders(ctx, locations, width, height);
    
    // Draw province labels
    this._drawProvinceLabels(ctx, locations, width, height);
  }
  
  /**
   * Draw a single province on the canvas
   * @param {CanvasRenderingContext2D} ctx - The canvas context
   * @param {string} location - Province location
   * @param {number} width - Canvas width
   * @param {number} height - Canvas height
   * @private 
   */
  _drawProvinceOnCanvas(ctx, location, width, height) {
    const pos = this.coordinateMapper.getPositionForLocation(location);
    const provinceInfo = this.coordinateMapper.getProvinceInfo(location);
    
    if (!pos || !provinceInfo) return;
    
    // Map 3D coordinates to 2D canvas
    // We're assuming the 3D map has coordinates from -500 to 500 in X and Z
    const x = (pos.x + 500) * (width / 1000);
    const y = (pos.z + 500) * (height / 1000);
    
    // Determine province color based on type
    const isSupplyCenter = provinceInfo.isSupplyCenter;
    const type = provinceInfo.type;
    
    // Set radius based on importance
    const radius = isSupplyCenter ? 45 : 40;
    
    // Draw province shape (circle for now, could be more complex shape in the future)
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    
    // Set province fill color
    if (type === 'sea') {
      ctx.fillStyle = '#4A87C5'; // Darker blue for sea
    } else {
      // Land provinces
      if (isSupplyCenter) {
        ctx.fillStyle = '#D4C499'; // Beige for supply centers
      } else {
        ctx.fillStyle = '#B8AA85'; // Tan for regular land
      }
    }
    
    ctx.fill();
    
    // Add a subtle highlight for supply centers
    if (isSupplyCenter) {
      ctx.beginPath();
      ctx.arc(x, y, radius - 10, 0, Math.PI * 2);
      ctx.fillStyle = type === 'sea' ? '#5899D9' : '#E7D6A9';
      ctx.fill();
    }
  }
  
  /**
   * Draw borders between provinces
   * @param {CanvasRenderingContext2D} ctx - The canvas context
   * @param {string[]} locations - List of province locations
   * @param {number} width - Canvas width
   * @param {number} height - Canvas height
   * @private
   */
  _drawProvinceBorders(ctx, locations, width, height) {
    // Draw connecting lines between adjacent provinces
    // For now, we'll use a simple approach and connect some known adjacent provinces
    
    // This is a simplified adjacency list for the standard map
    // In a full implementation, this would be loaded from a configuration file
    const adjacencyList = {
      // Western Europe
      'BRE': ['PAR', 'PIC', 'ENG', 'MAO', 'GAS'],
      'PAR': ['BRE', 'PIC', 'BUR', 'GAS'],
      'PIC': ['BRE', 'PAR', 'BUR', 'BEL', 'ENG'],
      'BEL': ['PIC', 'BUR', 'RUH', 'HOL', 'NTH', 'ENG'],
      'HOL': ['BEL', 'RUH', 'KIE', 'HEL', 'NTH'],
      
      // Great Britain
      'LON': ['YOR', 'WAL', 'ENG', 'NTH'],
      'YOR': ['LON', 'WAL', 'EDI', 'NTH'],
      'EDI': ['YOR', 'CLY', 'NTH', 'NWG'],
      'WAL': ['LON', 'YOR', 'IRI', 'ENG'],
      'CLY': ['EDI', 'NWG', 'NAO'],
      
      // Etc. for other regions
      // This is just a partial list for demonstration
    };
    
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 2;
    
    // Draw connections based on adjacency list
    for (const [province, adjacentProvinces] of Object.entries(adjacencyList)) {
      const pos1 = this.coordinateMapper.getPositionForLocation(province);
      if (!pos1) continue;
      
      const x1 = (pos1.x + 500) * (width / 1000);
      const y1 = (pos1.z + 500) * (height / 1000);
      
      for (const adjacentProvince of adjacentProvinces) {
        const pos2 = this.coordinateMapper.getPositionForLocation(adjacentProvince);
        if (!pos2) continue;
        
        const x2 = (pos2.x + 500) * (width / 1000);
        const y2 = (pos2.z + 500) * (height / 1000);
        
        // Draw line between provinces
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
    }
  }
  
  /**
   * Draw province labels on the canvas
   * @param {CanvasRenderingContext2D} ctx - The canvas context
   * @param {string[]} locations - List of province locations
   * @param {number} width - Canvas width
   * @param {number} height - Canvas height
   * @private
   */
  _drawProvinceLabels(ctx, locations, width, height) {
    // Draw province names
    ctx.font = '16px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    
    for (const location of locations) {
      const pos = this.coordinateMapper.getPositionForLocation(location);
      const provinceInfo = this.coordinateMapper.getProvinceInfo(location);
      
      if (!pos || !provinceInfo) continue;
      
      const x = (pos.x + 500) * (width / 1000);
      const y = (pos.z + 500) * (height / 1000);
      
      // Set text color based on province type
      ctx.fillStyle = provinceInfo.type === 'sea' ? '#FFFFFF' : '#000000';
      
      // Draw province name
      ctx.fillText(location, x, y);
    }
  }
  
  /**
   * Create the 3D mesh for the map
   * @private
   */
  _createMapMesh() {
    // Create a large plane for the map
    const geometry = new THREE.PlaneGeometry(1000, 1000);
    
    // Apply the map texture to a material
    const material = new THREE.MeshBasicMaterial({
      map: this.mapTexture,
      side: THREE.DoubleSide
    });
    
    // Create mesh and position it horizontally at y=0
    this.mapMesh = new THREE.Mesh(geometry, material);
    this.mapMesh.rotation.x = -Math.PI / 2; // Rotate to horizontal
    this.mapMesh.position.y = -1; // Slightly below units to prevent z-fighting
    
    // Add to scene
    this.scene.add(this.mapMesh);
    
    // After map is created, add supply center markers
    this._addSupplyCenterMarkers();
  }
  
  /**
   * Add visual markers for supply centers
   * @private
   */
  _addSupplyCenterMarkers() {
    // Get all province locations
    const allLocations = this.coordinateMapper.getAllLocations();
    
    // Create a marker for each supply center
    allLocations.forEach(location => {
      if (this.coordinateMapper.isSupplyCenter(location)) {
        const pos = this.coordinateMapper.getPositionForLocation(location);
        
        // Create a small cylinder as marker
        const geometry = new THREE.CylinderGeometry(5, 5, 2, 16);
        const material = new THREE.MeshBasicMaterial({ color: 0xffff00 });
        const marker = new THREE.Mesh(geometry, material);
        
        // Tag the marker so we can find it later
        marker.userData = { 
          type: 'supplyCenter',
          location: location
        };
        
        marker.position.set(pos.x, 1, pos.z); // Position at the supply center
        this.scene.add(marker);
      }
    });
  }
  
  /**
   * Handle window resize
   * @private
   */
  _onWindowResize() {
    if (!this.camera || !this.renderer) return;
    
    this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
  }
  
  /**
   * Start the render loop
   */
  startRendering() {
    if (!this.isInitialized) {
      console.warn('[MapRenderer] Cannot start rendering: not initialized');
      return;
    }
    
    this.isRendering = true;
    this.lastRenderTime = performance.now();
    this._renderLoop();
  }
  
  /**
   * Stop the render loop
   */
  stopRendering() {
    this.isRendering = false;
  }
  
  /**
   * The main render loop
   * @private
   */
  _renderLoop() {
    if (!this.isRendering) return;
    
    const now = performance.now();
    const deltaTime = (now - this.lastRenderTime) / 1000; // in seconds
    this.lastRenderTime = now;
    
    // Update controls
    this.controls.update();
    
    // Update animations
    this._updateAnimations(deltaTime);
    
    // Render the scene
    this.renderer.render(this.scene, this.camera);
    
    // Schedule the next frame
    requestAnimationFrame(() => this._renderLoop());
  }
  
  /**
   * Update animation states
   * @param {number} deltaTime - Time since last update in seconds
   * @private
   */
  _updateAnimations(deltaTime) {
    // Update animation effects
    if (this.animationEffects) {
      this.animationEffects.update(deltaTime);
    }
    
    // Update active unit animations
    this._updateUnitAnimations(deltaTime);
  }
  
  /**
   * Update unit animations
   * @param {number} deltaTime - Time since last update in seconds
   * @private
   */
  _updateUnitAnimations(deltaTime) {
    // Process active animations
    const completedAnimations = [];
    
    this.activeAnimations.forEach(animation => {
      // Update progress based on speed and deltaTime
      animation.progress += (deltaTime * this.animationSpeed) / animation.duration;
      
      // Cap progress at 1.0
      if (animation.progress > 1.0) {
        animation.progress = 1.0;
        completedAnimations.push(animation);
      }
      
      // Get the actual unit
      const unit = this.units.get(animation.unitId);
      if (!unit) return;
      
      // Calculate position along the path using easing
      let t = animation.progress;
      
      // Apply easing if enabled (cubic ease in/out)
      if (this.easing) {
        t = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      }
      
      // Get position along the path
      const pathPosition = this._getPositionAlongPath(animation.path, t);
      
      // For armies: add a small bounce effect
      let yOffset = 10; // Base height above the map
      if (unit.data.type === 'A') {
        yOffset += Math.sin(t * Math.PI) * 15; // Add bounce effect with sine wave
      }
      
      // Apply the position to the unit model
      unit.model.position.set(pathPosition.x, yOffset, pathPosition.z);
      
      // Update unit's internal position
      unit.position = { x: pathPosition.x, y: yOffset, z: pathPosition.z };
      
      // For fleets: rotate the model to face the movement direction
      if (unit.data.type === 'F' && t > 0 && t < 1) {
        // Calculate direction vector
        const nextT = Math.min(1, t + 0.05);
        const nextPos = this._getPositionAlongPath(animation.path, nextT);
        const dir = new THREE.Vector3(nextPos.x - pathPosition.x, 0, nextPos.z - pathPosition.z).normalize();
        
        // Calculate rotation
        const angle = Math.atan2(dir.x, dir.z);
        unit.model.rotation.y = angle;
      }
    });
    
    // Remove completed animations
    completedAnimations.forEach(animation => {
      const index = this.activeAnimations.indexOf(animation);
      if (index !== -1) {
        this.activeAnimations.splice(index, 1);
      }
      
      // Update unit location
      if (animation.onComplete) {
        animation.onComplete();
      }
      
      // Start next animation if queue is not empty
      this._startNextAnimation();
    });
  }
  
  /**
   * Start the next animation in the queue
   * @private
   */
  _startNextAnimation() {
    if (this.pendingAnimations.length > 0) {
      const nextAnimation = this.pendingAnimations.shift();
      this.activeAnimations.push(nextAnimation);
    }
  }
  
  /**
   * Get position along a path with given progress (0.0 - 1.0)
   * @param {Array<THREE.Vector3>} path - Array of path points
   * @param {number} t - Progress along the path (0.0 - 1.0)
   * @returns {THREE.Vector3} Position along the path
   * @private
   */
  _getPositionAlongPath(path, t) {
    // Handle edge cases
    if (t <= 0) return path[0];
    if (t >= 1) return path[path.length - 1];
    
    // Calculate the point index we're between
    const segmentCount = path.length - 1;
    const segmentIndex = Math.min(Math.floor(t * segmentCount), segmentCount - 1);
    
    // Calculate progress within this segment
    const segmentT = (t * segmentCount) - segmentIndex;
    
    // Get the two points we're between
    const p0 = path[segmentIndex];
    const p1 = path[segmentIndex + 1];
    
    // Interpolate between the points
    return new THREE.Vector3(
      p0.x + (p1.x - p0.x) * segmentT,
      p0.y + (p1.y - p0.y) * segmentT,
      p0.z + (p1.z - p0.z) * segmentT
    );
  }
  
  /**
   * Visualize an order on the map
   * @param {Object} orderData - The order data
   * @param {string} orderData.text - The order text
   * @param {string} orderData.power - The power giving the order
   * @param {boolean} orderData.success - Whether the order succeeded
   * @returns {Object} Visualization elements created
   */
  visualizeOrder(orderData) {
    if (!this.orderVisualizer) return null;
    return this.orderVisualizer.visualizeOrder(orderData);
  }
  
  /**
   * Clear all order visualizations
   */
  clearOrderVisualizations() {
    if (this.orderVisualizer) {
      this.orderVisualizer.clearAllVisualizations();
    }
  }
  
  /**
   * Remove a specific order visualization
   * @param {string} orderText - The order text to remove
   */
  removeOrderVisualization(orderText) {
    if (this.orderVisualizer) {
      this.orderVisualizer.removeVisualization(orderText);
    }
  }
  
  /**
   * Animate unit movement between provinces
   * @param {string} unitId - The unit ID
   * @param {string} fromLocation - Starting location
   * @param {string} toLocation - Destination location
   * @param {Object} options - Animation options
   * @param {number} options.duration - Animation duration in seconds (default: 1.5)
   * @param {number} options.arcHeight - Height of the arc for movement (default: 30)
   * @param {number} options.steps - Number of steps in the path (default: 10)
   * @param {boolean} options.queueAnimation - Whether to queue this animation (default: true)
   * @param {Function} options.onComplete - Callback when animation completes
   * @returns {boolean} Whether the animation was started or queued
   */
  animateUnitMovement(unitId, fromLocation, toLocation, options = {}) {
    // Get unit info
    const unit = this.units.get(unitId);
    if (!unit) {
      console.warn(`[MapRenderer] Cannot animate movement: unknown unit ${unitId}`);
      return false;
    }
    
    // Set option defaults
    const duration = options.duration || 1.5;
    const arcHeight = options.arcHeight || 30;
    const steps = options.steps || 10;
    const queueAnimation = options.queueAnimation !== false;
    
    // Get path between locations
    const path = this.coordinateMapper.getPathBetween(fromLocation, toLocation, steps, arcHeight);
    if (!path || path.length < 2) {
      console.warn(`[MapRenderer] Cannot animate movement: could not calculate path from ${fromLocation} to ${toLocation}`);
      return false;
    }
    
    // Create the animation object
    const animation = {
      unitId,
      fromLocation,
      toLocation,
      path,
      duration,
      progress: 0,
      onComplete: () => {
        // Update the unit's internal location when animation completes
        unit.data.location = toLocation;
        
        // Call the user-provided callback if any
        if (options.onComplete) {
          options.onComplete();
        }
      }
    };
    
    // Either start immediately or queue
    if (queueAnimation && this.activeAnimations.length > 0) {
      this.pendingAnimations.push(animation);
    } else {
      this.activeAnimations.push(animation);
    }
    
    return true;
  }
  
  /**
   * Set the animation speed multiplier
   * @param {number} speed - Speed multiplier (1.0 = normal)
   */
  setAnimationSpeed(speed) {
    this.animationSpeed = Math.max(0.1, Math.min(5.0, speed));
  }
  
  /**
   * Enable or disable animation easing
   * @param {boolean} enabled - Whether easing is enabled
   */
  setEasing(enabled) {
    this.easing = enabled;
  }
  
  /**
   * Pause all unit animations
   */
  pauseAnimations() {
    this.previousAnimationSpeed = this.animationSpeed;
    this.animationSpeed = 0;
  }
  
  /**
   * Resume all unit animations
   */
  resumeAnimations() {
    this.animationSpeed = this.previousAnimationSpeed || 1.0;
  }
  
  /**
   * Cancel all pending and active animations
   * @param {boolean} finishActive - Whether to finish active animations immediately
   */
  cancelAnimations(finishActive = false) {
    // Clear pending animations
    this.pendingAnimations = [];
    
    if (finishActive) {
      // Complete all active animations immediately
      this.activeAnimations.forEach(animation => {
        // Set progress to 1.0 to finish
        animation.progress = 1.0;
        
        // Update unit position to the end of the path
        const unit = this.units.get(animation.unitId);
        if (unit) {
          const finalPos = animation.path[animation.path.length - 1];
          unit.model.position.set(finalPos.x, 10, finalPos.z);
          unit.position = { x: finalPos.x, y: 10, z: finalPos.z };
          unit.data.location = animation.toLocation;
          
          // Call completion callback
          if (animation.onComplete) {
            animation.onComplete();
          }
        }
      });
      
      // Clear active animations
      this.activeAnimations = [];
    }
  }
  
  /**
   * Add a unit to the scene
   * @param {Object} unitData - The unit data
   * @param {string} unitData.id - Unique ID for the unit
   * @param {string} unitData.type - Unit type ('A' for army, 'F' for fleet)
   * @param {string} unitData.location - Unit location (e.g. "LON", "PAR")
   * @param {string} unitData.power - The power controlling the unit
   * @param {Object} [unitData.color] - Optional color override
   */
  addUnit(unitData) {
    // Skip if already exists
    if (this.units.has(unitData.id)) {
      console.warn(`[MapRenderer] Unit already exists: ${unitData.id}`);
      return;
    }
    
    // Get location coordinates
    const position = this.coordinateMapper.getPositionForLocation(unitData.location);
    if (!position) {
      console.warn(`[MapRenderer] Cannot add unit: unknown location ${unitData.location}`);
      return;
    }
    
    // Determine unit type and model
    const unitType = unitData.type === 'A' ? 'army' : 'fleet';
    const unitModel = this.unitModels.getUnitModel(unitType, unitData.power);
    
    // Determine unit color based on power
    const powerColors = {
      AUSTRIA: 0xBF1E2E,   // Red
      ENGLAND: 0x1B5EC0,   // Blue  
      FRANCE: 0x127BBF,    // Light Blue
      GERMANY: 0x454545,   // Gray/Black
      ITALY: 0x087E3B,     // Green
      RUSSIA: 0xFFFFFF,    // White
      TURKEY: 0xFFD700     // Yellow
    };
    
    // Use power color or default to gray
    const color = unitData.color || powerColors[unitData.power] || 0x888888;
    
    // Apply color to unit
    unitModel.traverse(child => {
      // Only apply to the main body, not to flags/sails which stay white
      if (child.isMesh && child !== unitModel.children[0]) {
        child.material = child.material.clone();
        child.material.color.setHex(color);
      }
    });
    
    // Position the unit
    unitModel.position.set(position.x, 10, position.z); // Higher above the map
    
    // Add to scene
    this.scene.add(unitModel);
    
    // Store reference to unit
    this.units.set(unitData.id, {
      data: unitData,
      model: unitModel,
      position: { ...position, y: 10 },
      animation: null
    });
  }
  
  /**
   * Remove a unit from the scene
   * @param {string} unitId - The unit ID
   */
  removeUnit(unitId) {
    const unit = this.units.get(unitId);
    if (!unit) return;
    
    // Remove from scene
    this.scene.remove(unit.model);
    
    // Remove from units map
    this.units.delete(unitId);
  }
  
  /**
   * Clear all units from the scene
   */
  clearUnits() {
    // Remove all units from the scene
    this.units.forEach(unit => {
      this.scene.remove(unit.model);
    });
    
    // Clear the units map
    this.units.clear();
  }
  
  /**
   * Update unit position
   * @param {string} unitId - The unit ID
   * @param {string} location - The new location
   */
  updateUnitPosition(unitId, location) {
    // Get the unit
    const unit = this.units.get(unitId);
    if (!unit) {
      console.warn(`[MapRenderer] Cannot update position: unknown unit ${unitId}`);
      return;
    }
    
    // Get new position
    const position = this.coordinateMapper.getPositionForLocation(location);
    if (!position) {
      console.warn(`[MapRenderer] Cannot update position: unknown location ${location}`);
      return;
    }
    
    // Update unit data
    unit.data.location = location;
    
    // Update position (without animation in Phase 1)
    unit.model.position.set(position.x, 10, position.z);
    unit.position = { ...position, y: 10 };
  }
  
  /**
   * Update the map variant and reload assets
   * @param {string} mapVariant - The new map variant
   * @returns {Promise<boolean>} A promise that resolves to true if the map was updated successfully
   */
  updateMapVariant(mapVariant) {
    if (this.mapVariant === mapVariant) {
      return Promise.resolve(true);
    }
    
    console.log(`[MapRenderer] Changing map variant from ${this.mapVariant} to ${mapVariant}`);
    
    // Validate map variant
    const validVariants = ['standard', 'ancmed', 'modern', 'pure'];
    if (!validVariants.includes(mapVariant)) {
      console.error(`[MapRenderer] Invalid map variant: ${mapVariant}`);
      return Promise.reject(new Error(`Invalid map variant: ${mapVariant}`));
    }
    
    return new Promise((resolve, reject) => {
      // Remove existing map mesh
      if (this.mapMesh) {
        this.scene.remove(this.mapMesh);
        this.mapMesh = null;
      }
      
      // Clean up existing supply center markers
      this._removeSupplyCenterMarkers();
      
      // Update map variant
      this.mapVariant = mapVariant;
      
      // Create new coordinate mapper
      this.coordinateMapper = new CoordinateMapper(this.mapVariant);
      
      // Reload map assets
      const textureLoader = new THREE.TextureLoader();
      const mapPath = `/diplomacy/animation/assets/maps/${this.mapVariant}_map.jpg`;
      
      textureLoader.load(
        mapPath,
        (texture) => {
          console.log(`[MapRenderer] Successfully loaded map texture: ${mapPath}`);
          this.mapTexture = texture;
          this._createMapMesh();
          
          // Clear units (they will need to be repositioned for the new map)
          this.clearUnits();
          
          resolve(true);
        },
        undefined, // Progress callback
        (error) => {
          console.warn(`[MapRenderer] Failed to load map texture: ${error.message}`);
          // If we failed to load the actual texture, create a placeholder
          this._createPlaceholderMap();
          
          // Clear units (they will need to be repositioned for the new map)
          this.clearUnits();
          
          resolve(true); // Still resolve as we created a placeholder
        }
      );
    });
  }
  
  /**
   * Remove supply center markers from the scene
   * @private
   */
  _removeSupplyCenterMarkers() {
    // Find and remove all supply center markers
    // We'll identify them by name
    const markersToRemove = [];
    
    this.scene.traverse(object => {
      if (object.userData && object.userData.type === 'supplyCenter') {
        markersToRemove.push(object);
      }
    });
    
    markersToRemove.forEach(marker => {
      this.scene.remove(marker);
    });
  }
  
  /**
   * Clean up resources
   */
  dispose() {
    this.stopRendering();
    
    // Remove event listeners
    window.removeEventListener('resize', this._onWindowResize);
    
    // Dispose of Three.js resources
    this.scene.traverse(object => {
      if (object.geometry) {
        object.geometry.dispose();
      }
      
      if (object.material) {
        if (Array.isArray(object.material)) {
          object.material.forEach(material => material.dispose());
        } else {
          object.material.dispose();
        }
      }
    });
    
    // Remove canvas from DOM
    if (this.renderer) {
      this.container.removeChild(this.renderer.domElement);
      this.renderer.dispose();
    }
    
    // Clear references
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.units.clear();
  }
} 