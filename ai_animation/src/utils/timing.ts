/**
 * Timing utilities for consistent animation across different frame rates
 */

/**
 * Creates a time-based animation value that oscillates between 0 and 1
 * @param frequency - Oscillations per second
 * @param elapsedTime - Time elapsed in seconds
 * @returns Value between 0 and 1
 */
export function oscillate(frequency: number, elapsedTime: number): number {
  return (Math.sin(elapsedTime * frequency * Math.PI * 2) + 1) / 2;
}

/**
 * Creates a time-based sine wave value
 * @param frequency - Oscillations per second
 * @param elapsedTime - Time elapsed in seconds
 * @param amplitude - Maximum displacement from center
 * @param offset - Center position
 * @returns Sine wave value
 */
export function sineWave(
  frequency: number, 
  elapsedTime: number, 
  amplitude: number = 1, 
  offset: number = 0
): number {
  return Math.sin(elapsedTime * frequency * Math.PI * 2) * amplitude + offset;
}

/**
 * Converts milliseconds to seconds
 * @param ms - Time in milliseconds
 * @returns Time in seconds
 */
export function msToSeconds(ms: number): number {
  return ms / 1000;
}

/**
 * Gets current high-resolution time in seconds
 * @returns Current time in seconds
 */
export function getTimeInSeconds(): number {
  return performance.now() / 1000;
}

/**
 * Clamps a value between min and max
 * @param value - Value to clamp
 * @param min - Minimum value
 * @param max - Maximum value
 * @returns Clamped value
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

/**
 * Linear interpolation between two values based on time
 * @param start - Start value
 * @param end - End value
 * @param progress - Progress from 0 to 1
 * @returns Interpolated value
 */
export function lerp(start: number, end: number, progress: number): number {
  return start + (end - start) * clamp(progress, 0, 1);
}