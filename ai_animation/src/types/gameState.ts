import { z } from 'zod';
import { PowerENUM, PowerSchema } from './map';
import { OrderFromString } from './unitOrders';

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
  messages: z.array(z.any()),
  name: z.string(),
  orders: z.record(PowerSchema, z.array(OrderFromString)),
  results: z.record(PowerSchema, OrderSchema),
  state: z.object({
    units: z.record(z.nativeEnum(PowerENUM), z.array(z.string()))
  }),
  year: z.number(),
  units: z.array(UnitSchema),
});

export const GameSchema = z.object({
  map_name: z.string(),
  game_id: z.string(),
  phases: z.array(PhaseSchema),
});

export type GamePhase = z.infer<typeof PhaseSchema>;
