import { z } from 'zod';

const UnitSchema = z.object({
  type: z.enum(["A", "F"]),
  power: z.string(),
  location: z.string(),
});

const OrderSchema = z.object({
  text: z.string(),
  power: z.string(),
  region: z.string(),
});

const PhaseSchema = z.object({
  name: z.string(),
  year: z.number(),
  season: z.enum(["SPRING", "FALL", "WINTER"]),
  type: z.enum(["MOVEMENT", "ADJUSTMENT"]),
  units: z.array(UnitSchema),
  orders: z.array(OrderSchema),
});

export const GameSchema = z.object({
  map_name: z.string(),
  game_id: z.string(),
  phases: z.array(PhaseSchema),
});
