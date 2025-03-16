import { z } from 'zod';
import { PowerENUMSchema } from './map';
import { OrderFromString } from './unitOrders';
import { ProvinceENUMSchema } from './map';

// Define the unit structure in the JSON
const UnitSchema = z.object({
  type: z.string(),
  power: PowerENUMSchema,
  location: z.string(),
  // Add any other possible fields with optional()
  region: z.string().optional(),
  coast: z.string().optional(),
  // Catch-all for any other fields
}).catchall(z.any());

// Define the order structure in the JSON
const OrderSchema = z.object({
  text: z.string(),
  power: PowerENUMSchema,
  region: z.string().optional(),
  // Add any other possible fields with optional()
  result: z.any().optional(),
  unit: z.any().optional(),
  type: z.string().optional(),
  // Catch-all for any other fields
}).catchall(z.any());

const PhaseSchema = z.object({
  name: z.string(),
  year: z.number().optional(),
  season: z.string().optional(),
  type: z.string().optional(),
  // Make messages optional with default empty array
  messages: z.array(z.object({
    sender: PowerENUMSchema,
    recipient: z.union([PowerENUMSchema, z.literal('GLOBAL')]),
    time_sent: z.number(),
    message: z.string()
  })).optional().default([]),
  // Units as an array of objects
  units: z.array(UnitSchema).optional(),
  // Orders - standardize on array format, with preprocessor to convert from object format
  orders: z.preprocess(
    (val) => {
      // If it's already an array, return it
      if (Array.isArray(val)) {
        return val;
      }
      
      // If it's an object with power keys and arrays of order strings
      if (val && typeof val === 'object') {
        const orderArray: any[] = [];
        
        // Convert from {POWER: [orderText1, orderText2]} to [{text: orderText1, power: POWER}, {text: orderText2, power: POWER}]
        Object.entries(val).forEach(([power, orders]) => {
          if (Array.isArray(orders)) {
            orders.forEach(orderText => {
              // Extract region from order text if possible
              let region = '';
              const match = orderText.match(/^[AF]\s+([A-Z]{3})/);
              if (match) {
                region = match[1];
              }
              
              orderArray.push({
                text: orderText,
                power: power,
                region: region
              });
            });
          }
        });
        
        return orderArray;
      }
      
      // Otherwise return empty array
      return [];
    },
    z.array(OrderSchema).optional().default([])
  ),
  // Results as an optional record
  results: z.record(z.string(), z.array(z.any())).optional().default({}),
  // State as an optional object
  state: z.object({
    units: z.record(PowerENUMSchema, z.array(z.string())).optional(),
    centers: z.record(PowerENUMSchema, z.array(ProvinceENUMSchema)).optional()
  }).optional().default({}),
  // Summary for phase completion
  summary: z.string().optional()
});

export const GameSchema = z.object({
  map_name: z.string().optional(),
  map: z.string().optional(),
  id: z.string().optional(),
  game_id: z.string().optional(),
  phases: z.array(PhaseSchema),
  // Add other possible fields
  powers: z.any().optional(),
  current_phase: z.any().optional(),
  status: z.any().optional(),
  created_at: z.any().optional(),
  updated_at: z.any().optional(),
}).catchall(z.any());

export type GamePhase = z.infer<typeof PhaseSchema>;
export type GameSchemaType = z.infer<typeof GameSchema>;
