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
 * UnitModels class for creating and managing 3D models for armies and fleets
 */
export class UnitModels {
  /**
   * Create unit models
   * @param {Object} options - Configuration options
   * @param {string} options.detailLevel - Level of detail for models ('low', 'medium', 'high')
   */
  constructor(options = {}) {
    this.detailLevel = options.detailLevel || 'medium';
    this.models = {
      army: null,
      fleet: null
    };
    
    // Standard power colors
    this.powerColors = {
      AUSTRIA: 0xBF1E2E,  // Red
      ENGLAND: 0x1B5EC0,  // Blue
      FRANCE: 0x127BBF,   // Light Blue
      GERMANY: 0x454545,  // Dark Gray
      ITALY: 0x087E3B,    // Green
      RUSSIA: 0xFFFFFF,   // White
      TURKEY: 0xFFD700    // Gold
    };
    
    // Initialize models
    this._createModels();
  }
  
  /**
   * Create 3D models for armies and fleets
   * @private
   */
  _createModels() {
    // Create models based on detail level
    switch (this.detailLevel) {
      case 'high':
        this._createHighDetailModels();
        break;
      case 'low':
        this._createLowDetailModels();
        break;
      case 'medium':
      default:
        this._createMediumDetailModels();
        break;
    }
  }
  
  /**
   * Create low detail (simple) unit models
   * @private
   */
  _createLowDetailModels() {
    // Simple army model (box)
    const armyGeometry = new THREE.BoxGeometry(10, 5, 10);
    const armyMaterial = new THREE.MeshPhongMaterial({
      color: 0x888888,
      shininess: 30
    });
    this.models.army = new THREE.Mesh(armyGeometry, armyMaterial);
    
    // Simple fleet model (cone)
    const fleetGeometry = new THREE.ConeGeometry(6, 15, 8);
    const fleetMaterial = new THREE.MeshPhongMaterial({
      color: 0x888888,
      shininess: 30
    });
    this.models.fleet = new THREE.Mesh(fleetGeometry, fleetMaterial);
    
    // Rotate fleet to look like a ship
    this.models.fleet.rotation.x = Math.PI / 2;
  }
  
  /**
   * Create medium detail unit models
   * @private
   */
  _createMediumDetailModels() {
    // Create army group
    this.models.army = new THREE.Group();
    
    // Army base (tank-like shape)
    const bodyGeometry = new THREE.BoxGeometry(10, 4, 12);
    const bodyMaterial = new THREE.MeshPhongMaterial({
      color: 0x888888,
      shininess: 50
    });
    const body = new THREE.Mesh(bodyGeometry, bodyMaterial);
    body.position.y = 2;
    this.models.army.add(body);
    
    // Army turret
    const turretGeometry = new THREE.CylinderGeometry(3, 3, 3, 8);
    const turretMaterial = new THREE.MeshPhongMaterial({
      color: 0x888888,
      shininess: 50
    });
    const turret = new THREE.Mesh(turretGeometry, turretMaterial);
    turret.position.y = 5.5;
    this.models.army.add(turret);
    
    // Army cannon
    const cannonGeometry = new THREE.CylinderGeometry(0.8, 0.8, 8, 8);
    const cannonMaterial = new THREE.MeshPhongMaterial({
      color: 0x666666,
      shininess: 70
    });
    const cannon = new THREE.Mesh(cannonGeometry, cannonMaterial);
    cannon.position.set(0, 5.5, 6);
    cannon.rotation.x = Math.PI / 2;
    this.models.army.add(cannon);
    
    // Army flag (to show power color)
    const flagPoleGeometry = new THREE.CylinderGeometry(0.3, 0.3, 10, 6);
    const flagPoleMaterial = new THREE.MeshPhongMaterial({
      color: 0xDDDDDD,
      shininess: 30
    });
    const flagPole = new THREE.Mesh(flagPoleGeometry, flagPoleMaterial);
    flagPole.position.set(0, 9, -3);
    this.models.army.add(flagPole);
    
    const flagGeometry = new THREE.PlaneGeometry(5, 3);
    const flagMaterial = new THREE.MeshPhongMaterial({
      color: 0xFFFFFF,
      shininess: 30,
      side: THREE.DoubleSide
    });
    const flag = new THREE.Mesh(flagGeometry, flagMaterial);
    flag.position.set(2.5, 11, -3);
    flag.rotation.y = Math.PI / 2;
    this.models.army.userData.flag = flag;
    this.models.army.add(flag);
    
    // Create fleet group
    this.models.fleet = new THREE.Group();
    
    // Fleet hull
    const hullGeometry = new THREE.CylinderGeometry(3, 6, 16, 8);
    const hullMaterial = new THREE.MeshPhongMaterial({
      color: 0x888888,
      shininess: 50
    });
    const hull = new THREE.Mesh(hullGeometry, hullMaterial);
    hull.rotation.x = Math.PI / 2;
    this.models.fleet.add(hull);
    
    // Fleet deck
    const deckGeometry = new THREE.BoxGeometry(4, 1, 12);
    const deckMaterial = new THREE.MeshPhongMaterial({
      color: 0x666666,
      shininess: 50
    });
    const deck = new THREE.Mesh(deckGeometry, deckMaterial);
    deck.position.y = 3;
    this.models.fleet.add(deck);
    
    // Fleet sail (to show power color)
    const sailGeometry = new THREE.PlaneGeometry(1, 10);
    const sailMaterial = new THREE.MeshPhongMaterial({
      color: 0xFFFFFF,
      shininess: 20,
      side: THREE.DoubleSide
    });
    const sail = new THREE.Mesh(sailGeometry, sailMaterial);
    sail.position.set(0, 8, 0);
    this.models.fleet.userData.sail = sail;
    this.models.fleet.add(sail);
    
    // Fleet mast
    const mastGeometry = new THREE.CylinderGeometry(0.4, 0.4, 10, 6);
    const mastMaterial = new THREE.MeshPhongMaterial({
      color: 0x8B4513,
      shininess: 30
    });
    const mast = new THREE.Mesh(mastGeometry, mastMaterial);
    mast.position.set(0, 8, 0);
    this.models.fleet.add(mast);
  }
  
  /**
   * Create high detail unit models
   * @private
   */
  _createHighDetailModels() {
    // For high detail, we'll use the medium detail models for now
    // In a real implementation, this would create more complex geometries
    this._createMediumDetailModels();
    
    // Add extra details to army
    const wheelsGeometry = new THREE.CylinderGeometry(1.5, 1.5, 12, 16);
    const wheelsMaterial = new THREE.MeshPhongMaterial({
      color: 0x333333,
      shininess: 40
    });
    
    // Add wheels to the tank
    const frontWheels = new THREE.Mesh(wheelsGeometry, wheelsMaterial);
    frontWheels.rotation.z = Math.PI / 2;
    frontWheels.position.set(0, 1, 4);
    this.models.army.add(frontWheels);
    
    const backWheels = new THREE.Mesh(wheelsGeometry, wheelsMaterial);
    backWheels.rotation.z = Math.PI / 2;
    backWheels.position.set(0, 1, -4);
    this.models.army.add(backWheels);
    
    // Add extra details to fleet
    const bowGeometry = new THREE.ConeGeometry(3, 4, 8);
    const bowMaterial = new THREE.MeshPhongMaterial({
      color: 0x888888,
      shininess: 50
    });
    const bow = new THREE.Mesh(bowGeometry, bowMaterial);
    bow.rotation.x = Math.PI / 2;
    bow.position.z = 10;
    this.models.fleet.add(bow);
  }
  
  /**
   * Get unit model by type
   * @param {string} type - Unit type ('A' for army, 'F' for fleet)
   * @param {string} power - Power controlling the unit (e.g. 'AUSTRIA')
   * @returns {THREE.Object3D} The unit model
   */
  getUnitModel(type, power) {
    // Get the base model
    const modelType = type === 'A' ? 'army' : 'fleet';
    const model = this.models[modelType].clone();
    
    // Determine unit color based on power
    const color = this.powerColors[power] || 0x888888;
    
    // Apply color
    model.traverse(child => {
      if (child.isMesh) {
        // Create a new material to avoid modifying the original
        child.material = child.material.clone();
        
        // Apply power color to main body parts, but not to some details
        if (
          (modelType === 'army' && child !== model.userData.flag) ||
          (modelType === 'fleet' && child !== model.userData.sail)
        ) {
          child.material.color.setHex(color);
        }
      }
    });
    
    // For army flag or fleet sail, set a lighter color
    const colorObj = new THREE.Color(color);
    const lightColor = new THREE.Color(
      Math.min(1, colorObj.r + 0.3),
      Math.min(1, colorObj.g + 0.3),
      Math.min(1, colorObj.b + 0.3)
    );
    
    if (modelType === 'army' && model.userData.flag) {
      model.userData.flag.material.color.copy(lightColor);
    }
    
    if (modelType === 'fleet' && model.userData.sail) {
      model.userData.sail.material.color.copy(lightColor);
    }
    
    return model;
  }
} 