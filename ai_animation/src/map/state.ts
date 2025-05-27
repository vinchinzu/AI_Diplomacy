import { getPowerHexColor } from "../units/create";
import { gameState } from "../gameState";
import { leaderboard } from "../domElements";
import { ProvTypeENUM, PowerENUM } from "../types/map";
import { MeshBasicMaterial } from "three";
import { updateRotatingDisplay } from "../components/rotatingDisplay";

export function updateSupplyCenterOwnership(centers) {
  if (!centers) return;
  const ownershipMap = {};
  // centers is typically { "AUSTRIA":["VIE","BUD"], "FRANCE":["PAR","MAR"], ... }
  for (const [power, provinces] of Object.entries(centers)) {
    provinces.forEach(p => {
      // No messages, animate units immediately
      ownershipMap[p.toUpperCase()] = power.toUpperCase();
    });
  }

  gameState.unitMeshes.forEach(obj => {
    if (obj.userData && obj.userData.isSupplyCenter) {
      const prov = obj.userData.province;
      const owner = ownershipMap[prov];
      if (owner) {
        const c = getPowerHexColor(owner);
        obj.userData.starMesh.material.color.setHex(c);

        // Add a pulsing animation
        if (!obj.userData.pulseAnimation) {
          obj.userData.pulseAnimation = {
            speed: 0.003 + Math.random() * 0.002,
            intensity: 0.3,
            time: Math.random() * Math.PI * 2
          };
          if (!gameState.scene.userData.animatedObjects) gameState.scene.userData.animatedObjects = [];
          gameState.scene.userData.animatedObjects.push(obj);
        }
      } else {
        // Neutral
        obj.userData.starMesh.material.color.setHex(0xFFD700);
        // remove pulse
        obj.userData.pulseAnimation = null;
      }
    }
  });
}

export function updateLeaderboard(phase) {
  // Instead of directly updating the leaderboard HTML,
  // use the rotating display component if game data exists
  if (gameState.gameData) {
    updateRotatingDisplay(gameState.gameData, gameState.phaseIndex, gameState.currentPower);
  }
}

export function updateMapOwnership() {
  let currentPhase = gameState.gameData?.phases[gameState.phaseIndex]
  if (currentPhase === undefined) {
    throw "Currentphase is undefined for index " + gameState.phaseIndex;
  }

  // Clear existing ownership to avoid stale data
  for (const key in gameState.boardState.provinces) {
    if (gameState.boardState.provinces[key].owner) {
      gameState.boardState.provinces[key].owner = undefined;
    }
  }
  // Set map ownership from the current influence section of the current phase

  for (let powerKey of Object.keys(currentPhase.state.influence) as Array<keyof typeof PowerENUM>) {
    for (let provKey of currentPhase.state.influence[powerKey]) {

      const province = gameState.boardState.provinces[provKey];
      province.owner = PowerENUM[powerKey as keyof typeof PowerENUM]

    }
  }
  for (let [provKey, province] of Object.entries(gameState.boardState.provinces)) {
    // Update the color of the provinces if needed, you can only own coast and land
    if ([ProvTypeENUM.COAST, ProvTypeENUM.LAND].indexOf(province.type) >= 0) {
      if (province.owner) {
        let powerColor = getPowerHexColor(province.owner);
        let powerColorHex = parseInt(powerColor.substring(1), 16);
        (province.mesh?.material as MeshBasicMaterial).color.setHex(powerColorHex);
      } else if (province.owner === undefined && province.mesh !== undefined) {
        let powerColor = getPowerHexColor(undefined);
        let powerColorHex = parseInt(powerColor.substring(1), 16);
        (province.mesh.material as MeshBasicMaterial).color.setHex(powerColorHex)
      }
    }
  }
}
