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

/**
 * Animation Player for Diplomacy game animation
 * This class connects the GameStateManager with the MapRenderer 
 * to provide a complete animation system.
 */

import { MapRenderer } from '../renderer/MapRenderer.js';
import { CoordinateMapper } from '../utils/CoordinateMapper.js';

export class AnimationPlayer {
  /**
   * Creates a new AnimationPlayer
   * @param {Object} options - Configuration options
   * @param {string} options.containerId - ID of the container element 
   * @param {GameStateManager} options.gameStateManager - Game state manager
   * @param {string} options.mapVariant - Map variant name (standard, ancmed, etc.)
   * @param {string} options.detailLevel - Detail level for unit models
   */
  constructor(options) {
    // Store options
    this.containerId = options.containerId;
    this.gameStateManager = options.gameStateManager;
    this.mapVariant = options.mapVariant || 'standard';
    this.detailLevel = options.detailLevel || 'medium';
    
    // Animation state
    this.isPlaying = false;
    this.playbackSpeed = 1.0;
    this.playbackInterval = null;
    this.phaseDisplayTime = 3000; // ms
    this.autoAdvance = true;
    
    // Feature flags
    this.animateUnitMovements = true;
    this.showOrderVisualizations = true;
    
    // Initialize the animation system
    this._initialize();
  }
  
  /**
   * Initialize the animation system
   * @private
   */
  _initialize() {
    console.log('Initializing animation player...');
    
    try {
      // Initialize the coordinate mapper
      this.coordinateMapper = new CoordinateMapper(this.mapVariant);
      
      // Initialize the map renderer
      this.mapRenderer = new MapRenderer({
        containerId: this.containerId,
        mapVariant: this.mapVariant,
        coordinateMapper: this.coordinateMapper,
        detailLevel: this.detailLevel
      });
      
      // Start rendering the map
      this.mapRenderer.startRendering();
      
      console.log('[AnimationPlayer] CoordinateMapper initialized successfully');
      
      // Setup game state manager listeners
      this.gameStateManager.addListener('phaseChanged', this._handlePhaseChange.bind(this));
      
      // Load the initial phase
      this._loadPhase(this.gameStateManager.getCurrentPhase());
      
      console.log('Animation player initialized successfully');
    } catch (error) {
      console.error('Error initializing animation player:', error);
    }
  }
  
  /**
   * Handle phase change event
   * @param {Object} phase - The new phase data
   * @private
   */
  _handlePhaseChange(phase) {
    this._loadPhase(phase);
  }
  
  /**
   * Load a phase into the renderer
   * @param {Object} phase - The phase data
   * @private
   */
  _loadPhase(phase) {
    if (!phase) {
      console.warn('[AnimationPlayer] Attempt to load undefined phase');
      return;
    }
    
    console.log(`[AnimationPlayer] Loading phase: ${phase.name || 'Unnamed'}`);
    
    try {
      // Clear the map state
      this.mapRenderer.clearUnits();
      this.mapRenderer.clearOrderVisualizations();
      
      // Load units
      if (phase.units && phase.units.length > 0) {
        // First pass: add all units to the map
        phase.units.forEach(unit => {
          try {
            // Generate ID if not present
            const unitId = unit.id || `${unit.power}_${unit.type}_${unit.location}`;
            
            this.mapRenderer.addUnit({
              id: unitId,
              type: unit.type,
              power: unit.power,
              location: unit.location
            });
          } catch (error) {
            console.warn(`[AnimationPlayer] Error adding unit:`, error);
          }
        });
      }
      
      // Visualize orders if enabled
      if (this.showOrderVisualizations && phase.orders && phase.orders.length > 0) {
        // Second pass: visualize orders
        phase.orders.forEach(order => {
          try {
            this.mapRenderer.visualizeOrder(order);
          } catch (error) {
            console.warn(`[AnimationPlayer] Error visualizing order:`, error);
          }
        });
      }
      
      // Trigger any events/callbacks for phase load
      const event = new CustomEvent('phaseLoaded', { detail: phase });
      document.getElementById(this.containerId).dispatchEvent(event);
      
    } catch (error) {
      console.error('[AnimationPlayer] Error loading phase:', error);
    }
  }
  
  /**
   * Start playback
   */
  play() {
    if (this.isPlaying) return;
    
    this.isPlaying = true;
    const advanceTime = this.phaseDisplayTime / this.playbackSpeed;
    
    // Set up interval for auto-advancing phases
    this.playbackInterval = setInterval(() => {
      const hasNext = this.gameStateManager.advancePhase();
      if (!hasNext && this.autoAdvance) {
        this.pause();
      }
    }, advanceTime);
  }
  
  /**
   * Pause playback
   */
  pause() {
    if (!this.isPlaying) return;
    
    this.isPlaying = false;
    clearInterval(this.playbackInterval);
  }
  
  /**
   * Go to the next phase
   */
  nextPhase() {
    this.gameStateManager.advancePhase();
  }
  
  /**
   * Go to the previous phase
   */
  previousPhase() {
    this.gameStateManager.previousPhase();
  }
  
  /**
   * Jump to a specific phase
   * @param {number} phaseIndex - Index of the phase to jump to
   */
  jumpToPhase(phaseIndex) {
    this.gameStateManager.jumpToPhase(phaseIndex);
  }
  
  /**
   * Set the playback speed
   * @param {number} speed - Playback speed multiplier (1.0 = normal)
   */
  setPlaybackSpeed(speed) {
    this.playbackSpeed = Math.max(0.1, Math.min(10.0, speed));
    
    // If currently playing, reset the interval with the new speed
    if (this.isPlaying) {
      this.pause();
      this.play();
    }
  }
  
  /**
   * Set whether animations use easing
   * @param {boolean} useEasing - Whether to use easing for animations
   */
  setEasing(useEasing) {
    if (this.mapRenderer) {
      this.mapRenderer.setEasing(useEasing);
    }
  }
  
  /**
   * Get the total number of phases
   * @returns {number} Total number of phases
   */
  getTotalPhases() {
    return this.gameStateManager.getPhaseCount();
  }
  
  /**
   * Get the current phase index
   * @returns {number} Current phase index
   */
  getCurrentPhaseIndex() {
    return this.gameStateManager.currentPhaseIndex;
  }
  
  /**
   * Get the current phase data
   * @returns {Object} Current phase data
   */
  getCurrentPhase() {
    return this.gameStateManager.getCurrentPhase();
  }
  
  /**
   * Set the camera position
   * @param {Object} position - Position as {x, y, z}
   */
  setCameraPosition(position) {
    if (this.mapRenderer && this.mapRenderer.camera) {
      this.mapRenderer.camera.position.set(position.x, position.y, position.z);
    }
  }
  
  /**
   * Reset the camera to the default position
   */
  resetCamera() {
    if (this.mapRenderer && this.mapRenderer.camera) {
      this.mapRenderer.camera.position.set(0, 500, 500);
      this.mapRenderer.camera.lookAt(0, 0, 0);
    }
  }
  
  /**
   * Clean up resources
   */
  dispose() {
    // Stop playback
    this.pause();
    
    // Dispose of renderer
    if (this.mapRenderer) {
      this.mapRenderer.dispose();
    }
    
    // Remove listeners
    if (this.gameStateManager) {
      this.gameStateManager.removeListener('phaseChanged', this._handlePhaseChange);
    }
  }
}