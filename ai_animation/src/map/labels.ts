import * as THREE from "three"
import type { Province } from "../types/map";

export function createLabel(font, provName: String, provinceData: Province) {

  const color = 0x006699;

  const matDark = new THREE.LineBasicMaterial({
    color: color,
    side: THREE.DoubleSide
  });

  const matLite = new THREE.MeshBasicMaterial({
    color: color,
    transparent: true,
    opacity: 0.7,
    side: THREE.DoubleSide
  });
  const shapes = font.generateShapes(provName, 20);

  const geometry = new THREE.ShapeGeometry(shapes);

  geometry.computeBoundingBox();
  const xMid = - 0.5 * (geometry.boundingBox.max.x - geometry.boundingBox.min.x);
  const yMid = - 0.5 * (geometry.boundingBox.max.y - geometry.boundingBox.min.y);

  geometry.translate(provinceData.label.x + xMid, -provinceData.label.y + yMid, 0);
  const text = new THREE.Mesh(geometry, matLite);
  return text
}
