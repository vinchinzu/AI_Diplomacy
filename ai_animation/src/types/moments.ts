import { z } from 'zod';
import { PowerENUMSchema } from './map';

/**
 * Schema for parsing Diplomacy phase names (e.g., "W1901R")
 */
export const PhaseNameSchema = z.string().regex(/^[SFW]\d{4}[MRA]$/, "Phase name must match format [Season][Year][Phase]");

/**
 * Schema for parsed phase components
 */
export const ParsedPhaseSchema = z.object({
  season: z.enum(['S', 'F', 'W']),
  year: z.number().int().min(1901),
  phase: z.enum(['M', 'R', 'A']),
  order: z.number().int()
});

/**
 * Schema for moment categories used in analysis
 */
export const MomentCategorySchema = z.enum([
  'BETRAYAL',
  'PROMISE_ADJUSTMENT',
  'COLLABORATION',
  'PLAYING_BOTH_SIDES',
  'BRILLIANT_STRATEGY',
  'STRATEGIC_BLUNDER',
  'STRATEGIC_BURST (UNFORESEEN_OUTCOME)',
]);


/**
 * Schema for metadata about the moments analysis
 */
export const MomentsMetadataSchema = z.object({
  timestamp: z.string(),
  generated_at: z.string(),
  source_folder: z.string(),
  analysis_model: z.string(),
  total_moments: z.number(),
  moment_categories: z.object({
    betrayals: z.number(),
    collaborations: z.number(),
    playing_both_sides: z.number(),
    brilliant_strategies: z.number(),
    strategic_blunders: z.number()
  }),
  score_distribution: z.object({
    scores_9_10: z.number(),
    scores_7_8: z.number(),
    scores_4_6: z.number(),
    scores_1_3: z.number()
  })
});

/**
 * Schema for diary context entries for each power
 */
export const DiaryContextSchema = z.record(PowerENUMSchema, z.string());

/**
 * Schema for an individual moment in the game
 */
export const MomentSchema = z.object({
  phase: z.string(),
  category: MomentCategorySchema,
  powers_involved: z.array(PowerENUMSchema),
  promise_agreement: z.string(),
  actual_action: z.string(),
  impact: z.string(),
  interest_score: z.number().min(0).max(10),
  diary_context: DiaryContextSchema
});

/**
 * Schema for the complete moments.json file
 */
export const MomentsDataSchema = z.object({
  metadata: MomentsMetadataSchema,
  power_models: z.record(PowerENUMSchema, z.string()),
  moments: z.array(MomentSchema)
});

/**
 * Parses a phase name like "W1901R" into its components
 */
export function parsePhase(phaseName: string): z.infer<typeof ParsedPhaseSchema> | null {
  const parseResult = PhaseNameSchema.safeParse(phaseName);
  if (!parseResult.success) {
    return null;
  }

  const match = phaseName.match(/^([SFW])(\d{4})([MRA])$/);
  if (!match) return null;

  const [, season, yearStr, phase] = match;
  const year = parseInt(yearStr, 10);

  const order = calculatePhaseOrder(season as 'S' | 'F' | 'W', year, phase as 'M' | 'R' | 'A');

  return ParsedPhaseSchema.parse({
    season: season as 'S' | 'F' | 'W',
    year,
    phase: phase as 'M' | 'R' | 'A',
    order
  });
}

/**
 * Calculates chronological order number for a phase
 */
function calculatePhaseOrder(season: 'S' | 'F' | 'W', year: number, phase: 'M' | 'R' | 'A'): number {
  const yearMultiplier = (year - 1901) * 9;
  
  let seasonOffset = 0;
  switch (season) {
    case 'S': seasonOffset = 0; break;
    case 'F': seasonOffset = 3; break;
    case 'W': seasonOffset = 6; break;
  }
  
  let phaseOffset = 0;
  switch (phase) {
    case 'M': phaseOffset = 0; break;
    case 'R': phaseOffset = 1; break;
    case 'A': phaseOffset = 2; break;
  }
  
  return yearMultiplier + seasonOffset + phaseOffset;
}

/**
 * Generates the next phase name in chronological order
 */
export function getNextPhaseName(currentPhaseName: string): string | null {
  const parsed = parsePhase(currentPhaseName);
  if (!parsed) return null;

  let { season, year, phase } = parsed;

  switch (phase) {
    case 'M': phase = 'R'; break;
    case 'R': phase = 'A'; break;
    case 'A':
      switch (season) {
        case 'S': season = 'F'; phase = 'M'; break;
        case 'F': season = 'W'; phase = 'M'; break;
        case 'W': season = 'S'; phase = 'M'; year++; break;
      }
      break;
  }

  return `${season}${year}${phase}`;
}

// Type exports
export type ParsedPhase = z.infer<typeof ParsedPhaseSchema>;
export type MomentCategory = z.infer<typeof MomentCategorySchema>;
export type MomentsMetadata = z.infer<typeof MomentsMetadataSchema>;
export type DiaryContext = z.infer<typeof DiaryContextSchema>;
export type Moment = z.infer<typeof MomentSchema>;
export type MomentsDataSchemaType = z.infer<typeof MomentsDataSchema>;
