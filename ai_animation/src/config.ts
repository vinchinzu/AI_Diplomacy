/**
 * Global configuration settings for the application
 */
export const config = {
  // Default speed in milliseconds for animations and transitions
  playbackSpeed: 500,

  // Whether to enable debug mode (faster animations, more console logging)
  isDebugMode: import.meta.env.VITE_DEBUG_MODE || false,

  // Duration of unit movement animation in ms
  animationDuration: 1500,

  // How frequently to play sound effects (1 = every message, 3 = every third message)
  soundEffectFrequency: 3,

  // Whether speech/TTS is enabled (can be toggled via debug menu)
  speechEnabled: import.meta.env.VITE_DEBUG_MODE ? false : true,

  // Webhook URL for phase change notifications (optional)
  webhookUrl: import.meta.env.VITE_WEBHOOK_URL || ''
}
