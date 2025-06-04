import { Page, expect } from '@playwright/test';

/**
 * Helper function to wait for the game to be ready and loaded
 */
export async function waitForGameReady(page: Page, timeout = 15000): Promise<void> {
  // Wait for the app to fully load
  await page.waitForLoadState('networkidle');

  // Wait for Three.js scene to initialize
  await page.waitForSelector('canvas', { timeout });

  // Wait for essential UI elements to be present
  await expect(page.locator('#play-btn')).toBeVisible({ timeout });
  await expect(page.locator('#prev-btn')).toBeVisible({ timeout });
  await expect(page.locator('#next-btn')).toBeVisible({ timeout });

  // Ensure play button is enabled (indicating game is loaded)
  await expect(page.locator('#play-btn')).toBeEnabled({ timeout });

}

/**
 * Helper function to start game playback and verify it started
 */
export async function startGamePlayback(page: Page): Promise<void> {
  await page.click('#play-btn');
  await expect(page.locator('#play-btn')).toHaveText(/⏸ Pause/);
}

/**
 * Helper function to stop game playback and verify it stopped
 */
export async function stopGamePlayback(page: Page): Promise<void> {
  await page.click('#play-btn');
  await expect(page.locator('#play-btn')).toHaveText(/▶ Play/);
}

/**
 * Helper function to check if a victory message is present (checks for victory modal)
 */
export async function checkForVictoryMessage(page: Page): Promise<string | null> {
  try {
    // Check for victory modal
    const victoryModal = page.locator('.victory-modal-overlay');
    if (await victoryModal.isVisible()) {
      // Extract victory message from modal
      const winnerText = await victoryModal.locator('h2').textContent();
      if (winnerText) {
        return winnerText;
      }
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Helper function to get current game ID
 */
export async function getCurrentGameId(page: Page): Promise<string | null> {
  try {
    return await page.locator('#game-id-display').textContent();
  } catch {
    return null;
  }
}

/**
 * Helper function to check if game is still playing
 */
export async function isGamePlaying(page: Page): Promise<boolean> {
  try {
    const playButtonText = await page.locator('#play-btn').textContent();
    return playButtonText?.includes('⏸') || false;
  } catch {
    return false;
  }
}

/**
 * Interface for victory timing measurement result
 */
export interface VictoryTimingResult {
  victoryDetected: boolean;
  victoryMessage: string | null;
  displayDuration: number;
  nextGameStarted: boolean;
  gameIdChanged: boolean;
}

/**
 * Helper function to measure victory message timing and next game transition
 */
export async function measureVictoryTiming(
  page: Page,
  maxWaitTime = 60000
): Promise<VictoryTimingResult> {
  const startTime = Date.now();
  let victoryMessage: string | null = null;
  let victoryDetected = false;
  let victoryStartTime = 0;
  let nextGameStarted = false;
  let gameIdChanged = false;
  let initialGameId: string | null = null;

  // Get initial game ID
  initialGameId = await getCurrentGameId(page);

  while ((Date.now() - startTime) < maxWaitTime) {
    // Check for victory message
    if (!victoryDetected) {
      victoryMessage = await checkForVictoryMessage(page);
      if (victoryMessage) {
        victoryDetected = true;
        victoryStartTime = Date.now();
        console.log('Victory message detected:', victoryMessage);
      }
    }

    // If victory was detected, monitor for next game transition
    if (victoryDetected) {
      // Check if game ID changed
      const currentGameId = await getCurrentGameId(page);
      if (currentGameId && currentGameId !== initialGameId) {
        gameIdChanged = true;
        nextGameStarted = true;
        console.log('Game ID changed from', initialGameId, 'to', currentGameId);
        break;
      }

      // Check if victory modal disappeared (indicating new game started)
      const victoryModal = page.locator('.victory-modal-overlay');
      const isModalVisible = await victoryModal.isVisible();
      if (!isModalVisible) {
        nextGameStarted = true;
        console.log('Victory modal disappeared, indicating new game started');
        break;
      }
    }

    await page.waitForTimeout(500);
  }

  const displayDuration = victoryDetected ? Date.now() - victoryStartTime : 0;

  return {
    victoryDetected,
    victoryMessage,
    displayDuration,
    nextGameStarted,
    gameIdChanged
  };
}

/**
 * Helper function to check if a two-power conversation is currently displayed
 */
export async function isTwoPowerConversationOpen(page: Page): Promise<boolean> {
  try {
    // Look for the dialogue overlay that appears when a two-power conversation is shown
    const overlay = page.locator('.dialogue-overlay');
    return await overlay.isVisible();
  } catch {
    return false;
  }
}

/**
 * Helper function to wait for a two-power conversation to close
 */
export async function waitForTwoPowerConversationToClose(page: Page, timeout = 5000): Promise<void> {
  const startTime = Date.now();
  while ((Date.now() - startTime) < timeout) {
    const isOpen = await isTwoPowerConversationOpen(page);
    if (!isOpen) {
      return;
    }
    await page.waitForTimeout(100);
  }
}

/**
 * Helper function to get current phase name
 */
export async function getCurrentPhaseName(page: Page): Promise<string | null> {
  try {
    const phaseText = await page.locator('#phase-display').textContent();
    // Extract phase name from "Era: {phaseName}" format
    return phaseText?.replace('Era: ', '') || null;
  } catch {
    return null;
  }
}

/**
 * Interface for manual advancement result
 */
export interface ManualAdvancementResult {
  victoryReached: boolean;
  phasesAdvanced: number;
  twoPowerConversationsFound: number;
  conversationPhases: string[];
  finalPhaseName: string | null;
}

/**
 * Helper function to advance game manually by clicking next button with conversation tracking
 */
export async function advanceGameManually(
  page: Page,
  maxClicks = 50,
  trackConversations = false
): Promise<boolean | ManualAdvancementResult> {
  let clicks = 0;
  let twoPowerConversationsFound = 0;
  const conversationPhases: string[] = [];

  while (clicks < maxClicks) {
    try {
      // Check for victory message first
      const victoryMessage = await checkForVictoryMessage(page);
      if (victoryMessage) {
        if (trackConversations) {
          return {
            victoryReached: true,
            phasesAdvanced: clicks,
            twoPowerConversationsFound,
            conversationPhases,
            finalPhaseName: await getCurrentPhaseName(page)
          };
        }
        return true; // Victory reached
      }

      // Get current phase name for tracking
      const currentPhase = await getCurrentPhaseName(page);

      // Check if we can advance
      const nextButton = page.locator('#next-btn');
      if (await nextButton.isEnabled()) {

        // If tracking conversations, check if one opened after clicking next
        if (trackConversations) {
          await page.waitForTimeout(300); // Give time for conversation to appear
          const conversationOpen = await isTwoPowerConversationOpen(page);

          if (conversationOpen) {
            twoPowerConversationsFound++;
            if (currentPhase) {
              conversationPhases.push(currentPhase);
            }
            console.log(`Two-power conversation detected at phase: ${currentPhase}`);

            // Wait for conversation to close automatically or close it manually
            await waitForTwoPowerConversationToClose(page, 35000); // 35 seconds max
          }
          await nextButton.click();
          await page.waitForTimeout(100);
        }
      } else {
        // Can't advance anymore, might be at end
        break;
      }

      clicks++;
    } catch (error) {
      console.log('Error during manual advance:', error);
      break;
    }
  }

  if (trackConversations) {
    return {
      victoryReached: false,
      phasesAdvanced: clicks,
      twoPowerConversationsFound,
      conversationPhases,
      finalPhaseName: await getCurrentPhaseName(page)
    };
  }

  return false; // Didn't reach victory
}
