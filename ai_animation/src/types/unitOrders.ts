import { z } from "zod";

export function cleanProvince(province: string): string {
  if (!province) return province;
  return province.split('/')[0];
};
export const OrderFromString = z.string().transform((orderStr) => {
  // Helper function to clean province names by removing coast specifications

  // Split the order into tokens by whitespace.
  const tokens = orderStr.trim().split(/\s+/);
  // The first token is the unit type (A or F)
  const unitType = tokens[0];
  // The second token is the origin province.
  const origin = cleanProvince(tokens[1]);

  // Check if this order is a support order.
  if (tokens.includes("S")) {
    const indexS = tokens.indexOf("S");
    // The tokens immediately after "S" define the supported unit.
    const supportedUnitType = tokens[indexS + 1];
    const supportedOrigin = cleanProvince(tokens[indexS + 2]);
    let supportedDestination = null;
    // If there is a hyphen following, then a destination is specified.
    if (tokens.length > indexS + 3 && tokens[indexS + 3] === "-") {
      supportedDestination = cleanProvince(tokens[indexS + 4]);
    }
    return {
      type: "support",
      unit: { type: unitType, origin },
      support: {
        unit: { type: supportedUnitType, origin: supportedOrigin },
        // If no destination is given, this means the supported unit is holding.
        destination: supportedDestination,
      },
      raw: orderStr,
    };
  }
  // Check if the order is a hold order.
  else if (tokens.includes("H")) {
    return {
      type: "hold",
      unit: { type: unitType, origin },
      raw: orderStr,
    };
  }
  // Check if order is a disband
  else if (tokens.includes("D")) {
    return {
      type: "disband",
      unit: { type: unitType, origin },
      raw: orderStr
    }
  }
  // Check if order is Bounce
  else if (tokens.includes("B")) {
    return {
      type: "build",
      unit: { type: unitType, origin },
      raw: orderStr
    }
  }
  else if (tokens.includes("R")) {
    return {
      type: "retreat",
      unit: { type: unitType, origin },
      destination: cleanProvince(tokens.at(-1) || ''),
      raw: orderStr
    }
  }
  else if (tokens.includes("C")) {
    // F NTH C A YOR - NWY
    return {
      type: "convoy",
      unit: { type: unitType, origin: cleanProvince(tokens.at(1) || '') },
      destination: cleanProvince(tokens.at(-1) || ''),
      raw: orderStr
    }
  }
  // Otherwise, assume it's a move order if a hyphen ("-") is present.
  else if (tokens.includes("-")) {
    const dashIndex = tokens.indexOf("-");
    // The token immediately after "-" is the destination.
    const destination = cleanProvince(tokens[dashIndex + 1]);
    return {
      type: "move",
      unit: { type: unitType, origin },
      destination,
      raw: orderStr,
    };
  }
  // If none of the expected tokens are found, throw an error.
  else {
    throw new Error(`Order format not recognized: ${orderStr}`);
  }
});
export type UnitOrder = z.infer<typeof OrderFromString>
