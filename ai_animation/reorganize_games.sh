#!/bin/bash

# Navigate to the games directory
cd "public/games" || exit 1

# Initialize counter
counter=0

# Process each directory (excluding files)
for dir in */; do
    # Remove trailing slash from directory name
    dir_name="${dir%/}"
    
    # Skip if it's not a directory or if it's a numeric directory (already processed)
    if [[ ! -d "$dir_name" ]] || [[ "$dir_name" =~ ^[0-9]+$ ]]; then
        continue
    fi
    
    echo "Processing: $dir_name"
    
    # Create empty file with same name as directory in parent directory
    touch "../$dir_name"
    
    # Check if lmvsgame.json exists and rename it to game.json
    if [[ -f "$dir_name/lmvsgame.json" ]]; then
        mv "$dir_name/lmvsgame.json" "$dir_name/game.json"
        echo "  Renamed lmvsgame.json to game.json"
    fi
    
    # Rename directory to integer
    mv "$dir_name" "$counter"
    echo "  Renamed directory to: $counter"
    
    # Increment counter
    ((counter++))
done

echo "Reorganization complete. Processed $counter directories."