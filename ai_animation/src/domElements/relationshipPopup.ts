import { relationshipsBtn } from '../domElements';
import { gameState } from '../gameState';
import { PowerENUM } from '../types/map';
import { GameSchemaType } from '../types/gameState';
import { renderRelationshipHistoryChartView, DisplayType } from '../components/rotatingDisplay';
import { getPowerDisplayName } from '../utils/powerNames';

// DOM element references
let relationshipPopupContainer: HTMLElement | null = null;
let relationshipContent: HTMLElement | null = null;
let closeButton: HTMLElement | null = null;

/**
 * Initialize the relationship popup by creating DOM elements and attaching event handlers
 */
export function initRelationshipPopup(): void {
  // Create the container if it doesn't exist
  if (!document.getElementById('relationship-popup-container')) {
    createRelationshipPopupElements();
  }

  // Get references to the created elements
  relationshipPopupContainer = document.getElementById('relationship-popup-container');
  relationshipContent = document.getElementById('relationship-content');
  closeButton = document.getElementById('relationship-close-btn');

  // Add event listeners
  if (closeButton) {
    closeButton.addEventListener('click', hideRelationshipPopup);
  }

  // Add click handler for the relationships button
  if (relationshipsBtn) {
    relationshipsBtn.addEventListener('click', toggleRelationshipPopup);
  }
}

/**
 * Create all DOM elements needed for the relationship popup
 */
function createRelationshipPopupElements(): void {
  const container = document.createElement('div');
  container.id = 'relationship-popup-container';
  container.className = 'relationship-popup-container';

  // Create header
  const header = document.createElement('div');
  header.className = 'relationship-header';

  const title = document.createElement('h2');
  title.textContent = 'Diplomatic Relations';
  header.appendChild(title);

  const closeBtn = document.createElement('button');
  closeBtn.id = 'relationship-close-btn';
  closeBtn.textContent = '×';
  closeBtn.title = 'Close Relationships Chart';
  header.appendChild(closeBtn);

  container.appendChild(header);

  // Create content container
  const content = document.createElement('div');
  content.id = 'relationship-content';
  content.className = 'relationship-content';
  container.appendChild(content);

  // Add to document
  document.body.appendChild(container);
}

/**
 * Toggle the visibility of the relationship popup
 */
export function toggleRelationshipPopup(): void {
  if (relationshipPopupContainer) {
    if (relationshipPopupContainer.classList.contains('visible')) {
      hideRelationshipPopup();
    } else {
      showRelationshipPopup();
    }
  }
}

/**
 * Show the relationship popup
 */
export function showRelationshipPopup(): void {
  if (relationshipPopupContainer && relationshipContent) {
    relationshipPopupContainer.classList.add('visible');

    // Only render if we have game data
    if (gameState.gameData) {
      renderRelationshipChart();
    } else {
      relationshipContent.innerHTML = '<div class="no-data-message">No game data loaded. Please load a game to view relationships.</div>';
    }
  }
}

/**
 * Hide the relationship popup
 */
export function hideRelationshipPopup(): void {
  if (relationshipPopupContainer) {
    relationshipPopupContainer.classList.remove('visible');
  }
}

/**
 * Render the relationship chart in the popup
 */
function renderRelationshipChart(): void {
  if (!relationshipContent || !gameState.gameData) return;

  // Clear current content
  relationshipContent.innerHTML = '';

  // Get a list of powers that have relationship data
  const powersWithRelationships = new Set<string>();

  // Check all phases for relationships
  if (gameState.gameData && gameState.gameData.phases) {
    // Debug what relationship data we have

    let hasRelationshipData = false;
    for (const phase of gameState.gameData.phases) {
      if (phase.agent_relationships) {
        hasRelationshipData = true;
        // Add powers that have relationship data defined
        Object.keys(phase.agent_relationships).forEach(power => {
          powersWithRelationships.add(power);
        });
      }
    }

    if (!hasRelationshipData) {
      console.log("No relationship data found in any phase");
    }
  }

  // Create a container for each power's relationship chart
  for (const power of Object.values(PowerENUM)) {
    // Skip any non-string values
    if (typeof power !== 'string') continue;

    // Check if this power has relationship data
    if (powersWithRelationships.has(power)) {
      const powerContainer = document.createElement('div');
      powerContainer.className = `power-relationship-container power-${power.toLowerCase()}`;

      const powerHeader = document.createElement('h3');
      powerHeader.className = `power-${power.toLowerCase()}`;
      powerHeader.textContent = getPowerDisplayName(power as PowerENUM);
      powerContainer.appendChild(powerHeader);

      const chartContainer = document.createElement('div');
      chartContainer.className = 'relationship-chart-container';

      // Use the existing chart rendering function
      renderRelationshipHistoryChartView(
        chartContainer,
        gameState.gameData,
        gameState.phaseIndex,
        power as PowerENUM
      );

      powerContainer.appendChild(chartContainer);
      relationshipContent.appendChild(powerContainer);
    }
  }

  // If no powers have relationship data, create message to say so
  if (powersWithRelationships.size === 0) {
    console.log("No relationship data found in game");

    // Create sample relationship data for all powers in the game
    const allPowers = new Set<string>();

    // Find all powers from units and centers
    if (gameState.gameData && gameState.gameData.phases && gameState.gameData.phases.length > 0) {
      const currentPhase = gameState.gameData.phases[gameState.phaseIndex];

      if (currentPhase.state?.units) {
        Object.keys(currentPhase.state.units).forEach(power => allPowers.add(power));
      }

      if (currentPhase.state?.centers) {
        Object.keys(currentPhase.state.centers).forEach(power => allPowers.add(power));
      }

      // Only proceed if we found some powers
      if (allPowers.size > 0) {
        console.log(`Found ${allPowers.size} powers in game, creating sample relationships`);

        // For each power, create a container and chart
        for (const power of allPowers) {
          const powerContainer = document.createElement('div');
          powerContainer.className = `power-relationship-container power-${power.toLowerCase()}`;

          const powerHeader = document.createElement('h3');
          powerHeader.className = `power-${power.toLowerCase()}`;
          powerHeader.textContent = getPowerDisplayName(power as PowerENUM);
          powerContainer.appendChild(powerHeader);

          const chartContainer = document.createElement('div');
          chartContainer.className = 'relationship-chart-container';

          // Create a message about sample data
          const sampleMessage = document.createElement('div');
          sampleMessage.className = 'sample-data-message';
          sampleMessage.innerHTML = `<strong>Note:</strong> No relationship data found for ${power}. 
                                     This chart will display when relationship data is available.`;

          chartContainer.appendChild(sampleMessage);
          powerContainer.appendChild(chartContainer);
          relationshipContent.appendChild(powerContainer);
        }
      } else {
        // If we couldn't find any powers, show the no data message
        const noDataMsg = document.createElement('div');
        noDataMsg.className = 'no-data-message';
        noDataMsg.textContent = 'No relationship data available in this game file.';
        relationshipContent.appendChild(noDataMsg);
      }
    } else {
      // If no phases, show the no data message
      const noDataMsg = document.createElement('div');
      noDataMsg.className = 'no-data-message';
      noDataMsg.textContent = 'No relationship data available in this game file.';
      relationshipContent.appendChild(noDataMsg);
    }
  }
}

/**
 * Update the relationship popup when game data changes
 */
export function updateRelationshipPopup(): void {
  if (relationshipPopupContainer &&
    relationshipPopupContainer.classList.contains('visible')) {
    renderRelationshipChart();
  }
}
