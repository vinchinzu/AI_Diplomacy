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

/**
 * OrderVisualizer class for parsing and visualizing Diplomacy orders
 */
export class OrderVisualizer {
  /**
   * Initialize the order visualizer
   * @param {AnimationEffects} animationEffects - Animation effects instance
   * @param {CoordinateMapper} coordinateMapper - Coordinate mapper instance
   */
  constructor(animationEffects, coordinateMapper) {
    this.animationEffects = animationEffects;
    this.coordinateMapper = coordinateMapper;
    
    // Track visualized orders
    this.visualizedOrders = new Map();
  }
  
  /**
   * Parse and visualize a Diplomacy order
   * @param {Object} orderData - The order data
   * @param {string} orderData.text - The order text (e.g., "A PAR-BUR")
   * @param {string} orderData.power - The power giving the order
   * @param {boolean} orderData.success - Whether the order was successful
   * @returns {Object} The created visual elements
   */
  visualizeOrder(orderData) {
    const { text, power, success = true } = orderData;
    
    // Parse the order
    const parsedOrder = this._parseOrderText(text);
    if (!parsedOrder) {
      console.error(`Failed to parse order: ${text}`);
      return null;
    }
    
    // Create visualization based on order type
    let visualization;
    switch (parsedOrder.type) {
      case 'move':
        visualization = this._visualizeMoveOrder(parsedOrder, power, success);
        break;
        
      case 'hold':
        visualization = this._visualizeHoldOrder(parsedOrder, power, success);
        break;
        
      case 'support':
        visualization = this._visualizeSupportOrder(parsedOrder, power, success);
        break;
        
      case 'convoy':
        visualization = this._visualizeConvoyOrder(parsedOrder, power, success);
        break;
        
      default:
        console.warn(`Unsupported order type: ${parsedOrder.type}`);
        return null;
    }
    
    // Store the visualization for potential cleanup
    if (visualization) {
      this.visualizedOrders.set(text, visualization);
    }
    
    return visualization;
  }
  
  /**
   * Parse Diplomacy order text into structured format
   * @param {string} orderText - The order text (e.g., "A PAR-BUR")
   * @returns {Object} Parsed order object
   * @private
   */
  _parseOrderText(orderText) {
    // Remove any extra whitespace
    const text = orderText.trim();
    
    // ==================
    // Move order: A PAR-BUR, F ION-ADR
    // ==================
    const moveRegex = /^([AF])\s+([A-Z]{3}(?:\/[A-Z]{2})?)-([A-Z]{3}(?:\/[A-Z]{2})?)$/;
    const moveMatch = text.match(moveRegex);
    
    if (moveMatch) {
      return {
        type: 'move',
        unitType: moveMatch[1],      // A or F
        location: moveMatch[2],      // Source location
        destination: moveMatch[3]    // Destination location
      };
    }
    
    // ==================
    // Hold order: A PAR H, F ION H
    // ==================
    const holdRegex = /^([AF])\s+([A-Z]{3}(?:\/[A-Z]{2})?)\s+H$/;
    const holdMatch = text.match(holdRegex);
    
    if (holdMatch) {
      return {
        type: 'hold',
        unitType: holdMatch[1], // A or F
        location: holdMatch[2]  // Location
      };
    }
    
    // ==================
    // Support hold order: A PAR S A BUR, F ION S F ADR
    // ==================
    const supportHoldRegex = /^([AF])\s+([A-Z]{3}(?:\/[A-Z]{2})?)\s+S\s+([AF])\s+([A-Z]{3}(?:\/[A-Z]{2})?)$/;
    const supportHoldMatch = text.match(supportHoldRegex);
    
    if (supportHoldMatch) {
      return {
        type: 'support',
        unitType: supportHoldMatch[1],       // A or F
        location: supportHoldMatch[2],       // Supporting unit location
        supportedUnitType: supportHoldMatch[3], // Supported unit type
        supportedLocation: supportHoldMatch[4],  // Supported unit location
        supportType: 'hold'
      };
    }
    
    // ==================
    // Support move order: A PAR S A MUN-BUR, F ION S F TYS-NAP
    // ==================
    const supportMoveRegex = /^([AF])\s+([A-Z]{3}(?:\/[A-Z]{2})?)\s+S\s+([AF])\s+([A-Z]{3}(?:\/[A-Z]{2})?)-([A-Z]{3}(?:\/[A-Z]{2})?)$/;
    const supportMoveMatch = text.match(supportMoveRegex);
    
    if (supportMoveMatch) {
      return {
        type: 'support',
        unitType: supportMoveMatch[1],       // A or F
        from: supportMoveMatch[2],           // Supporting unit location
        supportedUnitType: supportMoveMatch[3], // Supported unit type
        supportedFrom: supportMoveMatch[4],     // Supported unit source
        supportedTo: supportMoveMatch[5],       // Supported unit destination
        supportType: 'move'
      };
    }
    
    // ==================
    // Convoy order: F NTH C A LON-BEL
    // ==================
    const convoyRegex = /^F\s+([A-Z]{3}(?:\/[A-Z]{2})?)\s+C\s+A\s+([A-Z]{3}(?:\/[A-Z]{2})?)-([A-Z]{3}(?:\/[A-Z]{2})?)$/;
    const convoyMatch = text.match(convoyRegex);
    
    if (convoyMatch) {
      return {
        type: 'convoy',
        from: convoyMatch[1],       // Convoying fleet location
        convoyedFrom: convoyMatch[2], // Convoyed army source
        convoyedTo: convoyMatch[3]    // Convoyed army destination
      };
    }
    
    // If no match found, return null
    return null;
  }
  
  /**
   * Visualize a move order
   * @param {Object} parsedOrder - Parsed order object
   * @param {string} power - The power giving the order
   * @param {boolean} success - Whether the order was successful
   * @returns {Object} Created visual elements
   * @private
   */
  _visualizeMoveOrder(parsedOrder, power, success) {
    const { unitType, location, destination } = parsedOrder;
    
    // Extract locations
    const from = location;
    const to = destination;
    
    // Get positions for the locations
    const fromPos = this.coordinateMapper.getPositionForLocation(from);
    const toPos = this.coordinateMapper.getPositionForLocation(to);
    
    if (!fromPos || !toPos) {
      console.error(`[OrderVisualizer] Invalid locations for move order: ${from} to ${to}`);
      return null;
    }
    
    try {
      // Create path with arc between positions
      const pathPoints = this.coordinateMapper.getPathBetween(from, to, 10, 30);
      
      if (!pathPoints || pathPoints.length < 2) {
        console.error(`[OrderVisualizer] Failed to generate path between ${from} and ${to}`);
        return null;
      }
      
      // Create visual elements
      const path = this.animationEffects.createMovementPath(pathPoints, 'move', success);
      
      // Handle case where path creation failed
      if (!path) {
        console.error(`[OrderVisualizer] Failed to create movement path for ${from} to ${to}`);
        return null;
      }
      
      const arrow = this.animationEffects.createMovementArrow(fromPos, toPos, 'move', success);
      
      // If unsuccessful, add bounce effect at destination
      if (!success) {
        const bounceEffect = this.animationEffects.createBounceEffect(toPos);
        return { path, arrow, bounceEffect };
      }
      
      return { path, arrow };
    } catch (error) {
      console.error(`[OrderVisualizer] Error visualizing move order: ${error.message}`);
      return null;
    }
  }
  
  /**
   * Visualize a hold order
   * @param {Object} parsedOrder - Parsed order object
   * @param {string} power - The power giving the order
   * @param {boolean} success - Whether the order was successful
   * @returns {Object} Created visual elements
   * @private
   */
  _visualizeHoldOrder(parsedOrder, power, success) {
    const { unitType, location } = parsedOrder;
    
    // Get position for the location
    const pos = this.coordinateMapper.getPositionForLocation(location);
    
    if (!pos) {
      console.error(`Invalid location for hold order: ${location}`);
      return null;
    }
    
    // Create hold indicator
    const holdIndicator = this.animationEffects.createHoldIndicator(pos, success);
    
    // If unsuccessful, add dislodge effect
    if (!success) {
      const dislodgeEffect = this.animationEffects.createDislodgeEffect(pos);
      return { holdIndicator, dislodgeEffect };
    }
    
    return { holdIndicator };
  }
  
  /**
   * Visualize a support order
   * @param {Object} parsedOrder - Parsed order object
   * @param {string} power - The power giving the order
   * @param {boolean} success - Whether the order was successful
   * @returns {Object} Created visual elements
   * @private
   */
  _visualizeSupportOrder(parsedOrder, power, success) {
    const { unitType, from, supportType } = parsedOrder;
    
    // Get position for the supporting unit
    const fromPos = this.coordinateMapper.getPositionForLocation(from);
    
    if (!fromPos) {
      console.error(`Invalid location for support order: ${from}`);
      return null;
    }
    
    // Create visual elements based on support type
    if (supportType === 'hold') {
      const { supportedLocation } = parsedOrder;
      const supportedPos = this.coordinateMapper.getPositionForLocation(supportedLocation);
      
      if (!supportedPos) {
        console.error(`Invalid supported location: ${supportedLocation}`);
        return null;
      }
      
      // Create path with arc between positions
      const pathPoints = this.coordinateMapper.getPathBetween(from, supportedLocation, 10, 20);
      
      // Create visual elements
      const path = this.animationEffects.createMovementPath(pathPoints, 'support', success);
      const arrow = this.animationEffects.createMovementArrow(fromPos, supportedPos, 'support', success);
      
      // Create highlight around supported unit
      const highlight = this.animationEffects.createTerritoryHighlight(supportedPos, success ? 0xFFC107 : 0xF44336);
      
      return { path, arrow, highlight };
    } else if (supportType === 'move') {
      const { supportedFrom, supportedTo } = parsedOrder;
      const supportedFromPos = this.coordinateMapper.getPositionForLocation(supportedFrom);
      const supportedToPos = this.coordinateMapper.getPositionForLocation(supportedTo);
      
      if (!supportedFromPos || !supportedToPos) {
        console.error(`Invalid locations for supported move: ${supportedFrom} to ${supportedTo}`);
        return null;
      }
      
      // Create path to the supporting unit
      const pathToSupported = this.coordinateMapper.getPathBetween(from, supportedFrom, 10, 20);
      
      // Create path for the supported move
      const pathForSupportedMove = this.coordinateMapper.getPathBetween(supportedFrom, supportedTo, 10, 30);
      
      // Create visual elements
      const path1 = this.animationEffects.createMovementPath(pathToSupported, 'support', success);
      const path2 = this.animationEffects.createMovementPath(pathForSupportedMove, 'support', success);
      const arrow = this.animationEffects.createMovementArrow(supportedFromPos, supportedToPos, 'support', success);
      
      return { pathToUnit: path1, pathForMove: path2, arrow };
    }
    
    return null;
  }
  
  /**
   * Visualize a convoy order
   * @param {Object} parsedOrder - Parsed order object
   * @param {string} power - The power giving the order
   * @param {boolean} success - Whether the order was successful
   * @returns {Object} Created visual elements
   * @private
   */
  _visualizeConvoyOrder(parsedOrder, power, success) {
    const { from, convoyedFrom, convoyedTo } = parsedOrder;
    
    // Get positions for the locations
    const fleetPos = this.coordinateMapper.getPositionForLocation(from);
    const armyFromPos = this.coordinateMapper.getPositionForLocation(convoyedFrom);
    const armyToPos = this.coordinateMapper.getPositionForLocation(convoyedTo);
    
    if (!fleetPos || !armyFromPos || !armyToPos) {
      console.error(`Invalid locations for convoy order: ${from}, ${convoyedFrom}, ${convoyedTo}`);
      return null;
    }
    
    // Create paths
    const pathToFleet = this.coordinateMapper.getPathBetween(convoyedFrom, from, 10, 20);
    const pathFromFleet = this.coordinateMapper.getPathBetween(from, convoyedTo, 10, 20);
    
    // Create visual elements
    const path1 = this.animationEffects.createMovementPath(pathToFleet, 'convoy', success);
    const path2 = this.animationEffects.createMovementPath(pathFromFleet, 'convoy', success);
    
    // Create highlight around the convoying fleet
    const highlight = this.animationEffects.createTerritoryHighlight(fleetPos, success ? 0x9C27B0 : 0xF44336);
    
    return { pathToFleet: path1, pathFromFleet: path2, highlight };
  }
  
  /**
   * Clear all visualized orders
   */
  clearAllVisualizations() {
    // Animation effects will handle the actual removal
    this.visualizedOrders.clear();
    this.animationEffects.clearAllEffects();
  }
  
  /**
   * Remove visualization for a specific order
   * @param {string} orderText - The order text to remove
   */
  removeVisualization(orderText) {
    const visualization = this.visualizedOrders.get(orderText);
    if (visualization) {
      // Remove each element in the visualization
      Object.values(visualization).forEach(element => {
        this.animationEffects.scene.remove(element);
        
        // Remove from active effects
        const index = this.animationEffects.activeEffects.indexOf(element);
        if (index !== -1) {
          this.animationEffects.activeEffects.splice(index, 1);
        }
      });
      
      this.visualizedOrders.delete(orderText);
    }
  }
} 