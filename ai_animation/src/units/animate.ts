import * as THREE from "three";
import { Tween, Easing } from "@tweenjs/tween.js";
import { createUnitMesh } from "./create";
import { getProvincePosition } from "../map/utils";
import { gameState } from "../gameState";
import type { UnitOrder } from "../types/unitOrders";
import { logger } from "../logger";
import { config } from "../config"; // Assuming config is defined in a separate file
import { PowerENUM, ProvinceENUM, ProvTypeENUM } from "../types/map";
import { UnitTypeENUM } from "../types/units";

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

/* Return a tween animation for the spawning of a unit.
 *  Intended to be invoked before the unit is added to the scene
*/
function createSpawnAnimation(newUnitMesh: THREE.Group): Tween {
  // Start the unit really high, and lower it to the board.
  newUnitMesh.position.setY(1000)
  return new Tween({ y: 1000 })
    .to({ y: 10 }, 1000)
    .easing(Easing.Quadratic.Out)
    .onUpdate((object) => {
      newUnitMesh.position.setY(object.y)
    }).start()
}

function createMoveAnimation(unitMesh: THREE.Group, orderDestination: ProvinceENUM): Tween {
  let destinationVector = getProvincePosition(orderDestination);
  if (!destinationVector) {
    throw new Error("Unable to find the vector for province with name " + orderDestination)
  }
  let anim = new Tween(unitMesh.position)
    .to({
      x: destinationVector.x,
      y: 10,
      z: destinationVector.z
    }, config.animationDuration)
    .easing(Easing.Quadratic.InOut)
    .onUpdate(() => {
      unitMesh.position.y = 10 + Math.sin(Date.now() * 0.05) * 2;
      if (unitMesh.userData.type === 'F') {
        unitMesh.rotation.z = Math.sin(Date.now() * 0.03) * 0.1;
        unitMesh.rotation.x = Math.sin(Date.now() * 0.02) * 0.1;
      }
    })
    .onComplete(() => {
      unitMesh.userData.province = orderDestination;
      unitMesh.position.y = 10;
      if (unitMesh.userData.type === 'F') {
        unitMesh.rotation.z = 0;
        unitMesh.rotation.x = 0;
      }
    })
    .start();
  gameState.unitAnimations.push(anim);
  return anim
}

/**
 * Creates animations for unit movements based on orders from the previous phase
 *
**/
export function createAnimationsForNextPhase() {
  let previousPhase = gameState.gameData?.phases[gameState.phaseIndex == 0 ? 0 : gameState.phaseIndex - 1]

  // Safety check - if no previous phase or no orders, return
  if (!previousPhase) {
    logger.log("No previous phase to animate");
    return;
  }
  for (const [power, orders] of Object.entries(previousPhase.orders)) {
    if (orders === null) {
      continue
    }
    for (const order of orders) {
      // Check if unit bounced
      let lastPhaseResultMatches = Object.entries(previousPhase.results).filter(([key, _]) => {
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
      // If the result is void, that means the move was not valid?
      if (lastPhaseResultMatches[0].result === "void") continue;

      let unitIndex = getUnit(order, power);
      if (order.type != "build" && unitIndex < 0) throw new Error("Unable to find unit for order " + order.raw)
      switch (order.type) {
        case "move":
          if (!order.destination) throw new Error("Move order with no destination, cannot complete move.")
          // Create a tween for smooth movement
          createMoveAnimation(gameState.unitMeshes[unitIndex], order.destination as keyof typeof ProvinceENUM)
          break;

        case "disband":
          // TODO: Death animation
          gameState.scene.remove(gameState.unitMeshes[unitIndex]);
          gameState.unitMeshes.splice(unitIndex, 1);
          break;

        case "build":
          // TODO: Spawn animation?
          let newUnit = createUnitMesh({
            power: PowerENUM[power as keyof typeof PowerENUM],
            type: UnitTypeENUM[order.unit.type as keyof typeof UnitTypeENUM],
            province: order.unit.origin
          })
          gameState.unitAnimations.push(createSpawnAnimation(newUnit))
          gameState.scene.add(newUnit)
          gameState.unitMeshes.push(newUnit)
          break;

        case "bounce":
          // TODO: implement bounce animation
          break;
        case "hold":
          //TODO: Hold animation, maybe a sheild or something?
          break;

        case "retreat":
          createMoveAnimation(gameState.unitMeshes[unitIndex], order.destination as keyof typeof ProvinceENUM)
          break;

        case "support":
          break


        default:
          break;
      }
    }
  }
}
