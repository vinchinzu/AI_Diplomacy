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
   * Format phases from game data into a consistent format
   * @param {Object} gameData - The raw game data
   * @returns {Array} - Array of formatted phase objects
   * @private
   */
  _formatPhases(gameData) {
    // Handle both the format from loadGameFromDisk and our custom format
    if (gameData.phases) {
      return gameData.phases.map(phase => ({
        name: phase.name,
        state: phase.state,
        orders: phase.orders || {},
        results: phase.results || {},
        messages: Array.isArray(phase.messages) 
          ? phase.messages 
          : Object.values(phase.messages || {})
      }));
    } 
    
    // If using the Game object directly from the engine
    const phases = [];
    
    // Add historical phases
    if (gameData.state_history) {
      for (const [phaseName, state] of Object.entries(gameData.state_history)) {
        phases.push({
          name: phaseName,
          state: state,
          orders: (gameData.order_history && gameData.order_history[phaseName]) || {},
          results: (gameData.result_history && gameData.result_history[phaseName]) || {},
          messages: (gameData.message_history && gameData.message_history[phaseName]) 
            ? Object.values(gameData.message_history[phaseName])
            : []
        });
      }
    }
    
    // Add current phase
    if (gameData.phase) {
      phases.push({
        name: gameData.phase,
        state: gameData,
        orders: gameData.orders || {},
        results: (gameData.result_history && gameData.result_history[gameData.phase]) || {},
        messages: gameData.messages || []
      });
    }
    
    // Sort phases chronologically
    phases.sort((a, b) => {
      // Parse phase names and compare
      const aMatch = a.name.match(/([SFWR])(\d+)([AMRB])/);
      const bMatch = b.name.match(/([SFWR])(\d+)([AMRB])/);
      
      if (!aMatch || !bMatch) return 0;
      
      // Compare years
      const yearDiff = parseInt(aMatch[2]) - parseInt(bMatch[2]);
      if (yearDiff !== 0) return yearDiff;
      
      // Compare seasons (S-Spring, F-Fall, W-Winter, R-Retreat)
      const seasonOrder = {S: 0, F: 1, W: 2, R: 3};
      const seasonDiff = seasonOrder[aMatch[1]] - seasonOrder[bMatch[1]];
      if (seasonDiff !== 0) return seasonDiff;
      
      // Compare phase types (M-Movement, R-Retreat, A-Adjustment, B-Build)
      const phaseOrder = {M: 0, R: 1, A: 2, B: 3};
      return phaseOrder[aMatch[3]] - phaseOrder[bMatch[3]];
    });
    
    return phases;
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
} 