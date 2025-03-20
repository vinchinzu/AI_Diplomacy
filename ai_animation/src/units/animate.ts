import * as THREE from "three";
import type { GamePhase } from "../types/gameState";
import { createUnitMesh } from "./create";
import { UnitMesh } from "../types/units";
import { getProvincePosition } from "../map/utils";
import * as TWEEN from "@tweenjs/tween.js";
import { gameState } from "../gameState";
import type { UnitOrder } from "../types/unitOrders";
import { OrderFromString } from "../types/unitOrders";
import { logger } from "../logger";
import { config } from "../config"; // Assuming config is defined in a separate file

//FIXME: Move this to a file with all the constants
enum AnimationTypeENUM {
  CREATE,
  MOVE,
  DELETE,
}
export type UnitAnimation = {
  duration: number
  endPos: any
  startPos: any
  object: THREE.Group
  startTime: number
  animationType?: AnimationTypeENUM
}

function getUnit(unitOrder: UnitOrder, power: string) {
  if (power === undefined) throw new Error("Must pass the power argument, cannot be undefined")
  let posUnits = gameState.unitMeshes.filter((unit) => {
    return (
      unit.userData.province === unitOrder.unit.origin &&
      unit.userData.type === unitOrder.unit.type &&
      unit.userData.power === power
    );
  });

  if (posUnits.length === 0) {
    return -1;
  }

  // Return the first matching unit
  return gameState.unitMeshes.indexOf(posUnits[0]);
}

/**
 * Creates animations for unit movements based on orders from the previous phase
 * @param currentPhase The current game phase
 * @param previousPhase The previous game phase containing orders to process
 *
**/
export function createTweenAnimations(currentPhase: GamePhase, previousPhase: GamePhase | null) {
  // Safety check - if no previous phase or no orders, return
  if (!previousPhase) {
    logger.log("No previous phase to animate");
    return;
  }
  for (const [power, orders] of Object.entries(previousPhase.orders)) {
    for (const order of orders) {
      // Check if unit bounced
      let lastPhaseResultMatches = Object.entries(previousPhase.results).filter(([key, value]) => {
        return key.split(" ")[1] == order.unit.origin
      }).map(val => {
        // in the form "A BER" (unitType origin)
        let orderSplit = val[0].split(" ")
        return { origin: orderSplit[1], unitType: orderSplit[0], result: val[1][0] }
      })
      // This should always exist. If we don't have a match here, that means something went wrong with our order parsing
      if (!lastPhaseResultMatches) {
        throw new Error("No result present in current phase for previous phase order. Cannot continue")
      }
      if (lastPhaseResultMatches.length > 1) {
        throw new Error("Multiple matching results from last phase. Should only ever be 1.")
      }
      if (lastPhaseResultMatches[0].result === "bounce") {
        order.type = "bounce"
      }

      let unitIndex = getUnit(order, power);
      if (unitIndex < 0) throw new Error("Unable to find unit for order " + order.raw)
      switch (order.type) {
        case "move":
          let destinationVector = getProvincePosition(gameState.boardState, order.destination);
          if (!destinationVector) {
            throw new Error("Unable to find the vector for province with name " + order.destination)
          }
          // Create a tween for smooth movement
          let anim = new TWEEN.Tween(gameState.unitMeshes[unitIndex].position)
            .to({
              x: destinationVector.x,
              y: 10,
              z: destinationVector.z
            }, config.animationDuration)
            .easing(TWEEN.Easing.Quadratic.InOut)
            .onUpdate(() => {
              gameState.unitMeshes[unitIndex].position.y = 10 + Math.sin(Date.now() * 0.05) * 2;
              if (gameState.unitMeshes[unitIndex].userData.type === 'F') {
                gameState.unitMeshes[unitIndex].rotation.z = Math.sin(Date.now() * 0.03) * 0.1;
                gameState.unitMeshes[unitIndex].rotation.x = Math.sin(Date.now() * 0.02) * 0.1;
              }
            })
            .onComplete(() => {
              gameState.unitMeshes[unitIndex].userData.province = order.destination;
              if (config.isDebugMode) {
                console.log(`Unit ${orderObj.power} ${gameState.unitMeshes[unitIndex].userData.type} moved: ${order.unit.origin} -> ${order.destination}`);
              }

              gameState.unitMeshes[unitIndex].position.y = 10;
              if (gameState.unitMeshes[unitIndex].userData.type === 'F') {
                gameState.unitMeshes[unitIndex].rotation.z = 0;
                gameState.unitMeshes[unitIndex].rotation.x = 0;
              }
            })
            .start();
          gameState.unitAnimations.push(anim);
          break;

        case "disband":
          if (config.isDebugMode) {
            console.log(`Disbanding unit ${orderObj.power} ${gameState.unitMeshes[unitIndex].userData.type} in ${gameState.unitMeshes[unitIndex].userData.province}`);
          }
          gameState.scene.remove(gameState.unitMeshes[unitIndex]);
          gameState.unitMeshes.splice(unitIndex, 1);
          break;

        case "bounce":
          // TODO: implement bounce animation
          break;

        default:
          if (config.isDebugMode) {
            console.log(`Skipping order type: ${order.type} for ${orderObj.text}`);
          }
          break;
      }
    }
  }
}

export function createAnimationsForPhaseTransition(unitMeshes: UnitMesh[], currentPhase: GamePhase, previousPhase: GamePhase | null): UnitAnimation[] {
  let unitAnimations: UnitAnimation[] = []
  // Prepare unit position maps
  const previousUnitPositions = {};
  if (previousPhase.state?.units) {
    for (const [power, unitArr] of Object.entries(previousPhase.state.units)) {
      unitArr.forEach(unitStr => {
        const match = unitStr.match(/^([AF])\s+(.+)$/);
        if (match) {
          const key = `${power} -${match[1]} -${match[2]} `;
          previousUnitPositions[key] = getProvincePosition(gameState.boardState, match[2]);
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
        const currentPos = getProvincePosition(gameState.boardState, location);

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
          duration: config.animationDuration
        });
      });
    }
  }
  return unitAnimations
}

// Easing function for smooth animations
function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export function proccessUnitAnimationWithTween(anim: Tween) {
  anim.update()
}

export function processUnitAnimation(anim: UnitAnimation): boolean {

  const currentTime = Date.now();
  const elapsed = currentTime - anim.startTime;
  // Calculate progress (0 to 1)
  const progress = Math.min(1, elapsed / anim.duration);

  // Apply movement
  if (progress < 1) {
    // Apply easing for more natural movement - ease in and out
    const easedProgress = easeInOutCubic(progress);

    // Update position
    anim.object.position.x = anim.startPos.x + (anim.endPos.x - anim.startPos.x) * easedProgress;
    anim.object.position.z = anim.startPos.z + (anim.endPos.z - anim.startPos.z) * easedProgress;

    // Subtle bobbing up and down during movement
    anim.object.position.y = 10 + Math.sin(progress * Math.PI * 2) * 5;

    // For fleets (ships), add a gentle rocking motion
    if (anim.object.userData.type === 'F') {
      anim.object.rotation.z = Math.sin(progress * Math.PI * 3) * 0.05;
      anim.object.rotation.x = Math.sin(progress * Math.PI * 2) * 0.05;
    }
    if (anim.object.position.x == anim.startPos.x) {
      console.log("We ain't moving")
    }
    anim.object.updateMatrix()
    return false
  } else {
    // Set final position
    anim.object.position.x = anim.endPos.x;
    anim.object.position.z = anim.endPos.z;
    anim.object.position.y = 10; // Reset height

    // Reset rotation for ships
    if (anim.object.userData.type === 'F') {
      anim.object.rotation.z = 0;
      anim.object.rotation.x = 0;
    }
    return true
  }
}
