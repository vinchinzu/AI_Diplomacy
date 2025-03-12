import { z } from 'zod';
import { PowerENUM } from './map';

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
const OrderFromString = z.union([
  OrderSchema,
  z.string().transform((val) => {
    // val should be like "F BUD D"
    const parts = val.split(" ");
    return {
      text: val,
      power: parts[0],
      region: parts[1]
    }
  })
])
const PhaseSchema = z.object({
  messages: z.array(z.any()),
  name: z.string(),
  orders: z.array(OrderSchema),
  results: z.record(z.nativeEnum(PowerENUM), OrderSchema),
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
