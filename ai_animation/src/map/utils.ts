import { gameState } from "../gameState";

export function getProvincePosition(loc: string) {
  // Convert e.g. "Spa/sc" to "SPA_SC" if needed
  const normalized = loc.toUpperCase().replace('/', '_');
  const base = normalized.split('_')[0];
  let coordinateData = gameState.boardState

  if (coordinateData.provinces[normalized]) {
    return {
      "x": coordinateData.provinces[normalized].label.x,
      "y": 10,
      "z": coordinateData.provinces[normalized].label.y
    };
  }
  if (coordinateData.provinces[base]) {
    return {
      "x": coordinateData.provinces[base].label.x,
      "y": 10,
      "z": coordinateData.provinces[base].label.y
    };
  }
  throw new Error(`Couldn't find province with name ${normalized} or ${base} in the provinces array`)

}
