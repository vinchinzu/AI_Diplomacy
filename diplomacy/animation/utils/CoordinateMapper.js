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
 * Maps Diplomacy game coordinates to 3D positions.
 * This class handles the translation between game location names (e.g. "LON", "PAR") 
 * and 3D coordinates for the Three.js renderer.
 */
export class CoordinateMapper {
  /**
   * Creates a new CoordinateMapper for a specific map
   * @param {string} mapName - The name of the map (e.g. "standard", "ancmed")
   */
  constructor(mapName) {
    this.mapName = mapName;
    this.coordinates = {};
    this.provinceData = {};
    this.mapWidth = 1000;  // Default map dimensions
    this.mapHeight = 1000;
    
    // Initialize with placeholder coordinates until we load the real ones
    this._initializeCoordinates();
  }

  /**
   * Public initialize method that returns a Promise
   * @returns {Promise} A promise that resolves when coordinates are loaded
   */
  initialize() {
    return new Promise((resolve, reject) => {
      // We're already initialized, just resolve
      setTimeout(resolve, 0);
    });
  }

  /**
   * Initialize coordinate mappings
   * @private
   */
  _initializeCoordinates() {
    // Try to load coordinates from the JSON file
    try {
      this._loadCoordinatesFromJson();
    } catch (error) {
      console.warn(`[CoordinateMapper] Could not load coordinates from JSON: ${error.message}`);
      console.warn('[CoordinateMapper] Using built-in placeholder coordinates');
      this._useBuiltinCoordinates();
    }
  }

  /**
   * Load coordinates from a JSON file
   * @private
   */
  _loadCoordinatesFromJson() {
    // Use relative paths for browser environment
    const jsonPath = `./diplomacy/animation/assets/maps/${this.mapName}_coords.json`;
    console.log(`[CoordinateMapper] Attempting to load coordinates from ${jsonPath}`);
    
    // In a browser environment, we need to use fetch to load the JSON
    if (typeof fetch !== 'undefined') {
      fetch(jsonPath)
        .then(response => {
          if (!response.ok) {
            // Try alternate path format
            const altPath = `./assets/maps/${this.mapName}_coords.json`;
            console.log(`[CoordinateMapper] First attempt failed, trying ${altPath}`);
            return fetch(altPath);
          }
          return response;
        })
        .then(response => {
          if (!response.ok) {
            throw new Error(`Could not load coordinates: ${response.status}`);
          }
          return response.json();
        })
        .then(data => {
          this._processCoordinateData(data);
        })
        .catch(error => {
          console.warn(`[CoordinateMapper] JSON fetch error: ${error.message}`);
          console.log('[CoordinateMapper] Falling back to built-in coordinates');
          this._useBuiltinCoordinates();
        });
    } else {
      // In a Node.js environment, we can use require
      // But in our browser context, this will likely fall back to built-in coords
      try {
        const data = require(`../assets/maps/${this.mapName}_coords.json`);
        this._processCoordinateData(data);
      } catch (error) {
        console.warn(`[CoordinateMapper] Could not load coordinate file: ${error.message}`);
        this._useBuiltinCoordinates();
      }
    }
  }

  /**
   * Process coordinate data from JSON
   * @param {Object} data - Coordinate data
   * @private
   */
  _processCoordinateData(data) {
    if (!data) {
      console.warn('[CoordinateMapper] Empty coordinate data, using built-in fallback');
      this._useBuiltinCoordinates();
      return;
    }
    
    try {
      console.log('[CoordinateMapper] Processing coordinate data');
      
      // Set map dimensions if provided
      if (data.mapWidth && data.mapHeight) {
        this.mapWidth = data.mapWidth;
        this.mapHeight = data.mapHeight;
      }
      
      // Process provinces
      if (data.provinces) {
        this.provinceData = data.provinces;
      }
      
      // Process coordinates
      if (data.coordinates) {
        this.coordinates = data.coordinates;
        console.log(`[CoordinateMapper] Loaded ${Object.keys(this.coordinates).length} locations`);
      } else {
        console.warn('[CoordinateMapper] No coordinates found in data, using built-in');
        this._useBuiltinCoordinates();
      }
    } catch (error) {
      console.error(`[CoordinateMapper] Error processing coordinate data: ${error.message}`);
      this._useBuiltinCoordinates();
    }
  }

  /**
   * Use built-in placeholder coordinates
   * @private
   */
  _useBuiltinCoordinates() {
    // For Phase 2, we provide detailed coordinates for the standard map
    
    // Standard map coordinates, optimized for better layout
    const standardMapCoordinates = {
      // Western Europe
      'BRE': { x: -350, y: 0, z: 150 },  // Brest
      'PAR': { x: -250, y: 0, z: 100 },  // Paris
      'PIC': { x: -250, y: 0, z: 50 },   // Picardy
      'BUR': { x: -200, y: 0, z: 100 },  // Burgundy 
      'GAS': { x: -300, y: 0, z: 200 },  // Gascony
      'BEL': { x: -200, y: 0, z: 0 },    // Belgium
      'RUH': { x: -150, y: 0, z: 0 },    // Ruhr
      'HOL': { x: -150, y: 0, z: -50 },  // Holland
      
      // Great Britain
      'LON': { x: -300, y: 0, z: -100 }, // London
      'WAL': { x: -350, y: 0, z: -100 }, // Wales
      'YOR': { x: -300, y: 0, z: -150 }, // Yorkshire
      'EDI': { x: -300, y: 0, z: -200 }, // Edinburgh
      'LVP': { x: -350, y: 0, z: -170 }, // Liverpool
      'CLY': { x: -330, y: 0, z: -250 }, // Clyde
      
      // Northern Europe
      'DEN': { x: -50, y: 0, z: -200 },  // Denmark
      'NWY': { x: 0, y: 0, z: -280 },    // Norway
      'SWE': { x: 50, y: 0, z: -250 },   // Sweden
      'FIN': { x: 150, y: 0, z: -300 },  // Finland
      'STP': { x: 200, y: 0, z: -300 },  // St. Petersburg
      'STP/NC': { x: 200, y: 0, z: -350 }, // St. Petersburg (North Coast)
      'STP/SC': { x: 250, y: 0, z: -250 }, // St. Petersburg (South Coast)
      
      // Central Europe
      'MUN': { x: -80, y: 0, z: 50 },    // Munich
      'BER': { x: -50, y: 0, z: -100 },  // Berlin
      'KIE': { x: -100, y: 0, z: -100 }, // Kiel
      'SIL': { x: 0, y: 0, z: -50 },     // Silesia
      'BOH': { x: 0, y: 0, z: 50 },      // Bohemia
      'TYR': { x: -20, y: 0, z: 100 },   // Tyrolia
      'VIE': { x: 50, y: 0, z: 100 },    // Vienna
      'TRI': { x: 50, y: 0, z: 150 },    // Trieste
      'BUD': { x: 100, y: 0, z: 100 },   // Budapest
      'GAL': { x: 120, y: 0, z: 50 },    // Galicia
      
      // Southern Europe
      'MAR': { x: -200, y: 0, z: 200 },  // Marseilles
      'PIE': { x: -100, y: 0, z: 150 },  // Piedmont
      'VEN': { x: -50, y: 0, z: 150 },   // Venice
      'TUS': { x: -50, y: 0, z: 200 },   // Tuscany
      'ROM': { x: 0, y: 0, z: 250 },     // Rome
      'NAP': { x: 50, y: 0, z: 300 },    // Naples
      'APU': { x: 100, y: 0, z: 250 },   // Apulia
      
      // Iberian Peninsula
      'SPA': { x: -350, y: 0, z: 300 },    // Spain
      'SPA/NC': { x: -380, y: 0, z: 250 }, // Spain (North Coast)
      'SPA/SC': { x: -330, y: 0, z: 350 }, // Spain (South Coast)
      'POR': { x: -450, y: 0, z: 350 },    // Portugal
      
      // Eastern Europe
      'WAR': { x: 100, y: 0, z: 0 },     // Warsaw
      'UKR': { x: 170, y: 0, z: 50 },    // Ukraine
      'LVN': { x: 150, y: 0, z: -200 },  // Livonia
      'MOS': { x: 250, y: 0, z: -100 },  // Moscow
      'SEV': { x: 300, y: 0, z: 100 },   // Sevastopol
      
      // Balkans
      'SER': { x: 150, y: 0, z: 180 },   // Serbia
      'ALB': { x: 130, y: 0, z: 230 },   // Albania
      'GRE': { x: 150, y: 0, z: 280 },   // Greece
      'BUL': { x: 200, y: 0, z: 200 },   // Bulgaria
      'BUL/EC': { x: 250, y: 0, z: 200 }, // Bulgaria (East Coast)
      'BUL/SC': { x: 200, y: 0, z: 230 }, // Bulgaria (South Coast)
      'RUM': { x: 200, y: 0, z: 150 },   // Rumania
      
      // Ottoman Empire
      'CON': { x: 250, y: 0, z: 250 },   // Constantinople
      'ANK': { x: 300, y: 0, z: 200 },   // Ankara
      'SMY': { x: 250, y: 0, z: 300 },   // Smyrna
      'ARM': { x: 350, y: 0, z: 150 },   // Armenia
      'SYR': { x: 350, y: 0, z: 250 },   // Syria
      
      // North Africa
      'TUN': { x: 50, y: 0, z: 400 },    // Tunisia
      'NAF': { x: -200, y: 0, z: 400 },  // North Africa
      
      // Seas
      'NAO': { x: -450, y: 0, z: -300 }, // North Atlantic Ocean
      'NWG': { x: -100, y: 0, z: -350 }, // Norwegian Sea
      'BAR': { x: 200, y: 0, z: -400 },  // Barents Sea
      'IRI': { x: -400, y: 0, z: -150 }, // Irish Sea
      'NTH': { x: -200, y: 0, z: -200 }, // North Sea
      'SKA': { x: 0, y: 0, z: -230 },    // Skagerrak
      'HEL': { x: -100, y: 0, z: -150 }, // Helgoland Bight
      'BAL': { x: 50, y: 0, z: -150 },   // Baltic Sea
      'BOT': { x: 100, y: 0, z: -250 },  // Gulf of Bothnia
      'ENG': { x: -270, y: 0, z: -20 },  // English Channel
      'MAO': { x: -450, y: 0, z: 200 },  // Mid-Atlantic Ocean
      'WES': { x: -100, y: 0, z: 350 },  // Western Mediterranean
      'LYO': { x: -150, y: 0, z: 250 },  // Gulf of Lyon
      'TYS': { x: 0, y: 0, z: 300 },     // Tyrrhenian Sea
      'ION': { x: 120, y: 0, z: 330 },   // Ionian Sea
      'ADR': { x: 80, y: 0, z: 200 },    // Adriatic Sea
      'AEG': { x: 200, y: 0, z: 300 },   // Aegean Sea
      'EAS': { x: 300, y: 0, z: 300 },   // Eastern Mediterranean
      'BLA': { x: 270, y: 0, z: 170 }    // Black Sea
    };

    // Ancient Mediterranean map coordinates (simplified)
    const ancmedMapCoordinates = {
      'ROM': { x: 0, y: 0, z: 0 },     // Rome
      'ATH': { x: 200, y: 0, z: 100 },  // Athens
      'CAR': { x: -100, y: 0, z: 150 }, // Carthage
      // ... more for ancmed
    };
    
    // Modern map coordinates (simplified)
    const modernMapCoordinates = {
      'WAS': { x: -300, y: 0, z: 0 },    // Washington
      'MOS': { x: 300, y: 0, z: -100 },  // Moscow
      'PEK': { x: 400, y: 0, z: 50 },    // Beijing
      // ... more for modern
    };
    
    // Pure map coordinates (simplified)
    const pureMapCoordinates = {
      'A1': { x: -300, y: 0, z: -300 },
      'B1': { x: -200, y: 0, z: -300 },
      'C1': { x: -100, y: 0, z: -300 },
      // ... more for pure
    };
    
    // Select the appropriate map coordinates based on map name
    const mapCoordinates = {
      standard: standardMapCoordinates,
      ancmed: ancmedMapCoordinates,
      modern: modernMapCoordinates,
      pure: pureMapCoordinates
    };
    
    // Set the coordinates for the specified map
    this.coordinates = mapCoordinates[this.mapName] || standardMapCoordinates;
    
    // Define sea provinces for standard map
    const seaProvinces = [
      'NAO', 'NWG', 'BAR', 'IRI', 'NTH', 'SKA', 'HEL', 'BAL', 'BOT',
      'ENG', 'MAO', 'WES', 'LYO', 'TYS', 'ION', 'ADR', 'AEG', 'EAS', 'BLA'
    ];
    
    // Define supply centers for standard map
    const supplyCenters = [
      'EDI', 'LVP', 'LON', 'PAR', 'BRE', 'MAR', 'KIE', 'BER', 'MUN', 
      'ROM', 'VEN', 'NAP', 'VIE', 'TRI', 'BUD', 'MOS', 'WAR', 'SEV', 
      'STP', 'ANK', 'CON', 'SMY', 'NWY', 'SWE', 'DEN', 'HOL', 'BEL', 
      'SPA', 'POR', 'TUN', 'SER', 'RUM', 'BUL', 'GRE'
    ];
    
    // Define coastal provinces that have special coast designations
    const coastalProvinces = {
      'SPA': ['NC', 'SC'],
      'STP': ['NC', 'SC'],
      'BUL': ['EC', 'SC']
    };
    
    // Generate detailed province data
    this.provinceData = {};
    
    // Process all coordinates
    for (const [province, position] of Object.entries(this.coordinates)) {
      // Skip special coast provinces, they will be handled with their base province
      if (province.includes('/')) continue;
      
      // Determine if it's a supply center
      const isSupplyCenter = supplyCenters.includes(province);
      
      // Determine province type
      let type = 'land';
      if (seaProvinces.includes(province)) {
        type = 'sea';
      } else if (coastalProvinces[province]) {
        type = 'coast';
      }
      
      // Create province data
      this.provinceData[province] = {
        position,
        isSupplyCenter,
        type,
        coasts: coastalProvinces[province] || []
      };
      
      // Add coast-specific positions if this is a coastal province
      if (coastalProvinces[province]) {
        this.provinceData[province].coastPositions = {};
        
        coastalProvinces[province].forEach(coast => {
          const coastKey = `${province}/${coast}`;
          if (this.coordinates[coastKey]) {
            this.provinceData[province].coastPositions[coast] = this.coordinates[coastKey];
          }
        });
      }
    }
  }

  /**
   * Get the 3D position for a location
   * @param {string} location - The location name (e.g. "LON", "PAR")
   * @returns {Object|null} The position as {x, y, z} or null if not found
   */
  getPositionForLocation(location) {
    if (!location) {
      console.warn(`[CoordinateMapper] Invalid location provided: ${location}`);
      return null;
    }
    
    // Trim and uppercase the location to standardize
    let normalizedLocation = location.trim().toUpperCase();
    
    // Handle both slash and underscore formats for coast locations
    // Convert slash format to underscore format for lookup
    if (normalizedLocation.includes('/')) {
      normalizedLocation = normalizedLocation.replace('/', '_');
    }
    
    // Direct lookup first
    if (this.coordinates[normalizedLocation]) {
      return { ...this.coordinates[normalizedLocation] };
    }
    
    // Try without coast designation
    const baseLocation = normalizedLocation.split('_')[0];
    if (baseLocation !== normalizedLocation && this.coordinates[baseLocation]) {
      console.log(`[CoordinateMapper] Using base location ${baseLocation} for ${normalizedLocation}`);
      return { ...this.coordinates[baseLocation] };
    }
    
    // For locations with coasts (e.g. "STP_SC"), check if we have a specific coast position
    if (normalizedLocation.includes('_')) {
      const parts = normalizedLocation.split('_');
      const baseLocationPart = parts[0];
      const coast = parts.slice(1).join('_'); // In case there are multiple underscores
      
      // Try different coast separator formats
      // Try slash format (STP/SC)
      const slashFormat = `${baseLocationPart}/${coast}`;
      if (this.coordinates[slashFormat]) {
        return { ...this.coordinates[slashFormat] };
      }
      
      // Check if we have province data with coast positions
      const provinceInfo = this.getProvinceInfo(baseLocationPart);
      if (provinceInfo && provinceInfo.coastPositions && provinceInfo.coastPositions[coast]) {
        return { ...provinceInfo.coastPositions[coast] };
      }
      
      // If we don't have a specific coast position, use the base province
      if (this.coordinates[baseLocationPart]) {
        console.log(`[CoordinateMapper] Falling back to base position for ${normalizedLocation}`);
        return { ...this.coordinates[baseLocationPart] };
      }
    }
    
    console.warn(`[CoordinateMapper] Location not found: ${location} (normalized: ${normalizedLocation})`);
    return null;
  }

  /**
   * Get province information
   * @param {string} location - The province name
   * @returns {Object|null} The province data or null if not found
   */
  getProvinceInfo(location) {
    if (!location) return null;
    
    let normalizedLocation = location.trim().toUpperCase();
    
    // Handle both slash and underscore formats
    if (normalizedLocation.includes('/')) {
      normalizedLocation = normalizedLocation.replace('/', '_');
    }
    
    // Get the base location (without coast designation)
    const baseLocation = normalizedLocation.split('_')[0];
    
    // First try with the full normalized location
    if (this.provinceData[normalizedLocation]) {
      return { ...this.provinceData[normalizedLocation] };
    }
    
    // Then try with the base location (no coast)
    if (this.provinceData[baseLocation]) {
      return { ...this.provinceData[baseLocation] };
    }
    
    // Try with slash format instead of underscore
    if (normalizedLocation.includes('_')) {
      const slashFormat = normalizedLocation.replace('_', '/');
      if (this.provinceData[slashFormat]) {
        return { ...this.provinceData[slashFormat] };
      }
    }
    
    console.log(`[CoordinateMapper] Province info not found for: ${location}`);
    return null;
  }

  /**
   * Check if a province is a supply center
   * @param {string} location - The province name
   * @returns {boolean} Whether the province is a supply center
   */
  isSupplyCenter(location) {
    const info = this.getProvinceInfo(location);
    return info ? info.isSupplyCenter : false;
  }

  /**
   * Get the type of a province (land, sea)
   * @param {string} location - The province name
   * @returns {string|null} The province type or null if not found
   */
  getProvinceType(location) {
    const info = this.getProvinceInfo(location);
    return info ? info.type : null;
  }

  /**
   * Get all available locations
   * @returns {string[]} An array of all location names
   */
  getAllLocations() {
    return Object.keys(this.coordinates);
  }

  /**
   * Calculate the midpoint between two locations, for animations
   * @param {string} location1 - The first location
   * @param {string} location2 - The second location
   * @returns {Object|null} The midpoint as {x, y, z} or null if either location not found
   */
  getMidpoint(location1, location2) {
    const pos1 = this.getPositionForLocation(location1);
    const pos2 = this.getPositionForLocation(location2);
    
    if (!pos1 || !pos2) return null;
    
    return {
      x: (pos1.x + pos2.x) / 2,
      y: (pos1.y + pos2.y) / 2 + 30, // Add some height for arcing movement
      z: (pos1.z + pos2.z) / 2
    };
  }

  /**
   * Check if a province has specific coasts
   * @param {string} location - The province name
   * @returns {string[]|null} Array of coast codes or null if not a coastal province
   */
  getProvinceCoasts(location) {
    const info = this.getProvinceInfo(location);
    return info && info.coasts ? [...info.coasts] : null;
  }

  /**
   * Check if a location is a valid coast of a province
   * @param {string} location - The full location with coast (e.g. "SPA/NC")
   * @returns {boolean} Whether the coast is valid
   */
  isValidCoast(location) {
    if (!location.includes('/')) return false;
    
    const [province, coast] = location.split('/');
    const coasts = this.getProvinceCoasts(province);
    
    return coasts ? coasts.includes(coast) : false;
  }

  /**
   * Get adjacent provinces for a given province
   * @param {string} location - The province name
   * @returns {string[]} Array of adjacent provinces
   */
  getAdjacentProvinces(location) {
    const baseLocation = location.split('/')[0];
    
    // This is a partial adjacency list for the standard map
    // In a full implementation, this would be loaded from a configuration file
    const adjacencyList = {
      // Western Europe
      'BRE': ['PAR', 'PIC', 'ENG', 'MAO', 'GAS'],
      'PAR': ['BRE', 'PIC', 'BUR', 'GAS'],
      'PIC': ['BRE', 'PAR', 'BUR', 'BEL', 'ENG'],
      'BUR': ['PAR', 'PIC', 'BEL', 'RUH', 'MUN', 'MAR', 'GAS'],
      'GAS': ['BRE', 'PAR', 'BUR', 'MAR', 'SPA', 'MAO'],
      'MAR': ['GAS', 'BUR', 'PIE', 'LYO', 'SPA'],
      'BEL': ['PIC', 'BUR', 'RUH', 'HOL', 'NTH', 'ENG'],
      'RUH': ['BEL', 'BUR', 'MUN', 'KIE', 'HOL'],
      'HOL': ['BEL', 'RUH', 'KIE', 'HEL', 'NTH'],
      
      // Great Britain
      'LON': ['YOR', 'WAL', 'ENG', 'NTH'],
      'YOR': ['LON', 'WAL', 'EDI', 'NTH'],
      'EDI': ['YOR', 'CLY', 'NTH', 'NWG'],
      'LVP': ['WAL', 'YOR', 'EDI', 'CLY', 'IRI', 'NAO'],
      'WAL': ['LON', 'YOR', 'LVP', 'IRI', 'ENG'],
      'CLY': ['EDI', 'LVP', 'NAO', 'NWG'],
      
      // Northern Europe
      'NWY': ['NTH', 'NWG', 'BAR', 'STP', 'FIN', 'SKA', 'SWE'],
      'SWE': ['NWY', 'FIN', 'BOT', 'BAL', 'DEN', 'SKA'],
      'DEN': ['HEL', 'BAL', 'SKA', 'SWE', 'KIE', 'NTH'],
      'FIN': ['NWY', 'STP', 'BOT', 'SWE'],
      
      // Central Europe
      'KIE': ['DEN', 'BAL', 'BER', 'MUN', 'RUH', 'HOL', 'HEL'],
      'BER': ['KIE', 'BAL', 'PRU', 'SIL', 'MUN'],
      'MUN': ['KIE', 'BER', 'SIL', 'BOH', 'TYR', 'BUR', 'RUH'],
      'SIL': ['MUN', 'BER', 'PRU', 'WAR', 'GAL', 'BOH'],
      'BOH': ['MUN', 'SIL', 'GAL', 'VIE', 'TYR'],
      'TYR': ['MUN', 'BOH', 'VIE', 'TRI', 'VEN', 'PIE'],
      'VIE': ['TYR', 'BOH', 'GAL', 'BUD', 'TRI'],
      'BUD': ['VIE', 'GAL', 'RUM', 'SER', 'TRI'],
      'TRI': ['VEN', 'TYR', 'VIE', 'BUD', 'SER', 'ALB', 'ADR'],
      'GAL': ['BOH', 'SIL', 'WAR', 'UKR', 'RUM', 'BUD', 'VIE'],
      
      // Eastern Europe
      'WAR': ['PRU', 'SIL', 'GAL', 'UKR', 'LVN'],
      'MOS': ['STP', 'LVN', 'UKR', 'SEV'],
      'UKR': ['WAR', 'GAL', 'RUM', 'SEV', 'MOS'],
      'LVN': ['PRU', 'BAL', 'BOT', 'STP', 'MOS', 'WAR'],
      'STP': ['BAR', 'NWY', 'FIN', 'BOT', 'LVN', 'MOS'],
      'STP/NC': ['BAR', 'NWY'],
      'STP/SC': ['FIN', 'BOT', 'LVN'],
      'SEV': ['UKR', 'RUM', 'BLA', 'ARM', 'MOS'],
      
      // Italy
      'PIE': ['MAR', 'TYR', 'VEN', 'TUS', 'LYO'],
      'VEN': ['PIE', 'TYR', 'TRI', 'ADR', 'APU', 'ROM', 'TUS'],
      'TUS': ['PIE', 'VEN', 'ROM', 'LYO', 'TYS'],
      'ROM': ['TUS', 'VEN', 'APU', 'NAP', 'TYS'],
      'NAP': ['ROM', 'APU', 'ION', 'TYS'],
      'APU': ['VEN', 'ADR', 'ION', 'NAP', 'ROM'],
      
      // Balkans
      'ALB': ['TRI', 'SER', 'GRE', 'ION', 'ADR'],
      'SER': ['TRI', 'BUD', 'RUM', 'BUL', 'GRE', 'ALB'],
      'GRE': ['ALB', 'SER', 'BUL', 'AEG', 'ION'],
      'BUL': ['SER', 'RUM', 'BLA', 'CON', 'AEG', 'GRE'],
      'BUL/EC': ['BLA', 'CON'],
      'BUL/SC': ['AEG', 'CON'],
      'RUM': ['GAL', 'UKR', 'SEV', 'BLA', 'BUL', 'SER', 'BUD'],
      
      // Ottoman Empire
      'CON': ['BUL', 'BLA', 'ANK', 'SMY', 'AEG'],
      'ANK': ['BLA', 'ARM', 'SMY', 'CON'],
      'SMY': ['CON', 'ANK', 'ARM', 'SYR', 'EAS', 'AEG'],
      'ARM': ['SEV', 'BLA', 'ANK', 'SMY', 'SYR'],
      'SYR': ['ARM', 'SMY', 'EAS'],
      
      // North Africa
      'TUN': ['NAF', 'WES', 'TYS', 'ION'],
      'NAF': ['MAO', 'WES', 'TUN'],
      
      // Iberian Peninsula
      'SPA': ['GAS', 'MAR', 'LYO', 'WES', 'MAO', 'POR'],
      'SPA/NC': ['GAS', 'MAO', 'POR'],
      'SPA/SC': ['MAR', 'LYO', 'WES', 'MAO'],
      'POR': ['SPA', 'MAO'],
      
      // Seas
      'NAO': ['MAO', 'IRI', 'LVP', 'CLY', 'NWG'],
      'NWG': ['NAO', 'CLY', 'EDI', 'NTH', 'NWY', 'BAR'],
      'BAR': ['NWG', 'NWY', 'STP', 'STP/NC'],
      'IRI': ['NAO', 'MAO', 'ENG', 'WAL', 'LVP'],
      'NTH': ['ENG', 'BEL', 'HOL', 'HEL', 'DEN', 'SKA', 'NWY', 'EDI', 'YOR', 'LON'],
      'SKA': ['NTH', 'DEN', 'SWE', 'NWY'],
      'HEL': ['NTH', 'DEN', 'KIE', 'HOL'],
      'BAL': ['DEN', 'KIE', 'BER', 'PRU', 'LVN', 'BOT', 'SWE'],
      'BOT': ['BAL', 'SWE', 'FIN', 'STP', 'STP/SC', 'LVN'],
      'ENG': ['IRI', 'WAL', 'LON', 'NTH', 'BEL', 'PIC', 'BRE', 'MAO'],
      'MAO': ['NAO', 'IRI', 'ENG', 'BRE', 'GAS', 'SPA', 'SPA/NC', 'SPA/SC', 'POR', 'NAF', 'WES'],
      'WES': ['MAO', 'SPA', 'SPA/SC', 'LYO', 'TYS', 'TUN', 'NAF'],
      'LYO': ['SPA', 'SPA/SC', 'MAR', 'PIE', 'TUS', 'TYS', 'WES'],
      'TYS': ['LYO', 'TUS', 'ROM', 'NAP', 'ION', 'TUN', 'WES'],
      'ION': ['TYS', 'NAP', 'APU', 'ADR', 'ALB', 'GRE', 'AEG', 'EAS', 'TUN'],
      'ADR': ['VEN', 'TRI', 'ALB', 'ION', 'APU'],
      'AEG': ['GRE', 'BUL', 'BUL/SC', 'CON', 'SMY', 'EAS', 'ION'],
      'EAS': ['ION', 'AEG', 'SMY', 'SYR'],
      'BLA': ['RUM', 'SEV', 'ARM', 'ANK', 'CON', 'BUL', 'BUL/EC']
    };
    
    return adjacencyList[baseLocation] || [];
  }

  /**
   * Check if two provinces are adjacent
   * @param {string} location1 - First province
   * @param {string} location2 - Second province
   * @returns {boolean} Whether the provinces are adjacent
   */
  areAdjacent(location1, location2) {
    const baseLocation1 = location1.split('/')[0];
    const baseLocation2 = location2.split('/')[0];
    
    // For provinces with coasts, first check if base provinces are adjacent
    if (baseLocation1 !== location1 || baseLocation2 !== location2) {
      // For coast-specific adjacency, we need to check special cases
      
      // Special case: St. Petersburg north coast only connects to Barents Sea,
      // while south coast connects to Gulf of Bothnia and Livonia
      if (location1 === 'STP/NC' && location2 === 'BOT') return false;
      if (location1 === 'STP/SC' && location2 === 'BAR') return false;
      if (location2 === 'STP/NC' && location1 === 'BOT') return false;
      if (location2 === 'STP/SC' && location1 === 'BAR') return false;
      
      // Similar special cases for Spain and Bulgaria coasts
      // ...
    }
    
    const adjacent = this.getAdjacentProvinces(baseLocation1);
    return adjacent.includes(baseLocation2);
  }

  /**
   * Calculate a path of positions between two locations
   * @param {string} fromLocation - The starting location
   * @param {string} toLocation - The destination location
   * @param {number} steps - The number of points to generate
   * @param {number} arcHeight - The height of the arc in the y-direction
   * @returns {THREE.Vector3[]|null} Array of THREE.Vector3 positions or null if either location not found
   */
  getPathBetween(fromLocation, toLocation, steps = 10, arcHeight = 30) {
    const startPos = this.getPositionForLocation(fromLocation);
    const endPos = this.getPositionForLocation(toLocation);
    
    if (!startPos || !endPos) return null;
    
    const path = [];
    
    // Determine path type based on province types
    const fromType = this.getProvinceType(fromLocation.split('/')[0]);
    const toType = this.getProvinceType(toLocation.split('/')[0]);
    
    // Higher arc for land movement, flatter for sea movement
    const actualArcHeight = (fromType === 'sea' && toType === 'sea') ? 
      arcHeight / 3 : arcHeight;
    
    // Import THREE if needed
    const THREE = window.THREE || (typeof global !== 'undefined' ? global.THREE : null);
    if (!THREE) {
      console.error('[CoordinateMapper] THREE.js not available');
      return null;
    }
    
    // Add intermediate points for better path
    if (this.areAdjacent(fromLocation, toLocation)) {
      // Direct path for adjacent provinces
      for (let i = 0; i <= steps; i++) {
        const t = i / steps;
        
        // Interpolate x and z linearly
        const x = startPos.x + (endPos.x - startPos.x) * t;
        const z = startPos.z + (endPos.z - startPos.z) * t;
        
        // Add an arc in the y direction using a sin curve
        // sin(π * t) gives a nice arc that starts and ends at 0
        const y = startPos.y + (endPos.y - startPos.y) * t + Math.sin(Math.PI * t) * actualArcHeight;
        
        // Create a THREE.Vector3 object
        path.push(new THREE.Vector3(x, y, z));
      }
    } else {
      // For non-adjacent provinces, try to find a path through adjacent provinces
      // This is a simplified approach; in a real implementation, you'd use a pathfinding algorithm
      
      // Just create a direct path for now, but with a higher arc
      for (let i = 0; i <= steps; i++) {
        const t = i / steps;
        
        // Interpolate x and z linearly
        const x = startPos.x + (endPos.x - startPos.x) * t;
        const z = startPos.z + (endPos.z - startPos.z) * t;
        
        // Add a higher arc for longer paths
        const y = startPos.y + (endPos.y - startPos.y) * t + Math.sin(Math.PI * t) * (actualArcHeight * 2);
        
        // Create a THREE.Vector3 object
        path.push(new THREE.Vector3(x, y, z));
      }
    }
    
    return path;
  }
} 