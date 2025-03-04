# Map Assets for Diplomacy Animation

This directory contains map textures and coordinate data for the Diplomacy animation system.

## Supported Map Variants

The animation system supports the following map variants:

- **standard**: Standard Diplomacy map (The classic 1901 map with 7 great powers)
- **ancmed**: Ancient Mediterranean map
- **modern**: Modern world map
- **pure**: Pure abstract map (for testing and simple games)

## Files for Each Map Variant

Each map variant should have two files:

1. `[variant]_map.jpg` - The texture map (high resolution image)
2. `[variant]_coords.json` - The coordinate data for provinces

## Texture Files

Texture files should be high-resolution JPEG or PNG images. The recommended resolution is 2048x2048 or higher, with a 1:1 aspect ratio.

## Coordinate Files

Each map variant requires a JSON file with the following structure:

```json
{
  "name": "standard",
  "dimensions": {
    "width": 1000,
    "height": 1000
  },
  "provinces": {
    "LON": {
      "position": { "x": -300, "y": 0, "z": -150 },
      "isSupplyCenter": true,
      "type": "land"
    },
    "NTH": {
      "position": { "x": -200, "y": 0, "z": -250 },
      "isSupplyCenter": false,
      "type": "sea"
    },
    // ... more provinces
  }
}
```

The `position` values map to 3D coordinates in the Three.js scene. The origin (0,0,0) is at the center of the map, with:
- **x**: left (-) to right (+)
- **y**: down (-) to up (+), typically 0 for the map surface
- **z**: top (-) to bottom (+) when viewing from above

## Generating Maps from SVG

You can use the included utility script to generate maps and coordinate files from SVG sources:

```
node diplomacy/animation/utils/convert_svg_maps.js <map_name> [output_dir]
```

Where:
- `<map_name>` is one of: standard, ancmed, modern, pure
- `[output_dir]` is an optional output directory (defaults to this directory)

## Manual Configuration

If you need to adjust coordinates manually, edit the coordinate JSON file. For example:

1. If a province is positioned incorrectly, adjust its x/z values
2. If you need to mark a territory as a supply center, set `isSupplyCenter` to true
3. To change whether a province is land or sea, set the `type` property

After making changes, refresh the map in the animation player to see the updates. 