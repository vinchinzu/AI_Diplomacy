import * as THREE from "three";
import { FontLoader } from 'three/addons/loaders/FontLoader.js';
import { SVGLoader } from 'three/addons/loaders/SVGLoader.js';
import { createLabel } from "./labels"
import { coordinateData } from "../gameState";
import { getPowerHexColor } from "../units/create";

export function initMap(scene,) {
  const loader = new SVGLoader();
  loader.load('assets/maps/standard/map.svg',
    function (data) {
      fetch('assets/maps/standard/styles.json')
        .then(resp => resp.json())
        .then(map_styles => {
          const paths = data.paths;
          const group = new THREE.Group();
          const textGroup = new THREE.Group();
          let fillColor;

          for (let i = 0; i < paths.length; i++) {
            fillColor = "#ddd2af";
            const path = paths[i];
            // The "standard" map has keys like _mos, so remove that then send them to caps
            let provinceKey = path.userData.node.id.substring(1).toUpperCase();


            if (map_styles[path.userData.node.classList[0]] === undefined) {
              // If there is no style in the map_styles, skip drawing the shape
              // This is a bandaid for using an svg with extraneous shapes
              continue
            } else if (provinceKey && coordinateData.provinces[provinceKey]) {
              fillColor = getPowerHexColor(coordinateData.provinces[provinceKey].owner)
            }
            else {
              fillColor = map_styles[path.userData.node.classList[0]].fill;
            }

            const material = new THREE.MeshBasicMaterial({
              color: fillColor,
              side: THREE.DoubleSide,
              depthWrite: false
            });

            const shapes = SVGLoader.createShapes(path);

            for (let j = 0; j < shapes.length; j++) {

              const shape = shapes[j];
              const geometry = new THREE.ShapeGeometry(shape);
              const mesh = new THREE.Mesh(geometry, material);

              mesh.rotation.x = Math.PI / 2;
              if (provinceKey && coordinateData.provinces[provinceKey]) {
                coordinateData.provinces[provinceKey].mesh = mesh
              }


              // Create an edges geometry from the shape geometry.
              const edges = new THREE.EdgesGeometry(geometry);
              // Create a line material with black color for the border.
              const lineMaterial = new THREE.LineBasicMaterial({ color: 0x000000, linewidth: 2 });
              // Create the line segments object to display the border.
              const line = new THREE.LineSegments(edges, lineMaterial);
              // Add the border as a child of the mesh.
              mesh.add(line);
              group.add(mesh);
            }
          }

          // Load all the labels for each map position
          const fontLoader = new FontLoader();
          fontLoader.load('assets/fonts/helvetiker_regular.typeface.json', function (font) {
            for (const [key, value] of Object.entries(coordinateData.provinces)) {

              textGroup.add(createLabel(font, key, value))
            }
          })
          // This rotates the SVG the "correct" way round, and scales it down
          group.scale.set(1, -1, 1)
          textGroup.rotation.x = Math.PI / 2;
          textGroup.scale.set(1, -1, 1)

          // After adding all meshes to the group, update its matrix:
          group.updateMatrixWorld(true);
          textGroup.updateMatrixWorld(true);

          // Compute the bounding box of the group:
          const box = new THREE.Box3().setFromObject(group);
          const center = new THREE.Vector3();
          box.getCenter(center);


          scene.add(group);
          scene.add(textGroup);

        })
        .catch(error => {
          console.error('Error loading map styles:', error);
        });
    },
    // Progress function
    undefined,
    function (error) { console.log(error) })

}
