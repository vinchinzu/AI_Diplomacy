import { z } from 'zod';
import { PowerENUMSchema } from './map';

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

// Type exports
export type MomentCategory = z.infer<typeof MomentCategorySchema>;
export type MomentsMetadata = z.infer<typeof MomentsMetadataSchema>;
export type DiaryContext = z.infer<typeof DiaryContextSchema>;
export type Moment = z.infer<typeof MomentSchema>;
export type MomentsDataSchemaType = z.infer<typeof MomentsDataSchema>;
