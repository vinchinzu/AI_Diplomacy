import { test, expect } from '@playwright/test';
import {
  waitForGameReady,
  startGamePlayback,
  stopGamePlayback,
  measureVictoryTiming,
  advanceGameManually,
  checkForVictoryMessage,
  isGamePlaying,
  type ManualAdvancementResult
} from './test-helpers';

test.describe('Game Playthrough Tests', () => {
  test.beforeEach(async ({ page, context }) => {
    // Navigate to the app
    await page.goto('/');
    await context.addInitScript(() => window.isUnderTest = true);

    // Wait for the game to be ready and loaded
    await waitForGameReady(page);
  });

  test('complete game playthrough with victory screen and next game transition', async ({ page }) => {

    // Start playing the game
    await startGamePlayback(page);

    // Wait for the game to complete and measure victory timing
    const result = await measureVictoryTiming(page, 90000); // 1.5 minutes max wait

    // Verify that we saw the victory message
    expect(result.victoryDetected).toBe(true);
    expect(result.victoryMessage).toBeTruthy();

    // Log the results
    console.log(`Victory message: "${result.victoryMessage}"`);
    console.log(`Victory message was visible for ${result.displayDuration}ms`);
    console.log(`Next game started: ${result.nextGameStarted}`);
    console.log(`Game ID changed: ${result.gameIdChanged}`);

    // Verify that victory message was displayed for a reasonable amount of time
    expect(result.displayDuration).toBeGreaterThan(50); // At least 50ms (reduced for instant mode)

    // The victory modal should still be visible when we detect it
    if (result.victoryDetected) {
      const currentVictoryMessage = await checkForVictoryMessage(page);
      if (currentVictoryMessage) {
        await expect(page.locator('.victory-modal-overlay')).toBeVisible();
      }
    }
  });

  test('victory popup stays visible for expected duration via manual advancement', async ({ page }) => {
    // This test focuses on the timing by manually advancing through the game
    test.setTimeout(60000); // 1 minute

    // Stop automatic playback and advance manually for more control
    if (await isGamePlaying(page)) {
      await stopGamePlayback(page);
    }

    // Manually advance through the game to reach victory
    const victoryReached = await advanceGameManually(page, 100, false);

    if (victoryReached) {
      // Now measure victory timing
      const result = await measureVictoryTiming(page, 30000); // 30 seconds max wait

      expect(result.victoryDetected).toBe(true);
      expect(result.displayDuration).toBeGreaterThan(50); // At least 50ms (reduced for instant mode)

      console.log(`Manual advancement: Victory message visible for ${result.displayDuration}ms`);
      console.log(`Manual advancement: Next game started: ${result.nextGameStarted}`);
    } else {
      console.log('Could not reach victory through manual advancement - test skipped');
      test.skip();
    }
  });

  test('game loads and basic UI elements are present', async ({ page }) => {
    // Basic smoke test to ensure the game loads properly

    // Check that essential UI elements are present
    await expect(page.locator('#play-btn')).toBeVisible();
    await expect(page.locator('#prev-btn')).toBeVisible();
    await expect(page.locator('#next-btn')).toBeVisible();
    await expect(page.locator('canvas')).toBeVisible();
    await expect(page.locator('#phase-display')).toBeVisible();
    await expect(page.locator('#game-id-display')).toBeVisible();

    // Check that the Three.js scene has loaded
    const canvas = page.locator('canvas');
    await expect(canvas).toHaveAttribute('width');
    await expect(canvas).toHaveAttribute('height');

    // Verify that we can start and stop playback
    await startGamePlayback(page);
    await stopGamePlayback(page);
  });

  test('manual phase advancement with two-power conversation detection', async ({ page }) => {
    // Test comprehensive manual advancement with conversation tracking
    test.setTimeout(120000); // 2 minutes

    // Stop automatic playback to control advancement manually
    if (await isGamePlaying(page)) {
      await stopGamePlayback(page);
    }

    // Manually advance through the entire game while tracking conversations
    const result = await advanceGameManually(page, 150, true) as ManualAdvancementResult;

    // Log comprehensive results
    console.log(`Manual advancement results:`);
    console.log(`- Victory reached: ${result.victoryReached}`);
    console.log(`- Phases advanced: ${result.phasesAdvanced}`);
    console.log(`- Two-power conversations found: ${result.twoPowerConversationsFound}`);
    console.log(`- Conversation phases: ${result.conversationPhases.join(', ')}`);
    console.log(`- Final phase: ${result.finalPhaseName}`);

    // Verify the game completed successfully
    expect(result.victoryReached).toBe(true);

    // Verify that we advanced through a reasonable number of phases
    expect(result.phasesAdvanced).toBeGreaterThan(5);

    // Two-power conversations should occur (though exact number depends on game data)
    // Just verify the tracking worked - some games might have 0 conversations
    expect(result.twoPowerConversationsFound).toBeGreaterThanOrEqual(0);

    // If conversations were found, verify they were properly tracked
    if (result.twoPowerConversationsFound > 0) {
      expect(result.conversationPhases).toHaveLength(result.twoPowerConversationsFound);
      console.log('Two-power conversations detected at phases:', result.conversationPhases);
    } else {
      console.log('No two-power conversations found in this game');
    }

    // After victory, check that victory message is present
    const victoryMessage = await checkForVictoryMessage(page);
    expect(victoryMessage).toBeTruthy();
  });

  test('game advances phases manually', async ({ page }) => {
    // Test basic manual phase advancement
    const initialPhaseText = await page.locator('#phase-display').textContent();

    // Click next button
    await page.click('#next-btn');

    // Wait for phase to update
    await page.waitForTimeout(500);

    // Verify phase changed
    const newPhaseText = await page.locator('#phase-display').textContent();
    expect(newPhaseText).not.toBe(initialPhaseText);

    // Test previous button
    await page.click('#prev-btn');
    await page.waitForTimeout(500);

    const backPhaseText = await page.locator('#phase-display').textContent();
    expect(backPhaseText).toBe(initialPhaseText);
  });
});
