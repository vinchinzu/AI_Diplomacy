import { gameState } from "./gameState";
import { logger } from "./logger";


export function updatePhaseDisplay() {
  const currentPhase = gameState.gameData.phases[gameState.phaseIndex];
  // Add fade-out effect
  phaseDisplay.style.transition = 'opacity 0.3s ease-out';
  phaseDisplay.style.opacity = '0';

  // Update text after fade-out
  setTimeout(() => {
    phaseDisplay.textContent = `Era: ${currentPhase.name || 'Unknown Era'}`;
    // Fade back in
    phaseDisplay.style.opacity = '1';
  }, 300);
}

export function updateGameIdDisplay() {
  if (!gameIdDisplay) return;

  // Add fade-out effect
  gameIdDisplay.style.transition = 'opacity 0.3s ease-out';
  gameIdDisplay.style.opacity = '0';

  // Update text after fade-out
  setTimeout(() => {
    gameIdDisplay.textContent = `Game: ${gameState.gameId}`;
    // Fade back in
    gameIdDisplay.style.opacity = '1';
  }, 300);
}
// --- LOADING & DISPLAYING GAME PHASES ---
export function loadGameBtnFunction(file) {
  const reader = new FileReader();
  reader.onload = e => {
    gameState.loadGameData(e.target?.result)
  };
  reader.onerror = () => {
    logger.log("Error reading file.")
  };
  reader.readAsText(file);
}
export const loadBtn = document.getElementById('load-btn');
if (null === loadBtn) throw new Error("Element with ID 'load-btn' not found");

export const fileInput = document.getElementById('file-input');
if (null === fileInput) throw new Error("Element with ID 'file-input' not found");

export const prevBtn = document.getElementById('prev-btn');
if (null === prevBtn) throw new Error("Element with ID 'prev-btn' not found");

export const nextBtn = document.getElementById('next-btn');
if (null === nextBtn) throw new Error("Element with ID 'next-btn' not found");

export const playBtn = document.getElementById('play-btn');
if (null === playBtn) throw new Error("Element with ID 'play-btn' not found");

export const speedSelector = document.getElementById('speed-selector');
if (null === speedSelector) throw new Error("Element with ID 'speed-selector' not found");

export const phaseDisplay = document.getElementById('phase-display');
if (null === phaseDisplay) throw new Error("Element with ID 'phase-display' not found");

export const gameIdDisplay = document.getElementById('game-id-display');
if (null === gameIdDisplay) throw new Error("Element with ID 'game-id-display' not found");

export const mapView = document.getElementById('map-view');
if (null === mapView) throw new Error("Element with ID 'map-view' not found");

export const leaderboard = document.getElementById('leaderboard');
if (null === leaderboard) throw new Error("Element with ID 'leaderboard' not found");

export const standingsBtn = document.getElementById('standings-btn');
if (null === standingsBtn) throw new Error("Element with ID 'standings-btn' not found");

export const debugProvincePanel = document.getElementById('debug-province-panel');
if (null === debugProvincePanel) throw new Error("Element with ID 'debug-province-panel' not found");

export const provinceInput = document.getElementById('province-input') as HTMLInputElement;
if (null === provinceInput) throw new Error("Element with ID 'province-input' not found");

export const highlightProvinceBtn = document.getElementById('highlight-province-btn');
if (null === highlightProvinceBtn) throw new Error("Element with ID 'highlight-province-btn' not found");



// Add roundRect polyfill for browsers that don't support it
if (!CanvasRenderingContext2D.prototype.roundRect) {
  CanvasRenderingContext2D.prototype.roundRect = function (x, y, width, height, radius) {
    if (typeof radius === 'undefined') {
      radius = 5;
    }
    this.beginPath();
    this.moveTo(x + radius, y);
    this.lineTo(x + width - radius, y);
    this.arcTo(x + width, y, x + width, y + radius, radius);
    this.lineTo(x + width, y + height - radius);
    this.arcTo(x + width, y + height, x + width - radius, y + height, radius);
    this.lineTo(x + radius, y + height);
    this.arcTo(x, y + height, x, y + height - radius, radius);
    this.lineTo(x, y + radius);
    this.arcTo(x, y, x + radius, y, radius);
    this.closePath();
    return this;
  };
}

