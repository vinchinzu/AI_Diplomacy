import type { GamePhase } from "../types/gameState";
import { createUnitMesh } from "./create";
import { UnitMesh } from "../types/units";
import { getProvincePosition } from "../map/utils";
import { coordinateData } from "../gameState";

//FIXME: Move this to a file with all the constants
let animationDuration = 1500; // Duration of unit movement animation in ms
enum AnimationTypeENUM {
  CREATE,
  MOVE,
  DELETE,
}
type unitAnimation = {
  animationType: AnimationTypeENUM
}

export function createAnimationsForPhaseTransition(unitMeshes: UnitMesh[], currentPhase: GamePhase, previousPhase: GamePhase | null): unitAnimation[] {
  let unitAnimations: unitAnimation[] = []
  // Prepare unit position maps
  const previousUnitPositions = {};
  if (previousPhase.state?.units) {
    for (const [power, unitArr] of Object.entries(previousPhase.state.units)) {
      unitArr.forEach(unitStr => {
        const match = unitStr.match(/^([AF])\s+(.+)$/);
        if (match) {
          const key = `${power} -${match[1]} -${match[2]} `;
          previousUnitPositions[key] = getProvincePosition(coordinateData, match[2]);
        }
      });
    }
  }

  // Animate new units from old positions (or spawn from below)
  if (currentPhase.state?.units) {
    for (const [power, unitArr] of Object.entries(currentPhase.state.units)) {
      unitArr.forEach(unitStr => {
        // For each unit, create a new mesh
        const match = unitStr.match(/^([AF])\s+(.+)$/);
        if (!match) return;
        const unitType = match[1];
        const location = match[2];


        // Current final
        const currentPos = getProvincePosition(coordinateData, location);

        let startPos;
        let matchFound = false;
        for (const prevKey in previousUnitPositions) {
          if (prevKey.startsWith(`${power} -${unitType} `)) {
            startPos = previousUnitPositions[prevKey];
            matchFound = true;
            delete previousUnitPositions[prevKey];
            break;
          }
        }
        if (!matchFound) {
          // TODO: Add a spawn animation?
          //
          // New spawn
          startPos = { x: currentPos.x, y: -20, z: currentPos.z };
        }

        const unitMesh = createUnitMesh({
          power: power,
          province: location,
          type: unitType,
        });
        unitMesh.position.set(startPos.x, 10, startPos.z);

        // Animate
        unitAnimations.push({
          object: unitMesh,
          startPos,
          endPos: currentPos,
          startTime: Date.now(),
          duration: animationDuration
        });
      });
    }
  }
  return unitAnimations
}
