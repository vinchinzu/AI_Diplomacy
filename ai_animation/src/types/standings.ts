/**
 * Types for the Standings Board feature
 */

export interface StandingsEntry {
  model: string;
  wins: Record<string, number>;
  totalWins: number;
}

export interface StandingsData {
  models: string[];
  powers: string[];
  entries: StandingsEntry[];
}

export enum SortBy {
  MODEL = 'model',
  TOTAL_WINS = 'totalWins',
  POWER = 'power' // Will be combined with power name, e.g., 'power_England'
}

export enum SortDirection {
  ASC = 'asc',
  DESC = 'desc'
}

export interface SortOptions {
  by: SortBy | string;
  direction: SortDirection;
} 