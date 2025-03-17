# Map Assets for Diplomacy Animation

This directory contains the map assets used by the 3D animation system.

## Files Required for Each Map Variant

For each map variant (e.g., standard, ancmed, modern, pure), the following files are needed:

1. `[variant].svg` - The main SVG map (shows country boundaries)
2. `[variant]_map.jpg` - A fallback JPG map texture 
3. `[variant]_coords.json` - JSON file with province coordinates for 3D positioning

## Coordinate Format

The coordinate JSON files should have the following structure:

```json
{
  "mapWidth": 1000,
  "mapHeight": 1000,
  "coordinates": {
    "LON": { "x": -300, "y": 0, "z": -100 },
    "PAR": { "x": -250, "y": 0, "z": 100 },
    ...
  },
  "provinces": {
    "LON": { "isSupplyCenter": true, "type": "land" },
    "PAR": { "isSupplyCenter": true, "type": "land" },
    "MAO": { "isSupplyCenter": false, "type": "sea" },
    "STP": { "isSupplyCenter": true, "type": "land", "coasts": ["NC", "SC"] },
    ...
  }
}
```

### Coordinates

- The origin (0,0,0) is the center of the map
- The x-axis runs horizontally (negative = west, positive = east)
- The y-axis is for elevation (0 = sea level, positive = up)
- The z-axis runs vertically (negative = north, positive = south)

### Special Coast Notation

For provinces with multiple coasts (like St. Petersburg), coast positions should be defined:

1. In coordinates section using underscore notation:
   - `"STP_NC": { "x": 200, "y": 0, "z": -350 }`

2. In provinces section using the coasts array:
   - `"STP": { "isSupplyCenter": true, "type": "land", "coasts": ["NC", "SC"] }`