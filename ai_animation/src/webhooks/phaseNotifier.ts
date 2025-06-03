import { config } from '../config';
import { gameState } from '../gameState';

// Test webhook URL validity on startup
testWebhookUrl().catch(err => console.error("Webhook test failed:", err));

async function testWebhookUrl() {
  const webhookUrl = config.webhookUrl || import.meta.env.VITE_WEBHOOK_URL || '';
  
  if (!webhookUrl) {
    console.log("⚠️  No webhook URL configured (optional feature)");
    return;
  }

  try {
    // For Discord webhooks, we can test with a GET request
    if (webhookUrl.includes('discord.com/api/webhooks')) {
      const response = await fetch(webhookUrl, {
        method: 'GET',
      });

      if (response.ok) {
        const webhookInfo = await response.json();
        console.log(`✅ Discord webhook is valid and ready (${webhookInfo.name || 'Unnamed webhook'})`);
      } else if (response.status === 401) {
        console.error(`❌ Discord webhook invalid: Unauthorized (check webhook URL)`);
      } else {
        console.error(`❌ Discord webhook error: ${response.status}`);
      }
    } else {
      // For non-Discord webhooks, just validate the URL format
      try {
        new URL(webhookUrl);
        console.log(`✅ Webhook URL is valid: ${webhookUrl.substring(0, 50)}...`);
      } catch {
        console.error(`❌ Invalid webhook URL format`);
      }
    }
  } catch (error) {
    console.error("❌ Webhook connection error:", error);
  }
}

/**
 * Sends a webhook notification when a phase changes
 * This is a fire-and-forget operation that won't block the UI
 */
export async function notifyPhaseChange(oldPhaseIndex: number, newPhaseIndex: number): Promise<void> {
  console.log(`[Webhook] Phase change detected: ${oldPhaseIndex} -> ${newPhaseIndex}`);
  
  // Skip if no webhook URL is configured
  if (!config.webhookUrl) {
    console.log('[Webhook] No webhook URL configured, skipping notification');
    return;
  }

  // Skip if game data is not loaded
  if (!gameState.gameData || !gameState.gameData.phases) {
    console.warn('[Webhook] Game data not loaded, cannot send notification');
    return;
  }

  const currentPhase = gameState.gameData.phases[newPhaseIndex];
  if (!currentPhase) {
    console.warn(`[Webhook] Phase at index ${newPhaseIndex} not found`);
    return;
  }

  // Determine direction of phase change
  let direction: 'forward' | 'backward' | 'jump';
  if (newPhaseIndex === oldPhaseIndex + 1) {
    direction = 'forward';
  } else if (newPhaseIndex === oldPhaseIndex - 1) {
    direction = 'backward';
  } else {
    direction = 'jump';
  }

  const payload = {
    event: 'phase_change',
    timestamp: new Date().toISOString(),
    game_id: gameState.gameId || 0,
    phase_index: newPhaseIndex,
    phase_name: currentPhase.name,
    phase_year: currentPhase.year || parseInt(currentPhase.name.substring(1, 5)) || null,
    is_playing: gameState.isPlaying,
    direction: direction,
    total_phases: gameState.gameData.phases.length
  };

  // Discord webhooks need a different format
  const isDiscordWebhook = config.webhookUrl.includes('discord.com/api/webhooks');
  const webhookPayload = isDiscordWebhook ? {
    content: `Phase Change: **${currentPhase.name}** (${direction})`,
    embeds: [{
      title: "AI Diplomacy Phase Update",
      color: direction === 'forward' ? 0x00ff00 : direction === 'backward' ? 0xff0000 : 0x0000ff,
      fields: [
        { name: "Phase", value: currentPhase.name, inline: true },
        { name: "Year", value: String(payload.phase_year || "Unknown"), inline: true },
        { name: "Direction", value: direction, inline: true },
        { name: "Game ID", value: String(payload.game_id), inline: true },
        { name: "Phase Index", value: `${newPhaseIndex}/${payload.total_phases}`, inline: true },
        { name: "Auto-playing", value: payload.is_playing ? "Yes" : "No", inline: true }
      ],
      timestamp: payload.timestamp
    }]
  } : payload;

  console.log(`[Webhook] Sending notification for phase ${currentPhase.name} to ${config.webhookUrl}`);
  
  try {
    // Fire and forget - we don't await this
    fetch(config.webhookUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(webhookPayload)
    })
    .then(response => {
      if (response.ok) {
        console.log(`[Webhook] ✅ Successfully sent notification for phase ${currentPhase.name}`);
      } else {
        console.warn(`[Webhook] ❌ Failed with status ${response.status}: ${response.statusText}`);
      }
    })
    .catch(error => {
      // Log errors but don't let them break the animation
      console.error('[Webhook] ❌ Network error:', error);
    });
    
    if (config.isDebugMode) {
      console.log('[Webhook] Debug - Full payload:', payload);
    }
  } catch (error) {
    // Catch any synchronous errors (shouldn't happen with fetch)
    console.error('[Webhook] ❌ Unexpected error:', error);
  }
}