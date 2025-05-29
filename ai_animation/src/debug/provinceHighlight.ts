import { gameState } from "../gameState";
import { ProvinceENUM } from "../types/map";
import { MeshBasicMaterial } from "three";

interface FlashAnimation {
  mesh: THREE.Mesh;
  originalColor: number;
  startTime: number;
  duration: number;
}

let currentFlashAnimation: FlashAnimation | null = null;

/**
 * Highlights a province on the map with a flashing animation
 * @param provinceName - The name of the province to highlight (e.g., "PAR", "LON", "BER")
 */
export function highlightProvince(provinceName: string): void {
  // Stop any existing animation
  if (currentFlashAnimation) {
    stopCurrentFlash();
  }

  // Normalize the province name to uppercase
  const normalizedName = provinceName.toUpperCase().trim();
  
  // Check if it's a valid province
  if (!Object.values(ProvinceENUM).includes(normalizedName as ProvinceENUM)) {
    console.warn(`Province "${normalizedName}" not found. Valid provinces are:`, Object.values(ProvinceENUM));
    return;
  }

  // Find the province in the board state
  const province = gameState.boardState.provinces[normalizedName];
  if (!province || !province.mesh) {
    console.warn(`Province "${normalizedName}" mesh not found on the map`);
    return;
  }

  // Get the mesh material
  const material = province.mesh.material as MeshBasicMaterial;
  const originalColor = material.color.getHex();

  // Start the flash animation
  currentFlashAnimation = {
    mesh: province.mesh,
    originalColor,
    startTime: Date.now(),
    duration: 2000 // 2 seconds
  };

  console.log(`Highlighting province: ${normalizedName}`);
  
  // Start the animation loop
  animateFlash();
}

/**
 * Animates the flashing effect
 */
function animateFlash(): void {
  if (!currentFlashAnimation) return;

  const elapsed = Date.now() - currentFlashAnimation.startTime;
  const progress = elapsed / currentFlashAnimation.duration;

  if (progress >= 1) {
    // Animation complete, restore original color
    stopCurrentFlash();
    return;
  }

  // Calculate flash intensity using sine wave for smooth pulsing
  const flashIntensity = Math.sin(elapsed * 0.01) * 0.5 + 0.5; // 0 to 1
  
  // Interpolate between original color and bright yellow
  const material = currentFlashAnimation.mesh.material as MeshBasicMaterial;
  const originalColor = currentFlashAnimation.originalColor;
  
  // Extract RGB components from original color
  const originalR = (originalColor >> 16) & 255;
  const originalG = (originalColor >> 8) & 255;
  const originalB = originalColor & 255;
  
  // Flash to a bright yellow (255, 255, 0)
  const flashR = 255;
  const flashG = 255;
  const flashB = 0;
  
  // Interpolate between original and flash colors
  const r = Math.round(originalR + (flashR - originalR) * flashIntensity);
  const g = Math.round(originalG + (flashG - originalG) * flashIntensity);
  const b = Math.round(originalB + (flashB - originalB) * flashIntensity);
  
  // Set the new color
  const newColor = (r << 16) | (g << 8) | b;
  material.color.setHex(newColor);

  // Continue animation
  requestAnimationFrame(animateFlash);
}

/**
 * Stops the current flash animation and restores the original color
 */
function stopCurrentFlash(): void {
  if (!currentFlashAnimation) return;

  // Restore original color
  const material = currentFlashAnimation.mesh.material as MeshBasicMaterial;
  material.color.setHex(currentFlashAnimation.originalColor);
  
  currentFlashAnimation = null;
}

/**
 * Gets a list of all available province names
 */
export function getAvailableProvinces(): string[] {
  return Object.values(ProvinceENUM);
}