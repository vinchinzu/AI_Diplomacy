/**
 * Global configuration settings for the application
 */
export const config = {
  // Default speed in milliseconds for animations and transitions
  playbackSpeed: 500,

  // Whether to enable debug mode (faster animations, more console logging)
  isDebugMode: import.meta.env.VITE_DEBUG_MODE === 'true' || import.meta.env.VITE_DEBUG_MODE === 'True',

  // Duration of unit movement animation in ms
  animationDuration: 1500,

  // How frequently to play sound effects (1 = every message, 3 = every third message)
  soundEffectFrequency: 3,

  // Whether speech/TTS is enabled (can be toggled via debug menu)
  get speechEnabled(): boolean {
    return !(import.meta.env.VITE_DEBUG_MODE === 'true' || import.meta.env.VITE_DEBUG_MODE === 'True');
  },

  // Webhook URL for phase change notifications (optional)
  webhookUrl: import.meta.env.VITE_WEBHOOK_URL || '',
  get isTestingMode(): boolean {
    // have playwrite inject a marker saying that it's testing to brower
    return import.meta.env.VITE_TESTING_MODE === 'True' || import.meta.env.VITE_TESTING_MODE === 'true' || window.isUnderTest;
  },
  _isTestingMode: false,

  // Whether instant mode is enabled (makes all animations instant)
  // Can be enabled via VITE_INSTANT_MODE env variable or debug menu
  get isInstantMode(): boolean {
    if (this._instantModeOverride !== null) {
      return this._instantModeOverride
    }
    return import.meta.env.VITE_INSTANT_MODE === 'True' || import.meta.env.VITE_INSTANT_MODE === 'true'
  },

  // Internal flag to allow runtime toggling of instant mode
  _instantModeOverride: null,

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
  },

  // Animation timing configuration
  animation: {
    // Unit movement wave frequencies (Hz)
    unitBobFrequency: 0.8,
    fleetRollFrequency: 0.5,
    fleetPitchFrequency: 0.3,
    
    // Supply center pulse frequency (Hz)
    supplyPulseFrequency: 1.0,
    
    // Province highlight flash frequency (Hz)
    provinceFlashFrequency: 2.0,
    
    // Maximum frame delta time (seconds) to prevent animation jumps
    maxDeltaTime: 0.1
  }
}
