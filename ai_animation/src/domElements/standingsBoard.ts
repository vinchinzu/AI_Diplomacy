import { StandingsData, StandingsEntry, SortBy, SortDirection, SortOptions } from '../types/standings';
import { gameState } from '../gameState';
import { logger } from '../logger';
import { standingsBtn } from '../domElements';

// DOM element references
let standingsBoardContainer: HTMLElement | null = null;
let standingsTable: HTMLElement | null = null;
let closeButton: HTMLElement | null = null;

// Current data and state
let standingsData: StandingsData | null = null;
let currentSort: SortOptions = {
  by: SortBy.TOTAL_WINS,
  direction: SortDirection.DESC
};

/**
 * Initialize the standings board by creating DOM elements and attaching event handlers
 */
export function initStandingsBoard(): void {
  // Create the container if it doesn't exist
  if (!document.getElementById('standings-board-container')) {
    createStandingsBoardElements();
  }
  
  // Get references to the created elements
  standingsBoardContainer = document.getElementById('standings-board-container');
  standingsTable = document.getElementById('standings-table');
  closeButton = document.getElementById('standings-close-btn');
  
  // Add event listeners
  if (closeButton) {
    closeButton.addEventListener('click', hideStandingsBoard);
  }
  
  // Add click handler for the standings button
  if (standingsBtn) {
    standingsBtn.addEventListener('click', toggleStandingsBoard);
  }
  
  // Load standings data
  loadStandingsData();
}

/**
 * Create all DOM elements needed for the standings board
 */
function createStandingsBoardElements(): void {
  const container = document.createElement('div');
  container.id = 'standings-board-container';
  container.className = 'standings-board-container';
  
  // Create header
  const header = document.createElement('div');
  header.className = 'standings-header';
  
  const title = document.createElement('h2');
  title.textContent = 'AI Diplomacy Leaderboard';
  header.appendChild(title);
  
  const closeBtn = document.createElement('button');
  closeBtn.id = 'standings-close-btn';
  closeBtn.textContent = '×';
  closeBtn.title = 'Close Leaderboard';
  header.appendChild(closeBtn);
  
  container.appendChild(header);
  
  // Create table container
  const tableContainer = document.createElement('div');
  tableContainer.className = 'standings-table-container';
  
  const table = document.createElement('table');
  table.id = 'standings-table';
  table.className = 'standings-table';
  tableContainer.appendChild(table);
  
  container.appendChild(tableContainer);
  
  // Create legend/info section
  const legend = document.createElement('div');
  legend.className = 'standings-legend';
  legend.innerHTML = `
    <p>Numbers indicate wins per Power-Model combination. Click column headers to sort.</p>
  `;
  container.appendChild(legend);
  
  // Add to document
  document.body.appendChild(container);
}

/**
 * Load standings data from CSV
 */
function loadStandingsData(): void {
  fetch('./standings.csv')
    .then(response => {
      if (!response.ok) {
        throw new Error(`Failed to load standings data: ${response.status}`);
      }
      return response.text();
    })
    .then(csvText => {
      standingsData = parseCSV(csvText);
      renderStandingsTable();
    })
    .catch(error => {
      console.error('Error loading standings data:', error);
      logger.log(`Error loading standings: ${error.message}`);
    });
}

/**
 * Parse CSV data into our StandingsData format
 */
function parseCSV(csvText: string): StandingsData {
  const lines = csvText.split('\n').filter(line => line.trim().length > 0);
  const headers = lines[0].split(',').map(h => h.trim());
  
  // First column is 'Model', rest are power names
  const powers = headers.slice(1);
  
  // Process each data row
  const entries: StandingsEntry[] = [];
  const models: string[] = [];
  
  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',').map(v => v.trim());
    const model = values[0];
    models.push(model);
    
    // Create wins record
    const wins: Record<string, number> = {};
    let totalWins = 0;
    
    for (let j = 1; j < values.length; j++) {
      const power = powers[j - 1];
      const winCount = parseInt(values[j]) || 0;
      wins[power] = winCount;
      totalWins += winCount;
    }
    
    entries.push({ model, wins, totalWins });
  }
  
  return { models, powers, entries };
}

/**
 * Render the standings table with current data and sort options
 */
function renderStandingsTable(): void {
  if (!standingsTable || !standingsData) return;
  
  // Clear existing content
  standingsTable.innerHTML = '';
  
  // Create header row
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  
  // Model column header
  const modelHeader = document.createElement('th');
  modelHeader.textContent = 'Model';
  modelHeader.className = 'model-header';
  modelHeader.addEventListener('click', () => sortTable(SortBy.MODEL));
  headerRow.appendChild(modelHeader);
  
  // Power column headers
  standingsData.powers.forEach(power => {
    const th = document.createElement('th');
    th.textContent = power;
    th.className = `power-header power-${power.toLowerCase()}`;
    th.addEventListener('click', () => sortTable(`power_${power}`));
    headerRow.appendChild(th);
  });
  
  // Total column header
  const totalHeader = document.createElement('th');
  totalHeader.textContent = 'Total';
  totalHeader.className = 'total-header';
  totalHeader.addEventListener('click', () => sortTable(SortBy.TOTAL_WINS));
  headerRow.appendChild(totalHeader);
  
  thead.appendChild(headerRow);
  standingsTable.appendChild(thead);
  
  // Sort entries based on current sort options
  const sortedEntries = [...standingsData.entries].sort((a, b) => {
    if (currentSort.by === SortBy.MODEL) {
      const comparison = a.model.localeCompare(b.model);
      return currentSort.direction === SortDirection.ASC ? comparison : -comparison;
    } 
    else if (currentSort.by === SortBy.TOTAL_WINS) {
      const comparison = a.totalWins - b.totalWins;
      return currentSort.direction === SortDirection.ASC ? comparison : -comparison;
    }
    else if (currentSort.by.startsWith('power_')) {
      const power = currentSort.by.replace('power_', '');
      const comparison = (a.wins[power] || 0) - (b.wins[power] || 0);
      return currentSort.direction === SortDirection.ASC ? comparison : -comparison;
    }
    return 0;
  });
  
  // Create table body
  const tbody = document.createElement('tbody');
  
  sortedEntries.forEach(entry => {
    const row = document.createElement('tr');
    
    // Model cell
    const modelCell = document.createElement('td');
    modelCell.textContent = entry.model;
    modelCell.className = 'model-cell';
    row.appendChild(modelCell);
    
    // Power cells
    standingsData.powers.forEach(power => {
      const td = document.createElement('td');
      const wins = entry.wins[power] || 0;
      td.textContent = wins.toString();
      td.className = `power-cell power-${power.toLowerCase()} ${wins > 0 ? 'has-wins' : ''}`;
      // Add additional classes for high win counts
      if (wins >= 4) td.classList.add('high-wins');
      if (wins >= 5) td.classList.add('top-wins');
      row.appendChild(td);
    });
    
    // Total cell
    const totalCell = document.createElement('td');
    totalCell.textContent = entry.totalWins.toString();
    totalCell.className = 'total-cell';
    row.appendChild(totalCell);
    
    tbody.appendChild(row);
  });
  
  standingsTable.appendChild(tbody);
  
  // Update sort indicators
  updateSortIndicators();
}

/**
 * Update sort indicator classes on table headers
 */
function updateSortIndicators(): void {
  if (!standingsTable) return;
  
  // Remove all sort indicators
  const allHeaders = standingsTable.querySelectorAll('th');
  allHeaders.forEach(header => {
    header.classList.remove('sort-asc', 'sort-desc');
  });
  
  // Add indicator to current sort column
  let headerSelector = '.model-header';
  
  if (currentSort.by === SortBy.TOTAL_WINS) {
    headerSelector = '.total-header';
  } 
  else if (currentSort.by.startsWith('power_')) {
    const power = currentSort.by.replace('power_', '');
    headerSelector = `.power-${power.toLowerCase()}`;
  }
  
  const header = standingsTable.querySelector(headerSelector);
  if (header) {
    header.classList.add(
      currentSort.direction === SortDirection.ASC ? 'sort-asc' : 'sort-desc'
    );
  }
}

/**
 * Sort the table by the specified column
 */
function sortTable(sortBy: SortBy | string): void {
  if (currentSort.by === sortBy) {
    // Toggle direction if already sorting by this column
    currentSort.direction = 
      currentSort.direction === SortDirection.ASC 
        ? SortDirection.DESC 
        : SortDirection.ASC;
  } else {
    // Set new sort column with default direction
    currentSort = {
      by: sortBy,
      direction: sortBy === SortBy.MODEL ? SortDirection.ASC : SortDirection.DESC
    };
  }
  
  renderStandingsTable();
}

/**
 * Toggle the visibility of the standings board
 */
export function toggleStandingsBoard(): void {
  if (standingsBoardContainer) {
    if (standingsBoardContainer.classList.contains('visible')) {
      hideStandingsBoard();
    } else {
      showStandingsBoard();
    }
  }
}

/**
 * Show the standings board
 */
export function showStandingsBoard(): void {
  if (standingsBoardContainer) {
    standingsBoardContainer.classList.add('visible');
  }
}

/**
 * Hide the standings board
 */
export function hideStandingsBoard(): void {
  if (standingsBoardContainer) {
    standingsBoardContainer.classList.remove('visible');
  }
}

/**
 * Auto-display standings board based on game state
 * Shows when no game is loaded, hides when a game is loaded
 */
export function updateStandingsBoardVisibility(): void {
  if (!gameState.gameData || gameState.gameData.phases.length === 0) {
    showStandingsBoard();
  } else {
    hideStandingsBoard();
  }
} 