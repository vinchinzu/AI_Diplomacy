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
 * Game State Manager for the animation system.
 * Handles the game state, phases, and transitions between states.
 */

/**
 * Manages the game state for animation playback purposes
 */
export class GameStateManager {
  /**
   * Creates a new GameStateManager
   * @param {Object} [gameData] - The loaded game data (optional, can be loaded later with loadGameState)
   */
  constructor(gameData) {
    this.currentPhaseIndex = 0;
    this.listeners = [];
    this.phases = [];
    
    // If gameData is provided, initialize with it
    if (gameData) {
      this.loadGameState(gameData);
    } else {
      this.gameData = null;
      this.mapName = 'standard';
      this.gameId = 'unknown';
      console.log('[GameStateManager] Initialized without game data. Call loadGameState() to load data.');
    }
  }

  /**
   * Load game state data
   * @param {Object} gameData - The game state data to load
   * @returns {Promise} - Resolves when the game state is loaded
   */
  async loadGameState(gameData) {
    console.log('[GameStateManager] loadGameState called', gameData ? 'with data' : 'without data');
    
    if (!gameData) {
      console.error('[GameStateManager] No game data provided');
      throw new Error('Game data is required');
    }
    
    this.gameData = gameData;
    
    // Extract key information
    this.mapName = gameData.map_name || gameData.mapName || 'standard';
    this.gameId = gameData.game_id || gameData.id || 'unknown';
    
    // Format phase data for easier access
    this.phases = this._formatPhases(gameData);
    this.currentPhaseIndex = 0;
    
    console.log(`[GameStateManager] Loaded ${this.phases.length} phases for game ${this.gameId}`);
    
    console.log('[GameStateManager] Checking if notifyListeners methods exist:', {
      _notifyListeners: typeof this._notifyListeners === 'function',
      notifyListeners: typeof this.notifyListeners === 'function'
    });
    
    // Use the correct method to notify listeners
    try {
      // First try using the public method
      if (typeof this.notifyListeners === 'function') {
        console.log('[GameStateManager] Using public notifyListeners');
        this.notifyListeners('gameStateLoaded', this.gameData);
      } 
      // Fallback to private method
      else if (typeof this._notifyListeners === 'function') {
        console.log('[GameStateManager] Using private _notifyListeners');
        this._notifyListeners('gameStateLoaded', this.gameData);
      } 
      // If neither exists, log an error
      else {
        console.error('[GameStateManager] No notification method available');
      }
    } catch (error) {
      console.error('[GameStateManager] Error notifying listeners:', error);
    }
    
    return this.gameData;
  }

  /**
   * Load a game file from disk
   * @param {Event} event - File input event
   * @returns {Promise} Promise that resolves when the file is loaded
   */
  loadGameFromDisk() {
    return new Promise((resolve, reject) => {
      console.log('[GameStateManager] Preparing to load game from disk');
      
      // Create a file input element
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.json,.lmvsgame';
      
      // Handle file selection
      input.onchange = (event) => {
        const file = event.target.files[0];
        if (!file) {
          reject(new Error('No file selected'));
          return;
        }
        
        console.log(`[GameStateManager] Selected file: ${file.name}`);
        
        const reader = new FileReader();
        
        reader.onload = () => {
          try {
            const data = JSON.parse(reader.result);
            console.log('[GameStateManager] Successfully parsed game file');
            
            // Detect if this is a results file or a standard game file
            if (data.rounds && Array.isArray(data.rounds)) {
              // This appears to be a results file, convert it
              console.log('[GameStateManager] Detected results file format, converting...');
              const convertedData = this.processResultsFile(data);
              this.loadGameState(convertedData)
                .then(resolve)
                .catch(reject);
            } else {
              // Standard game file format
              this.loadGameState(data)
                .then(resolve)
                .catch(reject);
            }
          } catch (error) {
            console.error('[GameStateManager] Error parsing game file:', error);
            reject(new Error(`Failed to parse game file: ${error.message}`));
          }
        };
        
        reader.onerror = () => {
          reject(new Error('Error reading file'));
        };
        
        reader.readAsText(file);
      };
      
      // Trigger file selection dialog
      input.click();
    });
  }

  /**
   * Process and convert results-file format to animation format
   * This method takes the output format from the AI Diplomacy results and 
   * converts it to the format needed by the animation system
   * @param {Object} resultsData - Results data from AI Diplomacy
   * @returns {Object} Formatted game data compatible with the animation system
   */
  processResultsFile(resultsData) {
    // Create a base game data structure
    const gameData = {
      map_name: "standard",
      game_id: resultsData.game_id || "ai-diplomacy-game",
      phases: []
    };
    
    try {
      // Extract phases from the results data
      // Typical format includes rounds with states, orders, etc.
      if (resultsData.rounds && Array.isArray(resultsData.rounds)) {
        console.log(`[GameStateManager] Processing ${resultsData.rounds.length} rounds from results file`);
        
        // Convert each round to a phase
        gameData.phases = resultsData.rounds.map((round, index) => {
          // Extract phase info
          const phase = {
            name: round.name || `Round ${index + 1}`,
            year: round.year || 1900 + Math.floor(index / 3),
            season: round.season || (index % 3 === 0 ? "SPRING" : (index % 3 === 1 ? "FALL" : "WINTER")),
            type: round.type || (index % 3 === 2 ? "ADJUSTMENT" : "MOVEMENT"),
            units: [],
            orders: [],
            results: [],
            messages: round.messages || [],
            index: index
          };
          
          // Extract unit positions
          if (round.state && round.state.units) {
            // Convert units to expected format
            for (const [power, units] of Object.entries(round.state.units)) {
              if (Array.isArray(units)) {
                units.forEach(unit => {
                  // Parse unit info (e.g., "A PAR" or "F BRE")
                  const match = unit.match(/^([AF])\s+(.+)$/);
                  if (match) {
                    const unitType = match[1]; // 'A' or 'F'
                    const location = match[2];
                    
                    // Create a unique ID for the unit
                    const unitId = `${power.toUpperCase()}_${unitType}_${location}_${index}`;
                    
                    phase.units.push({
                      id: unitId,
                      type: unitType,
                      power: power.toUpperCase(),
                      location: location
                    });
                  }
                });
              }
            }
          }
          
          // Extract orders
          if (round.orders) {
            for (const [power, orders] of Object.entries(round.orders)) {
              if (Array.isArray(orders)) {
                orders.forEach(order => {
                  // Extract the region from the order (e.g., "A PAR-BUR" -> "PAR")
                  const regionMatch = order.match(/^[AF]\s+([A-Za-z_]+)/);
                  const region = regionMatch ? regionMatch[1] : "";
                  
                  // Check if the order format needs to be standardized
                  let standardizedOrder = order;
                  // Ensure there are spaces between order components (e.g., A PAR-BUR, not A PAR - BUR)
                  standardizedOrder = standardizedOrder
                    .replace(/([A-Z]{3})\s*-\s*([A-Z]{3})/g, '$1-$2')
                    .replace(/([A-Z]{3})\s*H/g, '$1 H')
                    .replace(/([A-Z]{3})\s*S\s*([AF])\s*([A-Z]{3})/g, '$1 S $2 $3');
                  
                  phase.orders.push({
                    text: standardizedOrder,
                    power: power.toUpperCase(),
                    region: region,
                    success: true // Default to true unless specified otherwise
                  });
                });
              }
            }
          }
          
          return phase;
        });
      }
      
      console.log(`[GameStateManager] Processed ${gameData.phases.length} phases from results file`);
      return gameData;
    } catch (error) {
      console.error(`[GameStateManager] Error processing results file: ${error.message}`);
      console.error(error);
      throw new Error(`Failed to process results file: ${error.message}`);
    }
  }

  /**
   * Format game data into a consistent phase format for animation
   * @param {Object} gameData - The game data to format
   * @returns {Array} Array of formatted phases
   * @private
   */
  _formatPhases(gameData) {
    const phases = [];
    
    try {
      console.log('[GameStateManager] Formatting phases');
      
      // If gameData contains a 'phases' array, we can use it directly
      if (Array.isArray(gameData.phases)) {
        console.log(`[GameStateManager] Found ${gameData.phases.length} phases in game data`);
        
        // Map directly from phases array
        return gameData.phases.map((phase, index) => {
          // Ensure phase has a name
          if (!phase.name) {
            if (phase.state && phase.state.name) {
              phase.name = phase.state.name;
            } else {
              phase.name = `Phase ${index + 1}`;
            }
          }
          
          // Copy properties from phase object or from its state object
          return {
            name: phase.name,
            year: phase.year || (phase.state ? phase.state.year : null) || '?',
            season: phase.season || (phase.state ? phase.state.season : null) || '?',
            type: phase.type || (phase.state ? phase.state.type : null) || '?',
            units: phase.units || (phase.state ? phase.state.units : null) || [],
            centers: phase.centers || (phase.state ? phase.state.centers : null) || {},
            orders: phase.orders || [],
            results: phase.results || [],
            messages: phase.messages || [],
            summary: phase.summary || null,
            index: index
          };
        });
      }
      
      // For backward compatibility with older formats
      // (Add any other format conversions as needed)
      console.log('[GameStateManager] No phases array found, checking for state_history');
      
      // Fallback for older formats that use state_history
      if (gameData.state_history) {
        const stateHistory = gameData.state_history;
        const orderHistory = gameData.order_history || {};
        const resultHistory = gameData.result_history || {};
        const messageHistory = gameData.message_history || {};
        
        console.log(`[GameStateManager] Found ${Object.keys(stateHistory).length} phases in state_history`);
        
        // Convert to array of phases
        Object.entries(stateHistory).forEach(([phaseName, state], index) => {
          phases.push({
            name: phaseName,
            year: state.year || '?',
            season: state.season || '?',
            type: state.type || '?',
            units: state.units || [],
            centers: state.centers || {},
            orders: orderHistory[phaseName] ? Object.values(orderHistory[phaseName]) : [],
            results: resultHistory[phaseName] ? Object.values(resultHistory[phaseName]) : [],
            messages: messageHistory[phaseName] ? Object.values(messageHistory[phaseName]) : [],
            summary: gameData.phase_summaries && gameData.phase_summaries[phaseName] ? 
                    gameData.phase_summaries[phaseName] : null,
            index: index
          });
        });
        
        // Sort phases by year, season, and type
        phases.sort((a, b) => {
          if (a.year !== b.year) return a.year - b.year;
          if (a.season !== b.season) {
            const seasons = ['SPRING', 'SUMMER', 'FALL', 'AUTUMN', 'WINTER'];
            return seasons.indexOf(a.season) - seasons.indexOf(b.season);
          }
          const types = ['MOVEMENT', 'RETREAT', 'ADJUSTMENT', 'BUILD'];
          return types.indexOf(a.type) - types.indexOf(b.type);
        });
        
        console.log(`[GameStateManager] Formatted ${phases.length} phases from state_history`);
        return phases;
      }
      
      console.warn('[GameStateManager] Could not find phase data in the expected format');
      return [];
    } catch (error) {
      console.error(`[GameStateManager] Error formatting phases: ${error.message}`);
      return [];
    }
  }

  /**
   * Get the current phase
   * @returns {Object} The current phase
   */
  getCurrentPhase() {
    return this.phases[this.currentPhaseIndex];
  }

  /**
   * Get the next phase
   * @returns {Object|null} The next phase or null if at the end
   */
  getNextPhase() {
    if (this.currentPhaseIndex < this.phases.length - 1) {
      return this.phases[this.currentPhaseIndex + 1];
    }
    return null;
  }

  /**
   * Advance to the next phase
   * @returns {boolean} Whether the advance was successful
   */
  advancePhase() {
    if (this.currentPhaseIndex < this.phases.length - 1) {
      this.currentPhaseIndex++;
      this._notifyListeners('phaseChanged', this.getCurrentPhase());
      return true;
    }
    return false;
  }

  /**
   * Go back to the previous phase
   * @returns {boolean} Whether the move was successful
   */
  previousPhase() {
    if (this.currentPhaseIndex > 0) {
      this.currentPhaseIndex--;
      this._notifyListeners('phaseChanged', this.getCurrentPhase());
      return true;
    }
    return false;
  }

  /**
   * Jump to a specific phase by index
   * @param {number} phaseIndex - The index to jump to
   * @returns {boolean} Whether the jump was successful
   */
  jumpToPhase(phaseIndex) {
    if (phaseIndex >= 0 && phaseIndex < this.phases.length) {
      this.currentPhaseIndex = phaseIndex;
      this._notifyListeners('phaseChanged', this.getCurrentPhase());
      return true;
    }
    return false;
  }

  /**
   * Get all units in the current phase
   * @returns {Object} Map of power name to array of unit strings
   */
  getCurrentUnits() {
    const phase = this.getCurrentPhase();
    if (!phase || !phase.state || !phase.state.units) {
      return {};
    }
    
    return phase.state.units;
  }

  /**
   * Get all supply centers in the current phase
   * @returns {Object} Map of power name to array of supply centers
   */
  getCurrentSupplyCenters() {
    const phase = this.getCurrentPhase();
    if (!phase || !phase.state || !phase.state.centers) {
      return {};
    }
    
    return phase.state.centers;
  }

  /**
   * Get all orders for the current phase
   * @returns {Object} Map of power name to array of orders
   */
  getCurrentOrders() {
    const phase = this.getCurrentPhase();
    if (!phase || !phase.orders) {
      return {};
    }
    
    return phase.orders;
  }

  /**
   * Get the results of order resolution for the current phase
   * @returns {Object} Map of order to result
   */
  getCurrentResults() {
    const phase = this.getCurrentPhase();
    if (!phase || !phase.results) {
      return {};
    }
    
    return phase.results;
  }

  /**
   * Get the messages for the current phase
   * @returns {Array} Array of message objects
   */
  getCurrentMessages() {
    const phase = this.getCurrentPhase();
    if (!phase || !phase.messages) {
      return [];
    }
    
    return phase.messages;
  }

  /**
   * Add a listener for state changes
   * @param {string} event - The event to listen for ('phaseChanged', etc.)
   * @param {Function} callback - The callback function
   */
  addListener(event, callback) {
    this.listeners.push({ event, callback });
  }

  /**
   * Remove a listener
   * @param {string} event - The event to stop listening for
   * @param {Function} callback - The callback function to remove
   */
  removeListener(event, callback) {
    this.listeners = this.listeners.filter(
      listener => listener.event !== event || listener.callback !== callback
    );
  }

  /**
   * Notify all listeners of an event
   * @param {string} event - The event that occurred
   * @param {any} data - The data to pass to listeners
   * @private
   */
  _notifyListeners(event, data) {
    console.log(`[GameStateManager] _notifyListeners called for event: ${event}`, data);
    if (!Array.isArray(this.listeners)) {
      console.error('[GameStateManager] this.listeners is not an array:', this.listeners);
      return;
    }
    
    const relevantListeners = this.listeners.filter(listener => listener.event === event);
    console.log(`[GameStateManager] Found ${relevantListeners.length} listeners for event: ${event}`);
    
    relevantListeners.forEach(listener => {
      try {
        listener.callback(data);
      } catch (error) {
        console.error(`[GameStateManager] Error in listener callback for event ${event}:`, error);
      }
    });
  }

  /**
   * Public method to notify all listeners of an event
   * @param {string} event - The event that occurred
   * @param {any} data - The data to pass to listeners
   */
  notifyListeners(event, data) {
    console.log(`[GameStateManager] Public notifyListeners called for event: ${event}`, data);
    this._notifyListeners(event, data);
  }

  /**
   * Add phases to the game state
   * @param {Array} phases - Array of phase objects to add
   */
  appendPhases(phases) {
    if (!Array.isArray(phases) || phases.length === 0) {
      return;
    }
    
    this.phases = [...this.phases, ...phases];
    console.log(`[GameStateManager] Added ${phases.length} phases. Total phases: ${this.phases.length}`);
  }

  /**
   * Get the total number of phases
   * @returns {number} The total number of phases
   */
  getPhaseCount() {
    return this.phases.length;
  }

  /**
   * Get a specific phase by index
   * @param {number} index - The phase index to retrieve
   * @returns {Object|null} The phase at the specified index, or null if not found
   */
  getPhase(index) {
    if (index < 0 || index >= this.phases.length) {
      console.warn(`[GameStateManager] Phase index out of range: ${index}`);
      return null;
    }
    return this.phases[index];
  }
} 