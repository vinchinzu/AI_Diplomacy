import * as THREE from "three";
import { UnitData, UnitMesh } from "../types/units";
import { PowerENUM } from "../types/map";

// Get color for a power
export function getPowerHexColor(power: PowerENUM) {
  let defaultColor = '#ddd2af'
  if (power === undefined) return defaultColor
  const powerColors = {
    'AUSTRIA': '#c40000',
    'ENGLAND': '#00008B',
    'FRANCE': '#0fa0d0',
    'GERMANY': '#666666',
    'ITALY': '#008000',
    'RUSSIA': '#cccccc',
    'TURKEY': '#e0c846',
  };
  return powerColors[power] || defaultColor; // fallback to neutral
}

function createArmy(color: string): THREE.Group {
  let group = new THREE.Group();
  // Army: a block + small head for soldier-like appearance
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(15, 20, 10),
    new THREE.MeshStandardMaterial({ color })
  );
  body.position.y = 10;
  group.add(body);

  // Head
  const head = new THREE.Mesh(
    new THREE.SphereGeometry(4, 12, 12),
    new THREE.MeshStandardMaterial({ color })
  );
  head.position.set(0, 24, 0);
  group.add(head);
  return group
}

function createFleet(color: string): THREE.Group {

  let group = new THREE.Group();
  // Fleet: a rectangle + a mast and sail
  const hull = new THREE.Mesh(
    new THREE.BoxGeometry(30, 8, 15),
    new THREE.MeshStandardMaterial({ color: 0x8B4513 })
  );
  hull.position.y = 4;
  group.add(hull);

  // Mast
  const mast = new THREE.Mesh(
    new THREE.CylinderGeometry(1, 1, 30, 8),
    new THREE.MeshStandardMaterial({ color: 0x000000 })
  );
  mast.position.y = 15;
  group.add(mast);

  // Sail
  const sail = new THREE.Mesh(
    new THREE.PlaneGeometry(20, 15),
    new THREE.MeshStandardMaterial({ color, side: THREE.DoubleSide })
  );
  sail.rotation.y = Math.PI / 2;
  sail.position.set(0, 15, 0);
  group.add(sail);
  return group
}
export function createUnitMesh(unitData: UnitData): UnitMesh {
  const color = getPowerHexColor(unitData.power);
  let group: THREE.Group | null;

  // Minimal shape difference for armies vs fleets
  if (unitData.type === 'A') {
    group = createArmy(color)
  } else {
    group = createFleet(color)
  }

  // Store metadata
  group.userData = {
    power: unitData.power,
    type: unitData.type,
    location: unitData.province
  };

  return group;
}
