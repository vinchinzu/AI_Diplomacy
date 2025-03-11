import * as THREE from "three"
import { PowerENUM } from "./map"

export type UnitMesh = {
  mesh: THREE.Group
  userData: {
    province: string
    isSupplyCenter: boolean
    owner: PowerENUM
    starMesh: THREE.Mesh
    glowMesh: THREE.Mesh
  }
}
