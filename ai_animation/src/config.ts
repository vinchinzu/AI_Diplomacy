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
  webhookUrl: import.meta.env.VITE_WEBHOOK_URL || '',
  get isTestingMode(): boolean {
    // have playwrite inject a marker saying that it's testing to brower
    return import.meta.env.VITE_TESTING_MODE == 'True' || window.isUnderTest;
  },
  _isTestingMode: false,

  // Whether instant mode is enabled (makes all animations instant)
  // Can be enabled via VITE_INSTANT_MODE env variable or debug menu
  get isInstantMode(): boolean {
    return import.meta.env.VITE_INSTANT_MODE === 'True' || this._instantModeOverride;
  },

  // Internal flag to allow runtime toggling of instant mode
  _instantModeOverride: false,

  /**
   * Set instant mode state at runtime
   * @param enabled Whether to enable instant mode
   */
  setInstantMode(enabled: boolean): void {
    this._instantModeOverride = enabled;
    console.log(`Instant mode ${enabled ? 'enabled' : 'disabled'}`);
  },

  /**
   * Get effective animation duration (0 if instant mode, normal duration otherwise)
   */
  get effectiveAnimationDuration(): number {
    return this.isInstantMode ? 0 : this.animationDuration;
  },

  /**
   * Get effective playback speed (minimal if instant mode, normal speed otherwise)
   */
  get effectivePlaybackSpeed(): number {
    return this.isInstantMode ? 10 : this.playbackSpeed;
  }
}
