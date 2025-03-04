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
 * AnimationEffects class for creating and managing visual effects for animations
 */
export class AnimationEffects {
  /**
   * Initialize animation effects
   * @param {THREE.Scene} scene - The Three.js scene
   */
  constructor(scene) {
    this.scene = scene;
    this.activeEffects = [];
    this.arrowHelpers = new Map();
    this.effects = {};
    
    // Initialize common materials
    this._initMaterials();
  }
  
  /**
   * Initialize commonly used materials
   * @private
   */
  _initMaterials() {
    // Movement indicator materials
    this.materials = {
      // Regular movement
      move: new THREE.MeshBasicMaterial({
        color: 0x4CAF50, // Green
        transparent: true,
        opacity: 0.7
      }),
      
      // Hold order 
      hold: new THREE.MeshBasicMaterial({
        color: 0x2196F3, // Blue
        transparent: true,
        opacity: 0.7
      }),
      
      // Support order
      support: new THREE.MeshBasicMaterial({
        color: 0xFFC107, // Amber
        transparent: true,
        opacity: 0.7
      }),
      
      // Convoy order
      convoy: new THREE.MeshBasicMaterial({
        color: 0x9C27B0, // Purple
        transparent: true,
        opacity: 0.7
      }),
      
      // Failed order
      failed: new THREE.MeshBasicMaterial({
        color: 0xF44336, // Red
        transparent: true,
        opacity: 0.7
      }),
      
      // Cut support
      cut: new THREE.MeshBasicMaterial({
        color: 0xFF9800, // Orange
        transparent: true,
        opacity: 0.7
      })
    };
  }
  
  /**
   * Create a movement path for unit animation
   * @param {Array<THREE.Vector3>} path - Array of points defining the path
   * @param {string} orderType - Type of order ('move', 'support', 'convoy', etc.)
   * @param {boolean} success - Whether the order was successful
   * @returns {THREE.Object3D} The path object
   */
  createMovementPath(path, orderType = 'move', success = true) {
    // Use appropriate material based on order type and success
    let material;
    if (!success) {
      material = this.materials.failed;
    } else {
      material = this.materials[orderType] || this.materials.move;
    }
    
    // Create a smooth curve from the path points
    const curve = new THREE.CatmullRomCurve3(path);
    const points = curve.getPoints(50); // Higher number = smoother curve
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    
    // Create the path line
    const line = new THREE.Line(geometry, material);
    line.userData.type = 'movementPath';
    line.userData.createdAt = Date.now();
    line.userData.duration = 3000; // 3 seconds default lifetime
    
    // Add to scene
    this.scene.add(line);
    this.activeEffects.push(line);
    
    return line;
  }
  
  /**
   * Create an arrow showing the direction of movement
   * @param {THREE.Vector3} from - Starting position
   * @param {THREE.Vector3} to - Target position
   * @param {string} orderType - Type of order ('move', 'support', 'convoy', etc.)
   * @param {boolean} success - Whether the order was successful
   * @returns {THREE.Object3D} The arrow helper object
   */
  createMovementArrow(from, to, orderType = 'move', success = true) {
    // Use appropriate color based on order type and success
    let color;
    if (!success) {
      color = 0xF44336; // Red for failed
    } else {
      switch (orderType) {
        case 'support': color = 0xFFC107; break; // Amber
        case 'convoy': color = 0x9C27B0; break; // Purple
        case 'hold': color = 0x2196F3; break; // Blue
        default: color = 0x4CAF50; break; // Green
      }
    }
    
    // Calculate direction and length
    const direction = new THREE.Vector3().subVectors(to, from).normalize();
    const length = from.distanceTo(to) * 0.8; // Make arrow slightly shorter than full path
    
    // Create arrow helper
    const arrowHelper = new THREE.ArrowHelper(
      direction,
      from,
      length,
      color,
      length * 0.2, // Head length as 20% of total length
      length * 0.1  // Head width as 10% of total length
    );
    
    arrowHelper.userData.type = 'movementArrow';
    arrowHelper.userData.createdAt = Date.now();
    arrowHelper.userData.duration = 3000; // 3 seconds default lifetime
    
    // Add to scene
    this.scene.add(arrowHelper);
    this.activeEffects.push(arrowHelper);
    
    return arrowHelper;
  }
  
  /**
   * Create a bounce effect at the specified position
   * @param {THREE.Vector3} position - Position for the bounce effect
   * @returns {THREE.Object3D} The bounce effect object
   */
  createBounceEffect(position) {
    // Create a sphere that will expand and fade out
    const geometry = new THREE.SphereGeometry(2, 16, 16);
    const material = new THREE.MeshBasicMaterial({
      color: 0xFF5252,
      transparent: true,
      opacity: 0.8
    });
    
    const sphere = new THREE.Mesh(geometry, material);
    sphere.position.copy(position);
    sphere.userData.type = 'bounceEffect';
    sphere.userData.createdAt = Date.now();
    sphere.userData.duration = 1000; // 1 second effect
    sphere.userData.animation = {
      initialScale: 1,
      targetScale: 15,
      initialOpacity: 0.8,
      targetOpacity: 0
    };
    
    // Add to scene
    this.scene.add(sphere);
    this.activeEffects.push(sphere);
    
    return sphere;
  }
  
  /**
   * Create a dislodge effect at the specified position
   * @param {THREE.Vector3} position - Position for the dislodge effect
   * @returns {THREE.Object3D} The dislodge effect object
   */
  createDislodgeEffect(position) {
    // Create particles radiating outward
    const particleCount = 30;
    const particles = new THREE.Group();
    particles.position.copy(position);
    particles.userData.type = 'dislodgeEffect';
    particles.userData.createdAt = Date.now();
    particles.userData.duration = 1500; // 1.5 seconds effect
    
    // Create particles
    for (let i = 0; i < particleCount; i++) {
      const size = Math.random() * 2 + 1;
      const geometry = new THREE.BoxGeometry(size, size, size);
      const material = new THREE.MeshBasicMaterial({
        color: 0xFF0000,
        transparent: true,
        opacity: 0.8
      });
      
      const particle = new THREE.Mesh(geometry, material);
      
      // Set random direction
      const phi = Math.random() * Math.PI * 2;
      const theta = Math.random() * Math.PI;
      const speed = Math.random() * 5 + 5;
      
      particle.userData.velocity = new THREE.Vector3(
        Math.sin(theta) * Math.cos(phi) * speed,
        Math.sin(theta) * Math.sin(phi) * speed,
        Math.cos(theta) * speed
      );
      
      particles.add(particle);
    }
    
    // Add to scene
    this.scene.add(particles);
    this.activeEffects.push(particles);
    
    return particles;
  }
  
  /**
   * Create a highlight effect for a territory
   * @param {THREE.Vector3} position - Position for the highlight
   * @param {number} color - Color of the highlight
   * @returns {THREE.Object3D} The highlight effect object
   */
  createTerritoryHighlight(position, color = 0xFFEB3B) {
    // Create a ring at ground level
    const geometry = new THREE.RingGeometry(30, 40, 32);
    const material = new THREE.MeshBasicMaterial({
      color: color,
      transparent: true,
      opacity: 0.4,
      side: THREE.DoubleSide
    });
    
    const ring = new THREE.Mesh(geometry, material);
    ring.position.copy(position);
    ring.position.y = 1; // Just above ground
    ring.rotation.x = -Math.PI / 2; // Lay flat
    ring.userData.type = 'territoryHighlight';
    ring.userData.createdAt = Date.now();
    ring.userData.duration = 5000; // 5 seconds highlight
    ring.userData.animation = {
      pulseMin: 0.3,
      pulseMax: 0.6,
      pulseSpeed: 2
    };
    
    // Add to scene
    this.scene.add(ring);
    this.activeEffects.push(ring);
    
    return ring;
  }
  
  /**
   * Create a hold order indicator
   * @param {THREE.Vector3} position - Position for the hold indicator
   * @param {boolean} success - Whether the hold was successful
   * @returns {THREE.Object3D} The hold indicator object
   */
  createHoldIndicator(position, success = true) {
    // Create a circular pattern
    const geometry = new THREE.TorusGeometry(15, 2, 16, 32);
    const material = new THREE.MeshBasicMaterial({
      color: success ? 0x2196F3 : 0xF44336,
      transparent: true,
      opacity: 0.7
    });
    
    const torus = new THREE.Mesh(geometry, material);
    torus.position.copy(position);
    torus.position.y = 5; // Above ground
    torus.rotation.x = -Math.PI / 2; // Lay flat
    torus.userData.type = 'holdIndicator';
    torus.userData.createdAt = Date.now();
    torus.userData.duration = 3000; // 3 seconds display
    torus.userData.animation = {
      rotation: 0.01,
      pulseMin: 0.7,
      pulseMax: 1.0,
      pulseSpeed: 3
    };
    
    // Add to scene
    this.scene.add(torus);
    this.activeEffects.push(torus);
    
    return torus;
  }
  
  /**
   * Update all active effects
   * @param {number} deltaTime - Time elapsed since last update in seconds
   */
  update(deltaTime) {
    const now = Date.now();
    const expiredEffects = [];
    
    // Update each effect
    for (const effect of this.activeEffects) {
      const age = now - effect.userData.createdAt;
      const progress = Math.min(age / effect.userData.duration, 1);
      
      // Check if effect has expired
      if (progress >= 1) {
        expiredEffects.push(effect);
        continue;
      }
      
      // Update based on effect type
      switch (effect.userData.type) {
        case 'bounceEffect':
          this._updateBounceEffect(effect, progress);
          break;
          
        case 'dislodgeEffect':
          this._updateDislodgeEffect(effect, deltaTime);
          break;
          
        case 'territoryHighlight':
          this._updateTerritoryHighlight(effect, deltaTime);
          break;
          
        case 'holdIndicator':
          this._updateHoldIndicator(effect, deltaTime);
          break;
          
        case 'movementPath':
        case 'movementArrow':
          this._updateMovementIndicator(effect, progress);
          break;
      }
    }
    
    // Remove expired effects
    for (const effect of expiredEffects) {
      this.scene.remove(effect);
      const index = this.activeEffects.indexOf(effect);
      if (index !== -1) {
        this.activeEffects.splice(index, 1);
      }
    }
  }
  
  /**
   * Update bounce effect animation
   * @param {THREE.Object3D} effect - The effect to update
   * @param {number} progress - Animation progress (0-1)
   * @private
   */
  _updateBounceEffect(effect, progress) {
    const { initialScale, targetScale, initialOpacity, targetOpacity } = effect.userData.animation;
    const scale = initialScale + (targetScale - initialScale) * progress;
    const opacity = initialOpacity + (targetOpacity - initialOpacity) * progress;
    
    effect.scale.set(scale, scale, scale);
    effect.material.opacity = opacity;
  }
  
  /**
   * Update dislodge effect animation
   * @param {THREE.Object3D} effect - The effect to update
   * @param {number} deltaTime - Time elapsed since last update in seconds
   * @private
   */
  _updateDislodgeEffect(effect, deltaTime) {
    // Move each particle outward
    effect.children.forEach(particle => {
      particle.position.add(particle.userData.velocity.clone().multiplyScalar(deltaTime));
      particle.material.opacity -= deltaTime * 0.5; // Fade out
    });
  }
  
  /**
   * Update territory highlight animation
   * @param {THREE.Object3D} effect - The effect to update
   * @param {number} deltaTime - Time elapsed since last update in seconds
   * @private
   */
  _updateTerritoryHighlight(effect, deltaTime) {
    const { pulseMin, pulseMax, pulseSpeed } = effect.userData.animation;
    
    // Calculate pulsing opacity
    const time = Date.now() / 1000;
    const pulse = pulseMin + (pulseMax - pulseMin) * (0.5 + 0.5 * Math.sin(time * pulseSpeed));
    
    effect.material.opacity = pulse;
  }
  
  /**
   * Update hold indicator animation
   * @param {THREE.Object3D} effect - The effect to update
   * @param {number} deltaTime - Time elapsed since last update in seconds
   * @private
   */
  _updateHoldIndicator(effect, deltaTime) {
    const { rotation, pulseMin, pulseMax, pulseSpeed } = effect.userData.animation;
    
    // Rotate the torus
    effect.rotation.z += rotation;
    
    // Calculate pulsing opacity
    const time = Date.now() / 1000;
    const pulse = pulseMin + (pulseMax - pulseMin) * (0.5 + 0.5 * Math.sin(time * pulseSpeed));
    
    effect.material.opacity = pulse;
  }
  
  /**
   * Update movement indicator animation
   * @param {THREE.Object3D} effect - The effect to update
   * @param {number} progress - Animation progress (0-1)
   * @private
   */
  _updateMovementIndicator(effect, progress) {
    // Fade out as animation nears completion
    const fadeStart = 0.8;
    if (progress > fadeStart) {
      const fadeProgress = (progress - fadeStart) / (1 - fadeStart);
      if (effect.material) {
        effect.material.opacity = 0.7 * (1 - fadeProgress);
      } else if (effect.line && effect.line.material) {
        effect.line.material.opacity = 0.7 * (1 - fadeProgress);
      }
    }
  }
  
  /**
   * Clear all active effects
   */
  clearAllEffects() {
    for (const effect of this.activeEffects) {
      this.scene.remove(effect);
    }
    this.activeEffects = [];
  }
} 