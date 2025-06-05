import { PowerENUM } from '../types/map';
import { gameState } from '../gameState';

/**
 * Resolves a power name for display purposes.
 * If model names are available in moments data for the current game, uses those.
 * Otherwise falls back to the PowerENUM value.
 * 
 * @param power - The PowerENUM value to resolve
 * @returns The display name for the power
 */
export function getPowerDisplayName(power: PowerENUM | string): string {
  // Convert string to PowerENUM if needed
  const powerEnum = typeof power === 'string' ? power.toUpperCase() as PowerENUM : power;

  // Special handling for GLOBAL and EUROPE which aren't models
  if (powerEnum === PowerENUM.GLOBAL || powerEnum === PowerENUM.EUROPE) {
    return powerEnum;
  }

  // Check if we have moments data with power_models for the current game
  if (gameState.momentsData?.power_models && powerEnum in gameState.momentsData.power_models) {
    const modelName = gameState.momentsData.power_models[powerEnum];
    if (modelName) {
      // Remove the extra long parts of some of the model names e.g. openroute-meta/llama-4-maverick -> llama-4-maverick
      let slashIdx = modelName?.indexOf("/")
      if (slashIdx >= 0) {
        return modelName.slice(slashIdx + 1, modelName.length)
      }
      return modelName;
    }
  }

  // Fall back to the PowerENUM value
  return powerEnum;
}

/**
 * Gets all power display names as an array.
 * Useful for creating UI elements that need to iterate over all powers.
 * 
 * @returns Array of power display names in the standard order
 */
export function getAllPowerDisplayNames(): string[] {
  const standardPowers = [
    PowerENUM.AUSTRIA,
    PowerENUM.ENGLAND,
    PowerENUM.FRANCE,
    PowerENUM.GERMANY,
    PowerENUM.ITALY,
    PowerENUM.RUSSIA,
    PowerENUM.TURKEY
  ];

  return standardPowers.map(power => getPowerDisplayName(power));
}

/**
 * Gets a mapping from PowerENUM to display names.
 * Useful for configurations that need both the enum value and display name.
 * 
 * @returns Object mapping PowerENUM values to display names
 */
export function getPowerDisplayNameMapping(): Record<PowerENUM, string> {
  const mapping: Record<PowerENUM, string> = {} as Record<PowerENUM, string>;

  Object.values(PowerENUM).forEach(power => {
    mapping[power] = getPowerDisplayName(power);
  });

  return mapping;
}
