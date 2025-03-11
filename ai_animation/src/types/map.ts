import { z } from "zod";

export enum ProvTypeENUM {
  WATER = "Water",
  COAST = "Coast",
  LAND = "Land",
}

export enum PowerENUM {
  FRANCE = "France",
  TURKEY = "Turkey",
  AUSTRIA = "Austria",
  GERMANY = "Germany",
  ITALY = "Italy",
  RUSSIA = "Russia",
}

export const ProvTypeSchema = z.nativeEnum(ProvTypeENUM);
export const PowerSchema = z.nativeEnum(PowerENUM);

export const LabelSchema = z.object({
  x: z.number(),
  y: z.number(),
});

export const UnitSchema = z.object({
  x: z.number(),
  y: z.number(),
});

export const ProvinceSchema = z.object({
  label: LabelSchema,
  type: ProvTypeSchema,
  unit: UnitSchema.optional(),
  owner: PowerSchema.optional(),
});

export const CoordinateDataSchema = z.object({
  provinces: z.array(ProvinceSchema),
});

export type Province = z.infer<typeof ProvinceSchema>;
export type CoordinateData = z.infer<typeof CoordinateDataSchema>;

