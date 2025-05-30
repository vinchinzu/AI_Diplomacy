import { gameState } from "./gameState";
import { getPowerDisplayName } from './utils/powerNames';
import { PowerENUM } from './types/map';

class Logger {
  get infoPanel() {
    let _panel = document.getElementById('info-panel');
    if (_panel === null) {
      throw new Error("Unable to find the element with id 'info-panel'")
    }
    return _panel
  }

  // Modified to only log to console without updating the info panel
  log = (msg: string) => {
    if (typeof msg !== "string") {
      throw new Error(`Logger messages must be strings, you passed a ${typeof msg}`);
    }
    // Remove the update to infoPanel.textContent
    console.log(msg);
  }

  // Updated function to update info panel with useful information and smooth transitions
  updateInfoPanel = () => {
    const totalPhases = gameState.gameData?.phases?.length || 0;
    const currentPhaseNumber = gameState.phaseIndex + 1;
    const phaseName = gameState.gameData?.phases?.[gameState.phaseIndex]?.name || 'Unknown';

    // Add fade-out transition
    this.infoPanel.style.transition = 'opacity 0.3s ease-out';
    this.infoPanel.style.opacity = '0';

    // Update content after fade-out
    setTimeout(() => {
      // Get supply center counts for the current phase
      const scCounts = this.getSupplyCenterCounts();

      this.infoPanel.innerHTML = `
        <div><strong>Power:</strong> <span class="power-${gameState.currentPower.toLowerCase()}">${getPowerDisplayName(gameState.currentPower)}</span></div>
        <div><strong>Current Phase:</strong> ${phaseName}</div>
        <hr/>
        <h4>Supply Center Counts</h4>
        <ul style="list-style:none;padding-left:0;margin:0;">
          <li><span class="power-austria">${getPowerDisplayName(PowerENUM.AUSTRIA)}:</span> ${scCounts.AUSTRIA || 0}</li>
          <li><span class="power-england">${getPowerDisplayName(PowerENUM.ENGLAND)}:</span> ${scCounts.ENGLAND || 0}</li>
          <li><span class="power-france">${getPowerDisplayName(PowerENUM.FRANCE)}:</span> ${scCounts.FRANCE || 0}</li>
          <li><span class="power-germany">${getPowerDisplayName(PowerENUM.GERMANY)}:</span> ${scCounts.GERMANY || 0}</li>
          <li><span class="power-italy">${getPowerDisplayName(PowerENUM.ITALY)}:</span> ${scCounts.ITALY || 0}</li>
          <li><span class="power-russia">${getPowerDisplayName(PowerENUM.RUSSIA)}:</span> ${scCounts.RUSSIA || 0}</li>
          <li><span class="power-turkey">${getPowerDisplayName(PowerENUM.TURKEY)}:</span> ${scCounts.TURKEY || 0}</li>
        </ul>
      `;

      // Fade back in
      this.infoPanel.style.opacity = '1';
    }, 300);
  }

  // Helper function to count supply centers for each power
  getSupplyCenterCounts = () => {
    const counts = {
      AUSTRIA: 0,
      ENGLAND: 0,
      FRANCE: 0,
      GERMANY: 0,
      ITALY: 0,
      RUSSIA: 0,
      TURKEY: 0
    };

    // Get current phase's supply center data
    const centers = gameState.gameData?.phases?.[gameState.phaseIndex]?.state?.centers;

    if (centers) {
      // Count supply centers for each power
      Object.entries(centers).forEach(([power, provinces]) => {
        if (power && Array.isArray(provinces)) {
          counts[power as keyof typeof counts] = provinces.length;
        }
      });
    }

    return counts;
  }
}
export const logger = new Logger()
