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
 * Entry point for the Diplomacy game animation system.
 * This module provides a Three.js based animation player for replaying Diplomacy games.
 */

import { MapRenderer } from './renderer/MapRenderer.js';
import { GameStateManager } from './utils/GameStateManager.js';
import { AnimationPlayer } from './components/AnimationPlayer.js';

// Exported components for public API
export { MapRenderer } from './renderer/MapRenderer.js';
export { GameStateManager } from './utils/GameStateManager.js';
export { AnimationPlayer } from './components/AnimationPlayer.js';

// Map variant definitions
export const MAP_VARIANTS = ['standard', 'ancmed', 'modern', 'pure'];

/**
 * Initialize the animation system with a game state
 * @param {Object} options - Configuration options
 * @param {string} options.containerId - ID of the container element
 * @param {GameStateManager} options.gameStateManager - Game state manager instance
 * @param {string} options.mapVariant - Map variant to use (default: 'standard')
 * @param {string} options.detailLevel - Detail level for unit models (default: 'medium')
 * @returns {AnimationPlayer} The animation player instance
 */
export function initializeAnimation(options) {
  // Ensure we have required parameters
  if (!options.containerId) {
    throw new Error('Missing required parameter: containerId');
  }
  
  if (!options.gameStateManager) {
    throw new Error('Missing required parameter: gameStateManager');
  }
  
  // Create and return the animation player
  const player = new AnimationPlayer({
    containerId: options.containerId,
    gameStateManager: options.gameStateManager,
    mapVariant: options.mapVariant || 'standard',
    detailLevel: options.detailLevel || 'medium'
  });
  
  // Return the player instance for further interaction
  return player;
}

/**
 * Load a game from file and initialize the animation
 * @param {Object} options - Configuration options
 * @param {File} options.gameFile - Game file to load
 * @param {string} options.containerId - ID of the container element
 * @param {string} options.mapVariant - Map variant to use (default: 'standard')
 * @param {string} options.detailLevel - Detail level for unit models (default: 'medium')
 * @returns {Promise<AnimationPlayer>} Promise resolving to the animation player instance
 */
export async function loadGameFromFile(options) {
  // Ensure we have required parameters
  if (!options.gameFile) {
    throw new Error('Missing required parameter: gameFile');
  }
  
  if (!options.containerId) {
    throw new Error('Missing required parameter: containerId');
  }
  
  try {
    // Read file
    const fileContent = await options.gameFile.text();
    
    // Parse JSON
    const gameState = JSON.parse(fileContent);
    
    // Import GameStateManager
    const { GameStateManager } = await import('./utils/GameStateManager.js');
    
    // Initialize game state manager
    const gameStateManager = new GameStateManager();
    await gameStateManager.loadGameState(gameState);
    
    // Initialize animation
    return initializeAnimation({
      containerId: options.containerId,
      gameStateManager: gameStateManager,
      mapVariant: options.mapVariant || 'standard',
      detailLevel: options.detailLevel || 'medium'
    });
  } catch (error) {
    console.error('Error loading game from file:', error);
    throw error;
  }
}

/**
 * Load game data and initialize the animation
 * @param {Object} options - Configuration options
 * @param {Object} options.gameState - Game state data
 * @param {string} options.containerId - ID of the container element 
 * @param {string} options.mapVariant - Map variant to use (default: 'standard')
 * @param {string} options.detailLevel - Detail level for unit models (default: 'medium')
 * @returns {Promise<AnimationPlayer>} Promise resolving to the animation player instance
 */
export async function loadGameForAnimation(options) {
  // Ensure we have required parameters
  if (!options.gameState) {
    throw new Error('Missing required parameter: gameState');
  }
  
  if (!options.containerId) {
    throw new Error('Missing required parameter: containerId');
  }
  
  try {
    // Import GameStateManager
    const { GameStateManager } = await import('./utils/GameStateManager.js');
    
    // Initialize game state manager
    const gameStateManager = new GameStateManager();
    await gameStateManager.loadGameState(options.gameState);
    
    // Initialize animation
    return initializeAnimation({
      containerId: options.containerId,
      gameStateManager: gameStateManager,
      mapVariant: options.mapVariant || 'standard',
      detailLevel: options.detailLevel || 'medium'
    });
  } catch (error) {
    console.error('Error loading game for animation:', error);
    throw error;
  }
} 