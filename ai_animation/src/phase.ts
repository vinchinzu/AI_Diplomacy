import { gameState } from "./gameState";
import { logger } from "./logger";
import { phaseDisplay } from "./domElements";
import { createSupplyCenters } from "./units/create";
import { createUnitMesh } from "./units/create";
import { updateSupplyCenterOwnership, updateLeaderboard, updateMapOwnership } from "./map/state";

// New function to display initial state without messages
export function displayInitialPhase() {
  let index = 0
  if (!gameState.gameData || !gameState.gameData.phases || index < 0 || index >= gameState.gameData.phases.length) {
    logger.log("Invalid phase index.")
    return;
  }

  // Clear any existing units
  const supplyCenters = gameState.unitMeshes.filter(m => m.userData && m.userData.isSupplyCenter);
  const oldUnits = gameState.unitMeshes.filter(m => m.userData && !m.userData.isSupplyCenter);
  oldUnits.forEach(m => gameState.scene.remove(m));
  gameState.unitMeshes = supplyCenters;

  const phase = gameState.gameData.phases[index];
  phaseDisplay.textContent = `Era: ${phase.name || 'Unknown Era'} (${index + 1}/${gameState.gameData.phases.length})`;

  // Show supply centers
  let newSCs = createSupplyCenters();
  newSCs.forEach((sc) => gameState.scene.add(sc))
  if (phase.state?.centers) {
    updateSupplyCenterOwnership(phase.state.centers);
  }

  // Show units
  if (phase.state?.units) {
    for (const [power, unitArr] of Object.entries(phase.state.units)) {
      unitArr.forEach(unitStr => {
        const match = unitStr.match(/^([AF])\s+(.+)$/);
        if (match) {
          let newUnit = createUnitMesh({
            power: power.toUpperCase(),
            type: match[1],
            province: match[2],
          });
          gameState.scene.add(newUnit)
          gameState.unitMeshes.push(newUnit)
        }
      });
    }
  }

  updateLeaderboard(phase);
  updateMapOwnership(phase)

  logger.log(`Phase: ${phase.name}\nSCs: ${phase.state?.centers ? JSON.stringify(phase.state.centers) : 'None'}\nUnits: ${phase.state?.units ? JSON.stringify(phase.state.units) : 'None'}`)

  // Add: Update info panel
  logger.updateInfoPanel();

}
