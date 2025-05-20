import { PowerENUM } from "../types/map";
import { GameSchemaType } from "../types/gameState";

// Relationship value mapping
const RELATIONSHIP_VALUES = {
  "Enemy": -2,
  "Unfriendly": -1,
  "Neutral": 0,
  "Friendly": 1,
  "Ally": 2,
  // Add lowercase versions for case-insensitive matching
  "enemy": -2,
  "unfriendly": -1,
  "neutral": 0,
  "friendly": 1,
  "ally": 2
};
/**
 * Render the relationship history chart view
 * @param container The container element
 * @param gameData The current game data
 * @param currentPhaseIndex The current phase index
 * @param currentPlayerPower The power the current player is controlling
 */
export function renderRelationshipHistoryChartView(
  container: HTMLElement,
  gameData: GameSchemaType,
  currentPhaseIndex: number,
  currentPlayerPower: PowerENUM
): void {
  // Create header and description
  const header = document.createElement('div');
  header.innerHTML = `<strong>Diplomatic Relations</strong> <span class="power-${currentPlayerPower.toLowerCase()}">(${currentPlayerPower})</span>`;
  container.appendChild(header);

  // Prepare data for the chart
  const relationshipHistory = [];
  const otherPowers = new Set<string>();

  // Iterate through all phases to collect relationship data
  for (let i = 0; i < gameData.phases.length; i++) {
    const phase = gameData.phases[i];
    const phaseData: any = {
      phaseName: phase.name,
      phaseIndex: i
    };

    // Check if agent_relationships exists and has data for current player
    if (phase.agent_relationships &&
      phase.agent_relationships[currentPlayerPower]) {

      console.log(`Phase ${i} (${phase.name}): Found relationships for ${currentPlayerPower}`,
        phase.agent_relationships[currentPlayerPower]);

      const relationships = phase.agent_relationships[currentPlayerPower];

      for (const [power, relation] of Object.entries(relationships)) {
        if (power !== currentPlayerPower) {
          // Convert relationship string to numeric value
          let relationValue = RELATIONSHIP_VALUES[relation as keyof typeof RELATIONSHIP_VALUES];

          // Default to neutral if the relationship string is not recognized
          if (relationValue === undefined) {
            relationValue = 0;
            console.warn(`Unknown relationship value: ${relation}, defaulting to Neutral (0)`);
          }

          console.log(`  Relationship ${currentPlayerPower} -> ${power}: ${relation} (${relationValue})`);

          phaseData[power] = relationValue;
          otherPowers.add(power);
        }
      }
    }

    relationshipHistory.push(phaseData);
  }

  console.log("Collected relationship history:", relationshipHistory);
  console.log("Other powers found:", Array.from(otherPowers));

  // Convert otherPowers Set to Array for easier iteration
  const powers = Array.from(otherPowers);

  // Create SVG element
  const svgWidth = container.clientWidth;
  const svgHeight = 150;
  const margin = { top: 10, right: 10, bottom: 20, left: 25 };
  const width = svgWidth - margin.left - margin.right;
  const height = svgHeight - margin.top - margin.bottom;

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", `${svgHeight}px`);
  svg.setAttribute("viewBox", `0 0 100% ${svgHeight}`);
  svg.style.overflow = "visible";

  // Create SVG group for the chart content with margins
  const chart = document.createElementNS("http://www.w3.org/2000/svg", "g");
  chart.setAttribute("transform", `translate(${margin.left},${margin.top})`);
  svg.appendChild(chart);

  // Create scales
  // X scale: map phase index to x position
  const xScale = (index: number) => {
    const denominator = Math.max(1, relationshipHistory.length - 1); // Avoid division by zero
    return margin.left + (index / denominator) * width;
  };

  // Y scale: map relationship value (-2 to 2) to y position
  const yScale = (value: number) => margin.top + height / 2 - (value / 2) * (height / 2);

  // Draw axes
  // X-axis (middle, represents neutral)
  const xAxis = document.createElementNS("http://www.w3.org/2000/svg", "line");
  xAxis.setAttribute("x1", `${margin.left}`);
  xAxis.setAttribute("y1", `${yScale(0)}`);
  xAxis.setAttribute("x2", `${margin.left + width}`);
  xAxis.setAttribute("y2", `${yScale(0)}`);
  xAxis.setAttribute("stroke", "#8d5a2b");
  xAxis.setAttribute("stroke-width", "1");
  chart.appendChild(xAxis);

  // Y-axis
  const yAxis = document.createElementNS("http://www.w3.org/2000/svg", "line");
  yAxis.setAttribute("x1", `${margin.left}`);
  yAxis.setAttribute("y1", `${margin.top}`);
  yAxis.setAttribute("x2", `${margin.left}`);
  yAxis.setAttribute("y2", `${margin.top + height}`);
  yAxis.setAttribute("stroke", "#8d5a2b");
  yAxis.setAttribute("stroke-width", "1");
  chart.appendChild(yAxis);

  // Y-axis ticks and labels
  const yTicks = [-2, -1, 0, 1, 2];
  const yTickLabels = ["Enemy", "Unfriendly", "Neutral", "Friendly", "Ally"];

  for (let i = 0; i < yTicks.length; i++) {
    const tick = yTicks[i];
    const label = yTickLabels[i];

    // Tick line
    const tickLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    tickLine.setAttribute("x1", `${margin.left - 5}`);
    tickLine.setAttribute("y1", `${yScale(tick)}`);
    tickLine.setAttribute("x2", `${margin.left}`);
    tickLine.setAttribute("y2", `${yScale(tick)}`);
    tickLine.setAttribute("stroke", "#8d5a2b");
    tickLine.setAttribute("stroke-width", "1");
    chart.appendChild(tickLine);

    // Tick label
    const tickLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    tickLabel.setAttribute("x", `${margin.left - 8}`);
    tickLabel.setAttribute("y", `${yScale(tick) + 4}`);
    tickLabel.setAttribute("text-anchor", "end");
    tickLabel.setAttribute("font-size", "9");
    tickLabel.setAttribute("fill", "#3b2c02");
    tickLabel.textContent = label;
    chart.appendChild(tickLabel);
  }

  // Draw horizontal grid lines
  for (const tick of yTicks) {
    const gridLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    gridLine.setAttribute("x1", `${margin.left}`);
    gridLine.setAttribute("y1", `${yScale(tick)}`);
    gridLine.setAttribute("x2", `${margin.left + width}`);
    gridLine.setAttribute("y2", `${yScale(tick)}`);
    gridLine.setAttribute("stroke", "#d3bf96");
    gridLine.setAttribute("stroke-width", "0.5");
    gridLine.setAttribute("stroke-dasharray", "3,3");
    chart.appendChild(gridLine);
  }

  // Draw lines for each power
  for (const power of powers) {
    console.log(`Drawing line for power: ${power}`);

    // Create path for this power
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");

    // Generate path data
    let pathData = "";
    let hasData = false;
    let dataPoints = 0;

    for (let i = 0; i < relationshipHistory.length; i++) {
      if (relationshipHistory[i][power] !== undefined) {
        const relationValue = relationshipHistory[i][power];
        const x = xScale(i);
        const y = yScale(relationValue);

        console.log(`  Point ${i}: (${x}, ${y}) for value ${relationValue}`);
        dataPoints++;

        if (!hasData) {
          pathData += `M ${x} ${y}`;
          hasData = true;
        } else {
          pathData += ` L ${x} ${y}`;
        }
      }
    }

    console.log(`  Total data points for ${power}: ${dataPoints}, has data: ${hasData}`);
    console.log(`  Path data: ${pathData.length > 100 ? pathData.substring(0, 100) + '...' : pathData}`);

    if (hasData) {
      path.setAttribute("d", pathData);
      path.setAttribute("stroke", POWER_COLORS[power] || "#000000");
      path.setAttribute("stroke-width", "2");
      path.setAttribute("fill", "none");
      chart.appendChild(path);
      console.log(`  Added path to chart for ${power}`);
    } else {
      console.log(`  No path data for ${power}, not adding to chart`);
    }
  }

  // Add a vertical line to indicate current phase
  const currentPhaseX = xScale(currentPhaseIndex);
  const currentPhaseLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
  currentPhaseLine.setAttribute("x1", `${currentPhaseX}`);
  currentPhaseLine.setAttribute("y1", `${margin.top}`);
  currentPhaseLine.setAttribute("x2", `${currentPhaseX}`);
  currentPhaseLine.setAttribute("y2", `${margin.top + height}`);
  currentPhaseLine.setAttribute("stroke", "#000000");
  currentPhaseLine.setAttribute("stroke-width", "1");
  currentPhaseLine.setAttribute("stroke-dasharray", "3,3");
  chart.appendChild(currentPhaseLine);

  // Add legend
  const legendGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
  legendGroup.setAttribute("transform", `translate(${margin.left}, ${margin.top + height + 10})`);

  let legendX = 0;
  const legendItemWidth = width / powers.length;

  for (const power of powers) {
    // Legend color box
    const legendBox = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    legendBox.setAttribute("x", `${legendX}`);
    legendBox.setAttribute("y", "0");
    legendBox.setAttribute("width", "10");
    legendBox.setAttribute("height", "10");
    legendBox.setAttribute("fill", POWER_COLORS[power] || "#000000");
    legendGroup.appendChild(legendBox);

    // Legend text
    const legendText = document.createElementNS("http://www.w3.org/2000/svg", "text");
    legendText.setAttribute("x", `${legendX + 15}`);
    legendText.setAttribute("y", "8");
    legendText.setAttribute("font-size", "9");
    legendText.setAttribute("fill", "#3b2c02");
    legendText.textContent = power;
    legendGroup.appendChild(legendText);

    legendX += legendItemWidth;
  }

  chart.appendChild(legendGroup);

  // Add the SVG to the container
  container.appendChild(svg);

  // Add phase info
  const phaseInfo = document.createElement('div');
  phaseInfo.style.fontSize = '12px';
  phaseInfo.style.marginTop = '5px';
  phaseInfo.innerHTML = `Current phase: ${gameData.phases[currentPhaseIndex].name}`;
  container.appendChild(phaseInfo);
}
