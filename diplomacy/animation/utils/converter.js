/**
 * Utility functions for converting between different diplomacy game file formats
 */

/**
 * Convert AI Diplomacy results format to animation format
 * @param {Object} resultsData - Results data from AI Diplomacy
 * @returns {Object} Formatted game data compatible with the animation system
 */
export function convertResultsToAnimationFormat(resultsData) {
  // Create a base game data structure
  const gameData = {
    map_name: "standard",
    game_id: resultsData.game_id || "ai-diplomacy-game",
    phases: []
  };
  
  // Extract phases from the results data
  if (resultsData.rounds && Array.isArray(resultsData.rounds)) {
    console.log(`Processing ${resultsData.rounds.length} rounds from results file`);
    
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
              const regionMatch = order.match(/^[AF]\s+([A-Za-z_/]+)/);
              const region = regionMatch ? regionMatch[1] : "";
              
              // Standardize the order format
              let standardizedOrder = order;
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
  
  return gameData;
}

/**
 * Detect the format of a game file and convert it if needed
 * @param {Object} data - The loaded game data
 * @returns {Object} Game data in the correct format for animation
 */
export function processGameFile(data) {
  // Detect if this is a results file or a standard game file
  if (data.rounds && Array.isArray(data.rounds)) {
    // This appears to be a results file, convert it
    console.log('Detected results file format, converting...');
    return convertResultsToAnimationFormat(data);
  } 
  
  // Standard game file format with phases array
  if (data.phases && Array.isArray(data.phases)) {
    console.log('Standard game format detected');
    return data;
  }
  
  // Legacy format with state_history
  if (data.state_history) {
    console.log('Legacy format detected (state_history)');
    // Convert to standard format
    const convertedData = {
      map_name: data.map_name || 'standard',
      game_id: data.game_id || 'legacy-game',
      phases: []
    };
    
    // Extract phases from state_history
    const stateHistory = data.state_history;
    const orderHistory = data.order_history || {};
    const resultHistory = data.result_history || {};
    
    const phases = [];
    
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
    
    convertedData.phases = phases;
    return convertedData;
  }
  
  // Unknown format
  console.warn('Unknown game file format');
  return data;
}