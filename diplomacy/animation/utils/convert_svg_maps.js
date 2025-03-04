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
 * Map Conversion Utility
 * 
 * This script extracts province coordinates, supply centers and other data
 * from existing SVG map files and prepares them for use with the Three.js
 * animation system.
 * 
 * Usage:
 *   node convert_svg_maps.js <map_name> [output_dir]
 * 
 * Where:
 *   <map_name> is one of: standard, ancmed, modern, pure
 *   [output_dir] is an optional output directory (defaults to ../assets/maps/)
 * 
 * This will:
 *   1. Load the SVG map file from the maps directory
 *   2. Extract province data (positions, borders, etc.)
 *   3. Generate a texture map (high-res JPG)
 *   4. Create a coordinate file (JSON)
 *   5. Save both to the output directory
 */

const fs = require('fs');
const path = require('path');
const { createCanvas, loadImage } = require('canvas');
const { DOMParser } = require('xmldom');
const { optimize } = require('svgo');

// Map sources - adjust these paths for your codebase
const MAP_SOURCES = {
  standard: '../../maps/svg/standard.svg',
  ancmed: '../../maps/svg/ancmed.svg',
  modern: '../../maps/svg/modern.svg',
  pure: '../../maps/svg/pure.svg'
};

// Supply centers for standard map (others will be determined from SVG)
const SUPPLY_CENTERS = {
  standard: [
    'EDI', 'LVP', 'LON', 'BRE', 'PAR', 'MAR', 'SPA', 'POR', 'BEL', 'HOL', 'DEN',
    'NWY', 'SWE', 'KIE', 'BER', 'MUN', 'VEN', 'ROM', 'NAP', 'TUN', 'VIE', 'BUD',
    'TRI', 'SER', 'RUM', 'BUL', 'GRE', 'ANK', 'SMY', 'CON', 'SEV', 'WAR', 'MOS', 'STP'
  ],
  ancmed: [], // Will be extracted from SVG
  modern: [], // Will be extracted from SVG
  pure: []    // Will be extracted from SVG
};

// Map dimensions in 3D space
const MAP_DIMENSIONS = {
  standard: { width: 1000, height: 1000 },
  ancmed: { width: 1000, height: 1000 },
  modern: { width: 1000, height: 1000 },
  pure: { width: 1000, height: 1000 }
};

/**
 * Main function
 */
async function main() {
  // Parse command line arguments
  const args = process.argv.slice(2);
  const mapName = args[0]?.toLowerCase();
  const outputDir = args[1] || path.join(__dirname, '../assets/maps');
  
  // Validate map name
  if (!mapName || !MAP_SOURCES[mapName]) {
    console.error('Error: Invalid map name');
    console.error('Usage: node convert_svg_maps.js <map_name> [output_dir]');
    console.error('  where <map_name> is one of: standard, ancmed, modern, pure');
    process.exit(1);
  }
  
  // Create output directory if it doesn't exist
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }
  
  console.log(`Converting map: ${mapName}`);
  
  try {
    // Extract SVG data
    const svgData = await extractSvgFromSource(mapName);
    
    // Generate texture map
    await generateTextureMap(svgData, mapName, outputDir);
    
    // Generate coordinate file
    await generateCoordinateFile(svgData, mapName, outputDir);
    
    console.log('Conversion complete!');
  } catch (error) {
    console.error('Error during conversion:', error);
    process.exit(1);
  }
}

/**
 * Extract SVG data from source file
 * @param {string} mapName - The map name
 * @returns {Object} - SVG DOM and metadata
 */
async function extractSvgFromSource(mapName) {
  const sourcePath = path.join(__dirname, MAP_SOURCES[mapName]);
  
  console.log(`Reading SVG from: ${sourcePath}`);
  
  // Read SVG file
  const svgContent = fs.readFileSync(sourcePath, 'utf8');
  
  // Parse SVG
  const parser = new DOMParser();
  const svgDoc = parser.parseFromString(svgContent, 'image/svg+xml');
  
  // Get SVG dimensions
  const svgElement = svgDoc.documentElement;
  const viewBox = svgElement.getAttribute('viewBox')?.split(' ').map(Number) || [0, 0, 800, 600];
  const width = parseInt(svgElement.getAttribute('width') || viewBox[2], 10);
  const height = parseInt(svgElement.getAttribute('height') || viewBox[3], 10);
  
  return {
    doc: svgDoc,
    content: svgContent,
    width,
    height,
    viewBox
  };
}

/**
 * Generate texture map from SVG
 * @param {Object} svgData - SVG data
 * @param {string} mapName - Map name
 * @param {string} outputDir - Output directory
 */
async function generateTextureMap(svgData, mapName, outputDir) {
  console.log('Generating texture map...');
  
  // Optimize SVG for rendering
  const optimizedSvg = optimize(svgData.content, {
    multipass: true,
    plugins: [
      'removeViewBox',
      'removeDimensions',
      'removeUnknownsAndDefaults',
      'removeUselessStrokeAndFill',
      'mergeStyles',
      'inlineStyles'
    ]
  }).data;
  
  // Set output dimensions (high resolution for texture)
  const outputWidth = 2048;
  const outputHeight = Math.round((svgData.height / svgData.width) * outputWidth);
  
  // Create canvas
  const canvas = createCanvas(outputWidth, outputHeight);
  const ctx = canvas.getContext('2d');
  
  // Fill background
  ctx.fillStyle = '#E6EBF4'; // Light blue-gray background
  ctx.fillRect(0, 0, outputWidth, outputHeight);
  
  // Load and draw the SVG
  const image = await loadSvgToImage(optimizedSvg, outputWidth, outputHeight);
  ctx.drawImage(image, 0, 0, outputWidth, outputHeight);
  
  // Save as JPEG
  const outputPath = path.join(outputDir, `${mapName}_map.jpg`);
  const out = fs.createWriteStream(outputPath);
  const stream = canvas.createJPEGStream({ quality: 0.9 });
  stream.pipe(out);
  
  await new Promise((resolve, reject) => {
    out.on('finish', resolve);
    out.on('error', reject);
  });
  
  console.log(`Texture map saved to: ${outputPath}`);
}

/**
 * Load SVG to Image
 * @param {string} svg - SVG content
 * @param {number} width - Target width
 * @param {number} height - Target height
 * @returns {Promise<Image>} - Image object
 */
async function loadSvgToImage(svg, width, height) {
  // Create a data URL from the SVG
  const dataUrl = `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`;
  
  // Load the image
  const image = await loadImage(dataUrl);
  return image;
}

/**
 * Generate coordinate file from SVG
 * @param {Object} svgData - SVG data
 * @param {string} mapName - Map name
 * @param {string} outputDir - Output directory
 */
async function generateCoordinateFile(svgData, mapName, outputDir) {
  console.log('Extracting coordinate data...');
  
  const svgDoc = svgData.doc;
  const viewBox = svgData.viewBox;
  const mapDimensions = MAP_DIMENSIONS[mapName];
  
  // Result object
  const coordinateData = {
    name: mapName,
    dimensions: mapDimensions,
    provinces: {}
  };
  
  // Extract province elements
  const provinces = findProvinceElements(svgDoc, mapName);
  
  // Process each province
  for (const [province, element] of Object.entries(provinces)) {
    // Get province center/position
    const position = calculateProvinceCenter(element, viewBox, mapDimensions);
    
    // Determine if it's a supply center
    const isSupplyCenter = SUPPLY_CENTERS[mapName].includes(province);
    
    // Determine province type (sea, land, coast)
    const type = determineProvinceType(element, province);
    
    // Add to coordinate data
    coordinateData.provinces[province] = {
      position,
      isSupplyCenter,
      type
    };
  }
  
  // Save coordinate data as JSON
  const outputPath = path.join(outputDir, `${mapName}_coords.json`);
  fs.writeFileSync(outputPath, JSON.stringify(coordinateData, null, 2));
  
  console.log(`Coordinate data saved to: ${outputPath}`);
  console.log(`Extracted ${Object.keys(coordinateData.provinces).length} provinces`);
}

/**
 * Find province elements in the SVG
 * @param {Document} svgDoc - SVG Document
 * @param {string} mapName - Map name
 * @returns {Object} - Map of province ID to element
 */
function findProvinceElements(svgDoc, mapName) {
  const provinces = {};
  
  // Different maps have different conventions for province elements
  let elements;
  
  switch (mapName) {
    case 'standard':
      // Standard map typically has provinces as specific elements with IDs
      elements = svgDoc.getElementsByTagName('path');
      for (let i = 0; i < elements.length; i++) {
        const element = elements[i];
        const id = element.getAttribute('id');
        
        // Check if this is a province ID (usually uppercase, 3 letters)
        if (id && /^[A-Z]{3}(_[NS]C)?$/.test(id)) {
          const baseId = id.split('_')[0]; // Handle coast variants
          provinces[baseId] = element;
        }
      }
      break;
      
    case 'ancmed':
    case 'modern':
    case 'pure':
      // For other maps, we'd need to adapt the extraction logic
      // This is a placeholder - actual implementation would depend on the SVG structure
      elements = svgDoc.getElementsByTagName('g');
      for (let i = 0; i < elements.length; i++) {
        const element = elements[i];
        const id = element.getAttribute('id');
        
        if (id && (id.includes('province') || id.includes('territory'))) {
          // Extract province code from the element or its children
          const label = findProvinceLabel(element);
          if (label) {
            provinces[label] = element;
          }
        }
      }
      break;
  }
  
  return provinces;
}

/**
 * Find province label in an element or its children
 * @param {Element} element - SVG element
 * @returns {string|null} - Province label or null
 */
function findProvinceLabel(element) {
  // This would need to be adapted based on the specific SVG structure
  // For now, return a placeholder
  return element.getAttribute('data-province') || element.getAttribute('id');
}

/**
 * Calculate center position of a province
 * @param {Element} element - SVG element
 * @param {number[]} viewBox - SVG viewBox
 * @param {Object} mapDimensions - Target map dimensions
 * @returns {Object} - Position as {x, y, z}
 */
function calculateProvinceCenter(element, viewBox, mapDimensions) {
  // Get the bounding box of the element
  const bbox = element.getBBox();
  
  // Calculate center in SVG coordinates
  const centerX = bbox.x + bbox.width / 2;
  const centerY = bbox.y + bbox.height / 2;
  
  // Map to 3D coordinates
  // SVG coordinate system has origin at top-left, Y increases downward
  // 3D coordinate system for our map has origin at center, Y is up, Z is depth
  
  // Normalize to 0-1 range based on viewBox
  const normalizedX = (centerX - viewBox[0]) / viewBox[2];
  const normalizedY = (centerY - viewBox[1]) / viewBox[3];
  
  // Map to 3D space (X: -halfWidth to halfWidth, Z: -halfHeight to halfHeight)
  const halfWidth = mapDimensions.width / 2;
  const halfHeight = mapDimensions.height / 2;
  
  return {
    x: (normalizedX * mapDimensions.width) - halfWidth,
    y: 0, // Flat map at y=0
    z: (normalizedY * mapDimensions.height) - halfHeight
  };
}

/**
 * Determine the type of province (sea, land, coast)
 * @param {Element} element - SVG element
 * @param {string} province - Province ID
 * @returns {string} - Province type
 */
function determineProvinceType(element, province) {
  // Based on typical conventions in Diplomacy maps
  
  // Check element class or style for hints
  const className = element.getAttribute('class') || '';
  const style = element.getAttribute('style') || '';
  
  if (className.includes('water') || className.includes('sea') || style.includes('fill:blue')) {
    return 'sea';
  }
  
  // If we can't determine from element, use heuristics based on province code
  
  // Most sea spaces in standard map are 3-letter codes
  const seaSpaces = [
    'NAO', 'MAO', 'IRI', 'ENG', 'NTH', 'HEL', 'SKA', 'BAL', 'BOT', 'BAR',
    'NWG', 'WES', 'LYO', 'TYS', 'ADR', 'ION', 'AEG', 'EAS', 'BLA'
  ];
  
  if (seaSpaces.includes(province)) {
    return 'sea';
  }
  
  // Default to land
  return 'land';
}

// Run the main function
if (require.main === module) {
  main().catch(console.error);
}

module.exports = {
  convertMap: main,
  extractSvgFromSource,
  generateTextureMap,
  generateCoordinateFile
}; 