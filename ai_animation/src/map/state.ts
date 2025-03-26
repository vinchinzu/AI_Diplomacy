import { getPowerHexColor } from "../units/create";
import { gameState } from "../gameState";
import { leaderboard } from "../domElements";
import { ProvTypeENUM, PowerENUM } from "../types/map";
import { MeshBasicMaterial } from "three";


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
  // Get supply center counts
  const centerCounts = {};
  const unitCounts = {};

  // Count supply centers by power
  if (phase.state?.centers) {
    for (const [power, provinces] of Object.entries(phase.state.centers)) {
      centerCounts[power] = provinces.length;
    }
  }

  // Count units by power
  if (phase.state?.units) {
    for (const [power, units] of Object.entries(phase.state.units)) {
      unitCounts[power] = units.length;
    }
  }

  // Combine all powers from both centers and units
  const allPowers = new Set([
    ...Object.keys(centerCounts),
    ...Object.keys(unitCounts)
  ]);

  // Sort powers by supply center count (descending)
  const sortedPowers = Array.from(allPowers).sort((a, b) => {
    return (centerCounts[b] || 0) - (centerCounts[a] || 0);
  });

  // Build HTML for leaderboard
  let html = `<strong>Council Standings</strong><br/>`;

  sortedPowers.forEach(power => {
    const centers = centerCounts[power] || 0;
    const units = unitCounts[power] || 0;

    // Use CSS classes instead of inline styles for better contrast
    html += `<div style="margin: 5px 0; display: flex; justify-content: space-between;">
          <span class="power-${power.toLowerCase()}">${power}</span>
          <span>${centers} SCs, ${units} units</span>
        </div>`;
  });

  // Add victory condition reminder
  html += `<hr style="border-color: #555; margin: 8px 0;"/>
        <small>Victory: 18 supply centers</small>`;

  leaderboard.innerHTML = html;
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

  for (let powerKey of Object.keys(currentPhase.state.influence) as Array<keyof typeof PowerENUM>) {
    for (let provKey of currentPhase.state.influence[powerKey]) {

      const province = gameState.boardState.provinces[provKey];
      province.owner = PowerENUM[powerKey as keyof typeof PowerENUM]

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
}

