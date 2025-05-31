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
 * Schema for metadata about the moments analysis (comprehensive format)
 */
export const ComprehensiveMetadataSchema = z.object({
  game_results_folder: z.string(),
  analysis_timestamp: z.string(),
  model_used: z.string(),
  game_data_path: z.string(),
  power_to_model: z.record(PowerENUMSchema, z.string())
});

/**
 * Schema for metadata about the moments analysis (animation format)
 */
export const AnimationMetadataSchema = z.object({
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
 * Union schema for metadata that can handle both formats
 */
export const MomentsMetadataSchema = z.union([
  AnimationMetadataSchema,
  ComprehensiveMetadataSchema
]);

/**
 * Schema for diary context entries for each power
 */
export const DiaryContextSchema = z.record(PowerENUMSchema, z.string());

/**
 * Schema for state update context entries for each power
 */
export const StateUpdateContextSchema = z.record(PowerENUMSchema, z.string());

/**
 * Schema for a lie detected in the game
 */
export const LieSchema = z.object({
  phase: z.string(),
  liar: PowerENUMSchema,
  recipient: PowerENUMSchema,
  promise: z.string(),
  diary_intent: z.string(),
  actual_action: z.string(),
  intentional: z.boolean(),
  explanation: z.string()
});

/**
 * Schema for an individual moment in the game (animation format)
 */
export const AnimationMomentSchema = z.object({
  phase: z.string(),
  category: MomentCategorySchema,
  powers_involved: z.array(PowerENUMSchema),
  promise_agreement: z.string(),
  actual_action: z.string(),
  impact: z.string(),
  interest_score: z.number().min(0).max(10),
  diary_context: DiaryContextSchema,
  state_update_context: StateUpdateContextSchema
});

/**
 * Schema for an individual moment in the game (comprehensive format)
 */
export const ComprehensiveMomentSchema = z.object({
  phase: z.string(),
  category: MomentCategorySchema,
  powers_involved: z.array(PowerENUMSchema),
  promise_agreement: z.string(),
  actual_action: z.string(),
  impact: z.string(),
  interest_score: z.number().min(0).max(10),
  raw_messages: z.array(z.any()),
  raw_orders: z.record(z.any()),
  diary_context: z.record(z.string()),
  state_update_context: z.record(z.string()).optional()
});

/**
 * Union schema for moments that can handle both formats
 */
export const MomentSchema = z.union([
  AnimationMomentSchema,
  ComprehensiveMomentSchema
]);

/**
 * Schema for the animation format moments.json file
 */
export const AnimationMomentsDataSchema = z.object({
  metadata: AnimationMetadataSchema,
  power_models: z.record(PowerENUMSchema, z.string()),
  moments: z.array(MomentSchema)
});

/**
 * Schema for the comprehensive format game_moments_data.json file
 */
export const ComprehensiveMomentsDataSchema = z.object({
  metadata: ComprehensiveMetadataSchema,
  analysis_results: z.object({
    moments: z.array(ComprehensiveMomentSchema),
    lies: z.array(LieSchema),
    invalid_moves_by_model: z.record(z.string(), z.number())
  }),
  summary: z.object({
    total_moments: z.number(),
    total_lies: z.number(),
    moments_by_category: z.object({
      BETRAYAL: z.number(),
      COLLABORATION: z.number(),
      PLAYING_BOTH_SIDES: z.number(),
      BRILLIANT_STRATEGY: z.number(),
      STRATEGIC_BLUNDER: z.number()
    }),
    lies_by_power: z.record(z.number()),
    intentional_lies: z.number(),
    unintentional_lies: z.number(),
    score_distribution: z.object({
      "9-10": z.number(),
      "7-8": z.number(),
      "4-6": z.number(),
      "1-3": z.number()
    })
  }),
  phases_analyzed: z.array(z.string())
});

/**
 * Schema for the complete moments.json file (supports both formats)
 */
export const MomentsDataSchema = z.union([
  AnimationMomentsDataSchema,
  ComprehensiveMomentsDataSchema
]);

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
export type StateUpdateContext = z.infer<typeof StateUpdateContextSchema>;
export type Moment = z.infer<typeof MomentSchema>;
export type MomentsDataSchemaType = z.infer<typeof MomentsDataSchema>;

// Normalized format for internal use
export interface NormalizedMomentsData {
  metadata: z.infer<typeof AnimationMetadataSchema> | z.infer<typeof ComprehensiveMetadataSchema>;
  power_models: Record<PowerENUM, string>;
  moments: Moment[];
}
