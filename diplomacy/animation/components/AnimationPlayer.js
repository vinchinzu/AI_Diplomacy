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

import { MapRenderer } from '../renderer/MapRenderer.js';
import { CoordinateMapper } from '../utils/CoordinateMapper.js';

/**
 * AnimationPlayer component that controls animation playback and integrates with Three.js renderer
 */
export class AnimationPlayer {
  /**
   * Initialize the animation player
   * @param {Object} options - Configuration options
   * @param {string} options.containerId - ID of the container element
   * @param {GameStateManager} options.gameStateManager - Game state manager instance
   * @param {string} options.mapVariant - Map variant to use (default: 'standard')
   * @param {string} options.detailLevel - Detail level for unit models (default: 'medium')
   */
  constructor(options) {
    // Store options
    this.containerId = options.containerId;
    this.container = document.getElementById(this.containerId);
    this.gameStateManager = options.gameStateManager;
    this.mapVariant = options.mapVariant || 'standard';
    this.detailLevel = options.detailLevel || 'medium';
    
    // Animation control state
    this.isPlaying = false;
    this.playbackSpeed = 1.0;
    this.currentPhaseIndex = 0;
    this.autoAdvance = true;
    
    // Animation timing (in seconds for easier integration with MapRenderer)
    this.movementDuration = 1.5;
    this.phasePauseDuration = 2.0;
    this.orderVisualizationDuration = 1.0;
    this.currentAnimationPromise = null;
    
    // Animation flags
    this.showOrderVisualizations = true;
    this.animateUnitMovements = true;
    this.useEasing = true;
    
    // DOM elements
    this.domElements = {
      mapContainer: null,
      controlsContainer: null,
      playButton: null,
      pauseButton: null,
      nextButton: null,
      prevButton: null,
      speedSelector: null,
      phaseDisplay: null,
      messageDisplay: null,
      settingsContainer: null
    };
    
    // Initialize components
    this._setupDOM();
    this._createControls();
    this._createSettingsPanel();
    this._initialize();
  }
  
  /**
   * Set up the DOM structure
   * @private
   */
  _setupDOM() {
    // Clear any existing content
    this.container.innerHTML = '';
    
    // Create map container
    this.domElements.mapContainer = document.createElement('div');
    this.domElements.mapContainer.id = `${this.containerId}-map`;
    this.domElements.mapContainer.className = 'animation-map-container';
    this.domElements.mapContainer.style.width = '100%';
    this.domElements.mapContainer.style.height = '500px';
    this.domElements.mapContainer.style.position = 'relative';
    this.container.appendChild(this.domElements.mapContainer);
    
    // Create main layout container
    const mainLayout = document.createElement('div');
    mainLayout.className = 'animation-main-layout';
    mainLayout.style.display = 'grid';
    mainLayout.style.gridTemplateColumns = '3fr 1fr';
    mainLayout.style.gap = '10px';
    mainLayout.style.marginTop = '10px';
    this.container.appendChild(mainLayout);
    
    // Create left column for controls and messages
    const leftColumn = document.createElement('div');
    leftColumn.className = 'animation-left-column';
    mainLayout.appendChild(leftColumn);
    
    // Create controls container
    this.domElements.controlsContainer = document.createElement('div');
    this.domElements.controlsContainer.className = 'animation-controls-container';
    this.domElements.controlsContainer.style.padding = '10px';
    this.domElements.controlsContainer.style.display = 'flex';
    this.domElements.controlsContainer.style.alignItems = 'center';
    this.domElements.controlsContainer.style.justifyContent = 'space-between';
    this.domElements.controlsContainer.style.backgroundColor = '#f5f5f5';
    this.domElements.controlsContainer.style.borderRadius = '4px';
    leftColumn.appendChild(this.domElements.controlsContainer);
    
    // Create message display area
    this.domElements.messageDisplay = document.createElement('div');
    this.domElements.messageDisplay.className = 'animation-message-display';
    this.domElements.messageDisplay.style.padding = '10px';
    this.domElements.messageDisplay.style.maxHeight = '300px';
    this.domElements.messageDisplay.style.overflowY = 'auto';
    this.domElements.messageDisplay.style.border = '1px solid #ccc';
    this.domElements.messageDisplay.style.marginTop = '10px';
    this.domElements.messageDisplay.style.backgroundColor = '#fff';
    leftColumn.appendChild(this.domElements.messageDisplay);
    
    // Create right column for settings
    const rightColumn = document.createElement('div');
    rightColumn.className = 'animation-right-column';
    mainLayout.appendChild(rightColumn);
    
    // Create settings container
    this.domElements.settingsContainer = document.createElement('div');
    this.domElements.settingsContainer.className = 'animation-settings-container';
    this.domElements.settingsContainer.style.padding = '10px';
    this.domElements.settingsContainer.style.border = '1px solid #ccc';
    this.domElements.settingsContainer.style.backgroundColor = '#f5f5f5';
    this.domElements.settingsContainer.style.borderRadius = '4px';
    rightColumn.appendChild(this.domElements.settingsContainer);
  }
  
  /**
   * Create the animation controls
   * @private
   */
  _createControls() {
    // Create playback controls
    const playbackControls = document.createElement('div');
    playbackControls.className = 'animation-playback-controls';
    playbackControls.style.display = 'flex';
    playbackControls.style.gap = '10px';
    this.domElements.controlsContainer.appendChild(playbackControls);
    
    // Create prev button
    this.domElements.prevButton = document.createElement('button');
    this.domElements.prevButton.textContent = '⏮ Prev';
    this.domElements.prevButton.onclick = () => this.prev();
    playbackControls.appendChild(this.domElements.prevButton);
    
    // Create play button
    this.domElements.playButton = document.createElement('button');
    this.domElements.playButton.textContent = '▶ Play';
    this.domElements.playButton.onclick = () => {
      if (this.isPlaying) {
        this.pause();
      } else {
        this.play();
      }
    };
    playbackControls.appendChild(this.domElements.playButton);
    
    // Create next button
    this.domElements.nextButton = document.createElement('button');
    this.domElements.nextButton.textContent = '⏭ Next';
    this.domElements.nextButton.onclick = () => this.next();
    playbackControls.appendChild(this.domElements.nextButton);
    
    // Create speed selector
    const speedControl = document.createElement('div');
    speedControl.style.display = 'flex';
    speedControl.style.alignItems = 'center';
    speedControl.style.gap = '5px';
    
    const speedLabel = document.createElement('label');
    speedLabel.textContent = 'Speed:';
    speedControl.appendChild(speedLabel);
    
    this.domElements.speedSelector = document.createElement('select');
    ['0.5', '1.0', '1.5', '2.0', '3.0'].forEach(speed => {
      const option = document.createElement('option');
      option.value = speed;
      option.textContent = `${speed}x`;
      if (speed === '1.0') option.selected = true;
      this.domElements.speedSelector.appendChild(option);
    });
    this.domElements.speedSelector.onchange = (e) => {
      this.setSpeed(parseFloat(e.target.value));
    };
    speedControl.appendChild(this.domElements.speedSelector);
    
    playbackControls.appendChild(speedControl);
    
    // Create phase display
    this.domElements.phaseDisplay = document.createElement('div');
    this.domElements.phaseDisplay.className = 'animation-phase-display';
    this.domElements.phaseDisplay.style.fontWeight = 'bold';
    this.domElements.controlsContainer.appendChild(this.domElements.phaseDisplay);
  }
  
  /**
   * Create settings panel with additional controls
   * @private
   */
  _createSettingsPanel() {
    const settingsTitle = document.createElement('h3');
    settingsTitle.textContent = 'Animation Settings';
    settingsTitle.style.margin = '0 0 10px 0';
    this.domElements.settingsContainer.appendChild(settingsTitle);
    
    // Create settings list
    const settingsList = document.createElement('ul');
    settingsList.style.listStyle = 'none';
    settingsList.style.padding = '0';
    settingsList.style.margin = '0';
    this.domElements.settingsContainer.appendChild(settingsList);
    
    // Helper function to create a setting item
    const createSettingItem = (label, input) => {
      const item = document.createElement('li');
      item.style.marginBottom = '10px';
      
      const labelElement = document.createElement('label');
      labelElement.textContent = label;
      labelElement.style.display = 'block';
      labelElement.style.marginBottom = '5px';
      
      item.appendChild(labelElement);
      item.appendChild(input);
      
      settingsList.appendChild(item);
    };
    
    // Order visualization setting
    const orderVisInput = document.createElement('input');
    orderVisInput.type = 'checkbox';
    orderVisInput.checked = this.showOrderVisualizations;
    orderVisInput.id = 'setting-order-vis';
    orderVisInput.onchange = (e) => {
      this.showOrderVisualizations = e.target.checked;
    };
    createSettingItem('Show Order Visualizations', orderVisInput);
    
    // Unit movement animation setting
    const unitAnimInput = document.createElement('input');
    unitAnimInput.type = 'checkbox';
    unitAnimInput.checked = this.animateUnitMovements;
    unitAnimInput.id = 'setting-unit-anim';
    unitAnimInput.onchange = (e) => {
      this.animateUnitMovements = e.target.checked;
      if (this.mapRenderer) {
        // Disable animations in renderer if needed
        if (!this.animateUnitMovements) {
          this.mapRenderer.cancelAnimations(true);
        }
      }
    };
    createSettingItem('Animate Unit Movements', unitAnimInput);
    
    // Easing setting
    const easingInput = document.createElement('input');
    easingInput.type = 'checkbox';
    easingInput.checked = this.useEasing;
    easingInput.id = 'setting-easing';
    easingInput.onchange = (e) => {
      this.useEasing = e.target.checked;
      if (this.mapRenderer) {
        this.mapRenderer.setEasing(this.useEasing);
      }
    };
    createSettingItem('Use Animation Easing', easingInput);
    
    // Auto-advance setting
    const autoAdvanceInput = document.createElement('input');
    autoAdvanceInput.type = 'checkbox';
    autoAdvanceInput.checked = this.autoAdvance;
    autoAdvanceInput.id = 'setting-auto-advance';
    autoAdvanceInput.onchange = (e) => {
      this.setAutoAdvance(e.target.checked);
    };
    createSettingItem('Auto-Advance to Next Phase', autoAdvanceInput);
  }
  
  /**
   * Initialize the animation player components
   * @private
   */
  _initialize() {
    // Create the CoordinateMapper with the selected map variant
    this.coordinateMapper = new CoordinateMapper(this.mapVariant);
    
    // Initialize the CoordinateMapper with built-in coordinates
    this.coordinateMapper.initialize()
      .then(() => {
        console.log('[AnimationPlayer] CoordinateMapper initialized successfully');
        
        // Create the MapRenderer with the selected map variant
        this.mapRenderer = new MapRenderer({
          containerId: this.domElements.mapContainer.id,
          mapVariant: this.mapVariant,
          coordinateMapper: this.coordinateMapper,
          detailLevel: this.detailLevel,
          debug: false
        });
        
        // Configure the renderer with our settings
        this.mapRenderer.setEasing(this.useEasing);
        this.mapRenderer.setAnimationSpeed(this.playbackSpeed);
        
        // Start the rendering loop
        this.mapRenderer.startRendering();
        
        // Display the initial phase
        this._displayPhase(this.currentPhaseIndex);
        
        // Add loading indicator
        const loadingIndicator = document.createElement('div');
        loadingIndicator.textContent = 'Animation Ready';
        loadingIndicator.style.position = 'absolute';
        loadingIndicator.style.top = '10px';
        loadingIndicator.style.right = '10px';
        loadingIndicator.style.backgroundColor = '#4CAF50';
        loadingIndicator.style.color = 'white';
        loadingIndicator.style.padding = '5px 10px';
        loadingIndicator.style.borderRadius = '4px';
        loadingIndicator.style.opacity = '1';
        loadingIndicator.style.transition = 'opacity 1s';
        this.domElements.mapContainer.appendChild(loadingIndicator);
        
        // Fade out loading indicator after 2 seconds
        setTimeout(() => {
          loadingIndicator.style.opacity = '0';
          setTimeout(() => loadingIndicator.remove(), 1000);
        }, 2000);
      })
      .catch(error => {
        console.error('[AnimationPlayer] Failed to initialize CoordinateMapper:', error);
        this.domElements.messageDisplay.innerHTML = `<p class="error">Error initializing animation: ${error.message}</p>`;
      });
  }
  
  /**
   * Display a specific game phase
   * @param {number} phaseIndex - Index of the phase to display
   * @private
   */
  _displayPhase(phaseIndex) {
    // Ensure phase index is valid
    if (phaseIndex < 0 || phaseIndex >= this.gameStateManager.getPhaseCount()) {
      console.error(`[AnimationPlayer] Invalid phase index: ${phaseIndex}`);
      return;
    }
    
    // Clear any existing order visualizations
    if (this.mapRenderer) {
      this.mapRenderer.clearOrderVisualizations();
    }
    
    // Update the current phase index
    this.currentPhaseIndex = phaseIndex;
    
    // Get the phase data
    const phase = this.gameStateManager.getPhase(phaseIndex);
    
    // Update the phase display
    if (this.domElements.phaseDisplay) {
      this.domElements.phaseDisplay.textContent = `${phase.year} ${phase.season} - ${phase.type}`;
    }
    
    // Display the units for this phase
    this._displayUnits(phase);
    
    // Display messages for this phase
    this._displayMessages(phase);
    
    // Visualize orders if available and enabled
    if (this.showOrderVisualizations && phase.orders && phase.orders.length > 0) {
      // Slight delay to allow units to be positioned first
      setTimeout(() => {
        this._visualizeOrders(phase);
      }, 100);
    }
  }
  
  /**
   * Display units for a specific phase
   * @param {Object} phase - Phase data
   * @private
   */
  _displayUnits(phase) {
    if (!this.mapRenderer) return;
    
    // Clear existing units
    this.mapRenderer.clearUnits();
    
    // Add units for this phase
    if (phase.units && phase.units.length > 0) {
      phase.units.forEach(unit => {
        const unitData = {
          id: `${unit.type}_${unit.power}_${unit.location}`,
          type: unit.type,
          power: unit.power,
          location: unit.location
        };
        
        this.mapRenderer.addUnit(unitData);
      });
    }
  }
  
  /**
   * Visualize orders for a specific phase
   * @param {Object} phase - Phase data
   * @private
   */
  _visualizeOrders(phase) {
    if (!this.mapRenderer || !phase.orders) return;
    
    // Visualize each order
    phase.orders.forEach(order => {
      if (!order.text) return;
      
      // Determine if order was successful
      let success = true;
      if (phase.results && phase.results.length > 0) {
        // Find corresponding result for this order
        const result = phase.results.find(result => 
          result.power === order.power && 
          result.region === order.region
        );
        
        if (result) {
          success = result.success !== false;
        }
      }
      
      // Create order data object
      const orderData = {
        text: order.text,
        power: order.power,
        success: success
      };
      
      // Visualize the order
      this.mapRenderer.visualizeOrder(orderData);
    });
  }
  
  /**
   * Display messages for a specific phase
   * @param {Object} phase - Phase data
   * @private
   */
  _displayMessages(phase) {
    if (!this.domElements.messageDisplay) return;
    
    // Clear previous messages
    this.domElements.messageDisplay.innerHTML = '';
    
    // Add phase title
    const phaseTitle = document.createElement('h3');
    phaseTitle.textContent = `${phase.year} ${phase.season} - ${phase.type}`;
    phaseTitle.style.margin = '0 0 10px 0';
    phaseTitle.style.borderBottom = '1px solid #ddd';
    phaseTitle.style.paddingBottom = '5px';
    this.domElements.messageDisplay.appendChild(phaseTitle);
    
    // Add orders section if available
    if (phase.orders && phase.orders.length > 0) {
      const ordersTitle = document.createElement('h4');
      ordersTitle.textContent = 'Orders';
      ordersTitle.style.margin = '10px 0 5px 0';
      this.domElements.messageDisplay.appendChild(ordersTitle);
      
      const ordersList = document.createElement('ul');
      ordersList.style.listStyleType = 'none';
      ordersList.style.padding = '0';
      ordersList.style.margin = '0';
      
      // Group orders by power
      const ordersByPower = {};
      phase.orders.forEach(order => {
        if (!ordersByPower[order.power]) {
          ordersByPower[order.power] = [];
        }
        ordersByPower[order.power].push(order);
      });
      
      // Add orders grouped by power
      Object.keys(ordersByPower).sort().forEach(power => {
        const powerItem = document.createElement('li');
        powerItem.style.marginBottom = '8px';
        
        const powerHeader = document.createElement('div');
        powerHeader.textContent = power;
        powerHeader.style.fontWeight = 'bold';
        powerHeader.style.color = '#333';
        powerItem.appendChild(powerHeader);
        
        const powerOrders = document.createElement('ul');
        powerOrders.style.listStyleType = 'none';
        powerOrders.style.padding = '0 0 0 15px';
        powerOrders.style.margin = '3px 0 0 0';
        
        ordersByPower[power].forEach(order => {
          const orderItem = document.createElement('li');
          orderItem.textContent = order.text;
          orderItem.style.fontSize = '0.9em';
          orderItem.style.padding = '2px 0';
          powerOrders.appendChild(orderItem);
        });
        
        powerItem.appendChild(powerOrders);
        ordersList.appendChild(powerItem);
      });
      
      this.domElements.messageDisplay.appendChild(ordersList);
    }
    
    // Add results section if available
    if (phase.results && phase.results.length > 0) {
      const resultsTitle = document.createElement('h4');
      resultsTitle.textContent = 'Results';
      resultsTitle.style.margin = '15px 0 5px 0';
      this.domElements.messageDisplay.appendChild(resultsTitle);
      
      const resultsList = document.createElement('ul');
      resultsList.style.listStyleType = 'none';
      resultsList.style.padding = '0';
      resultsList.style.margin = '0';
      
      phase.results.forEach(result => {
        if (!result.text) return;
        
        const resultItem = document.createElement('li');
        resultItem.style.padding = '3px 0';
        resultItem.style.fontSize = '0.9em';
        resultItem.style.color = result.success === false ? '#d32f2f' : '#333';
        resultItem.textContent = result.text;
        resultsList.appendChild(resultItem);
      });
      
      this.domElements.messageDisplay.appendChild(resultsList);
    }
    
    // Add placeholder if no messages
    if ((!phase.orders || phase.orders.length === 0) && 
        (!phase.results || phase.results.length === 0)) {
      const noMessages = document.createElement('p');
      noMessages.textContent = 'No messages for this phase';
      noMessages.style.color = '#666';
      noMessages.style.fontStyle = 'italic';
      this.domElements.messageDisplay.appendChild(noMessages);
    }
  }
  
  /**
   * Animate a transition from one phase to the next
   * @param {number} fromPhaseIndex - Starting phase index
   * @param {number} toPhaseIndex - Target phase index
   * @returns {Promise} Promise that resolves when animation completes
   * @private
   */
  _animatePhaseTransition(fromPhaseIndex, toPhaseIndex) {
    if (!this.mapRenderer) {
      return Promise.resolve();
    }
    
    // Cancel any existing animation
    if (this.currentAnimationPromise) {
      this.mapRenderer.cancelAnimations(false);
    }
    
    return new Promise((resolve, reject) => {
      try {
        // Get phase data
        const fromPhase = this.gameStateManager.getPhase(fromPhaseIndex);
        const toPhase = this.gameStateManager.getPhase(toPhaseIndex);
        
        // Validate phases
        if (!fromPhase || !toPhase) {
          console.error('[AnimationPlayer] Invalid phase data for transition');
          this._displayPhase(toPhaseIndex);
          resolve();
          return;
        }
        
        // Create a map of current unit positions by ID
        const currentUnits = new Map();
        if (fromPhase.units && fromPhase.units.length > 0) {
          fromPhase.units.forEach(unit => {
            const unitId = `${unit.type}_${unit.power}_${unit.location}`;
            currentUnits.set(unitId, {
              id: unitId,
              type: unit.type,
              power: unit.power,
              location: unit.location
            });
          });
        }
        
        // Create a map of target unit positions by ID
        const targetUnits = new Map();
        if (toPhase.units && toPhase.units.length > 0) {
          toPhase.units.forEach(unit => {
            // Determine the likely previous location
            let fromLocation = unit.fromLocation || unit.location;
            let previousId = `${unit.type}_${unit.power}_${fromLocation}`;
            
            // If this was a dislodged unit, update the ID
            if (unit.dislodged) {
              previousId = `${unit.type}_${unit.power}_${unit.location}`;
            }
            
            targetUnits.set(previousId, {
              id: `${unit.type}_${unit.power}_${unit.location}`,
              type: unit.type,
              power: unit.power,
              location: unit.location,
              fromLocation: fromLocation,
              dislodged: unit.dislodged
            });
          });
        }
        
        // Clear any existing order visualizations
        this.mapRenderer.clearOrderVisualizations();
        
        // Calculate units that need to move, be added, or be removed
        const unitsToMove = [];
        const unitsToAdd = [];
        const unitsToRemove = [];
        
        // Find units to move or remove
        currentUnits.forEach((unit, unitId) => {
          const targetUnit = targetUnits.get(unitId);
          
          if (targetUnit) {
            // Unit exists in both phases, check if moved
            if (unit.location !== targetUnit.location) {
              // Unit moved
              unitsToMove.push({
                unitId: unitId,
                fromLocation: unit.location,
                toLocation: targetUnit.location,
                type: unit.type,
                power: unit.power
              });
            }
          } else {
            // Unit no longer exists, remove it
            unitsToRemove.push(unitId);
          }
        });
        
        // Find units to add (new units)
        targetUnits.forEach((unit, unitId) => {
          if (!currentUnits.has(unitId)) {
            // If this is not an id we already track, it might be a new unit
            // But we need to check if it's actually moved from somewhere else
            let existingUnit = false;
            
            // Check if this is a new unit ID for an existing unit that moved
            for (const [curId, curUnit] of currentUnits.entries()) {
              if (curUnit.type === unit.type && 
                  curUnit.power === unit.power && 
                  !targetUnits.has(curId)) {
                // This is an existing unit with a new ID
                unitsToMove.push({
                  unitId: curId,
                  newUnitId: unit.id,
                  fromLocation: curUnit.location,
                  toLocation: unit.location,
                  type: unit.type,
                  power: unit.power
                });
                existingUnit = true;
                break;
              }
            }
            
            if (!existingUnit) {
              // New unit, add it
              unitsToAdd.push({
                id: unit.id,
                type: unit.type,
                power: unit.power,
                location: unit.location
              });
            }
          }
        });
        
        // If no movement, just display the new phase
        if (unitsToMove.length === 0 && unitsToAdd.length === 0 && unitsToRemove.length === 0) {
          this._displayPhase(toPhaseIndex);
          resolve();
          return;
        }
        
        // First, remove units that no longer exist
        unitsToRemove.forEach(unitId => {
          this.mapRenderer.removeUnit(unitId);
        });
        
        // Then, add new units
        unitsToAdd.forEach(unit => {
          this.mapRenderer.addUnit(unit);
        });
        
        // Finally, animate unit movements
        if (unitsToMove.length === 0 || !this.animateUnitMovements) {
          // If no units to move or animations disabled, just display the new phase
          this._displayPhase(toPhaseIndex);
          resolve();
        } else {
          // Track movement animations
          let movementsComplete = 0;
          
          // Start all movement animations
          unitsToMove.forEach(movement => {
            const options = {
              duration: this.movementDuration,
              arcHeight: 30,
              steps: 15,
              queueAnimation: false,
              onComplete: () => {
                // If unit has a new ID in the target phase, update it
                if (movement.newUnitId && movement.newUnitId !== movement.unitId) {
                  // Remove old unit
                  this.mapRenderer.removeUnit(movement.unitId);
                  
                  // Add new unit
                  this.mapRenderer.addUnit({
                    id: movement.newUnitId,
                    type: movement.type,
                    power: movement.power,
                    location: movement.toLocation
                  });
                }
                
                movementsComplete++;
                
                // When all movements complete, resolve the promise
                if (movementsComplete === unitsToMove.length) {
                  this._displayPhase(toPhaseIndex);
                  resolve();
                }
              }
            };
            
            this.mapRenderer.animateUnitMovement(
              movement.unitId, 
              movement.fromLocation, 
              movement.toLocation, 
              options
            );
          });
        }
      } catch (error) {
        console.error('[AnimationPlayer] Error animating phase transition:', error);
        // In case of error, still show the target phase
        this._displayPhase(toPhaseIndex);
        reject(error);
      }
    });
  }
  
  /**
   * Play the animation from the current phase
   */
  play() {
    if (this.isPlaying) return;
    
    this.isPlaying = true;
    this.domElements.playButton.textContent = '⏸ Pause';
    
    // Update renderer animation speed
    if (this.mapRenderer) {
      this.mapRenderer.resumeAnimations();
    }
    
    const playNextPhase = () => {
      if (!this.isPlaying) return;
      
      const nextPhaseIndex = this.currentPhaseIndex + 1;
      
      if (nextPhaseIndex >= this.gameStateManager.getPhaseCount()) {
        // End of animation reached, stop playing
        this.pause();
        return;
      }
      
      // Animate transition to next phase
      this._animatePhaseTransition(this.currentPhaseIndex, nextPhaseIndex)
        .then(() => {
          // Pause between phases
          setTimeout(() => {
            if (this.isPlaying && this.autoAdvance) {
              playNextPhase();
            }
          }, this.phasePauseDuration * 1000 / this.playbackSpeed);
        })
        .catch(error => {
          console.error('[AnimationPlayer] Error playing animation:', error);
          this.pause();
        });
    };
    
    // Start playing
    playNextPhase();
  }
  
  /**
   * Pause the animation
   */
  pause() {
    this.isPlaying = false;
    this.domElements.playButton.textContent = '▶ Play';
    
    // Pause renderer animations
    if (this.mapRenderer) {
      this.mapRenderer.pauseAnimations();
    }
  }
  
  /**
   * Go to the next phase
   */
  next() {
    const nextPhaseIndex = this.currentPhaseIndex + 1;
    
    if (nextPhaseIndex >= this.gameStateManager.getPhaseCount()) {
      console.log('[AnimationPlayer] Reached the end of the animation');
      return;
    }
    
    // Pause any current playback
    const wasPlaying = this.isPlaying;
    this.pause();
    
    // Animate transition to next phase
    this._animatePhaseTransition(this.currentPhaseIndex, nextPhaseIndex)
      .then(() => {
        // Resume playback if it was playing before
        if (wasPlaying) {
          setTimeout(() => {
            this.play();
          }, this.phasePauseDuration * 1000 / this.playbackSpeed);
        }
      })
      .catch(error => {
        console.error('[AnimationPlayer] Error going to next phase:', error);
      });
  }
  
  /**
   * Go to the previous phase
   */
  prev() {
    const prevPhaseIndex = this.currentPhaseIndex - 1;
    
    if (prevPhaseIndex < 0) {
      console.log('[AnimationPlayer] Already at the beginning of the animation');
      return;
    }
    
    // Pause any current playback
    const wasPlaying = this.isPlaying;
    this.pause();
    
    // Just display the previous phase without animation
    this._displayPhase(prevPhaseIndex);
    
    // Resume playback if it was playing before
    if (wasPlaying) {
      setTimeout(() => {
        this.play();
      }, 500);
    }
  }
  
  /**
   * Set the playback speed
   * @param {number} speed - Playback speed multiplier
   */
  setSpeed(speed) {
    this.playbackSpeed = parseFloat(speed);
    console.log(`[AnimationPlayer] Playback speed set to ${this.playbackSpeed}x`);
    
    // Update renderer animation speed
    if (this.mapRenderer) {
      this.mapRenderer.setAnimationSpeed(this.playbackSpeed);
    }
  }
  
  /**
   * Set whether to automatically advance to the next phase
   * @param {boolean} autoAdvance - Whether to automatically advance
   */
  setAutoAdvance(autoAdvance) {
    this.autoAdvance = autoAdvance;
    console.log(`[AnimationPlayer] Auto-advance ${autoAdvance ? 'enabled' : 'disabled'}`);
  }
} 