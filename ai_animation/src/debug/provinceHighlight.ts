import { gameState } from "../gameState";
import { provinceInput, highlightProvinceBtn } from "../domElements";
import { ProvinceENUM } from "../types/map";
import { MeshBasicMaterial } from "three";
import { oscillate, msToSeconds } from "../utils/timing";
import { config } from "../config";

interface FlashAnimation {
  mesh: THREE.Mesh;
  originalColor: number;
  startTime: number;
  duration: number;
  animationId?: number; // For cancelling the animation
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
    startTime: performance.now(),
    duration: 2000 // 2 seconds
  };

  console.log(`Highlighting province: ${normalizedName}`);

  // Start the animation loop
  currentFlashAnimation.animationId = requestAnimationFrame(animateFlash);
}

/**
 * Animates the flashing effect
 */
function animateFlash(currentTime: number = 0): void {
  if (!currentFlashAnimation) return;

  const elapsed = currentTime - currentFlashAnimation.startTime;
  const progress = elapsed / currentFlashAnimation.duration;

  if (progress >= 1) {
    // Animation complete, restore original color
    stopCurrentFlash();
    return;
  }

  // Calculate flash intensity using sine wave for smooth pulsing
  // Use elapsed time in seconds for consistent animation speed
  const elapsedSeconds = msToSeconds(elapsed);
  const flashIntensity = oscillate(config.animation.provinceFlashFrequency, elapsedSeconds);

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
  currentFlashAnimation.animationId = requestAnimationFrame(animateFlash);
}

/**
 * Stops the current flash animation and restores the original color
 */
function stopCurrentFlash(): void {
  if (!currentFlashAnimation) return;

  // Cancel the animation frame if it exists
  if (currentFlashAnimation.animationId) {
    cancelAnimationFrame(currentFlashAnimation.animationId);
  }

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


// Initialize debug province highlighting functionality
export function initDebugProvinceHighlighting() {

  highlightProvinceBtn.addEventListener('click', () => {
    const provinceName = provinceInput.value.trim();
    if (provinceName) {
      highlightProvince(provinceName);
    } else {
      console.warn('Please enter a province name');
    }
  });

  // Allow highlighting on Enter key press
  provinceInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      const provinceName = provinceInput.value.trim();
      if (provinceName) {
        highlightProvince(provinceName);
      }
    }
  });

  // Add input validation and autocomplete suggestions
  provinceInput.addEventListener('input', () => {
    const input = provinceInput.value.toUpperCase().trim();
    const availableProvinces = getAvailableProvinces();

    // Basic validation - turn input red if it doesn't match any province
    if (input && !availableProvinces.some(p => p.startsWith(input))) {
      provinceInput.style.borderColor = '#ff4444';
      provinceInput.style.backgroundColor = '#ffe6e6';
    } else {
      provinceInput.style.borderColor = '#4f3b16';
      provinceInput.style.backgroundColor = '#faf0d8';
    }
  });
}
