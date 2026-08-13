/**
 * Feature store validation helpers.
 *
 * A Feature row stores exactly one of numericValue / textValue / booleanValue,
 * matching the valueType declared on its FeatureDefinition. This module
 * enforces that at write time so the store stays self-consistent no matter
 * what eventually writes to it (manual entry, CSV import, or the future
 * model).
 */

import { FeatureValueType } from "@/generated/prisma/enums";
import { findFeatureDefinition } from "@/features/definitions";

export class UnknownFeatureKeyError extends Error {}
export class FeatureValueTypeMismatchError extends Error {}

export type FeatureValueInput =
  | { type: "NUMERIC"; value: number }
  | { type: "TEXT"; value: string }
  | { type: "BOOLEAN"; value: boolean }
  | { type: "CATEGORY"; value: string };

export interface FeatureRowData {
  key: string;
  numericValue: number | null;
  textValue: string | null;
  booleanValue: boolean | null;
}

/**
 * Validates a feature value against its FeatureDefinition and returns the
 * row shape ready to persist. Throws if the key is unknown or the value
 * type doesn't match the definition.
 */
export function buildFeatureRow(key: string, input: FeatureValueInput): FeatureRowData {
  const definition = findFeatureDefinition(key);
  if (!definition) {
    throw new UnknownFeatureKeyError(
      `"${key}" is not a registered FeatureDefinition. Add it to src/features/definitions.ts before storing values for it.`
    );
  }

  if (definition.valueType !== input.type) {
    throw new FeatureValueTypeMismatchError(
      `Feature "${key}" expects a ${definition.valueType} value, got ${input.type}`
    );
  }

  switch (input.type) {
    case "NUMERIC":
      return { key, numericValue: input.value, textValue: null, booleanValue: null };
    case "BOOLEAN":
      return { key, numericValue: null, textValue: null, booleanValue: input.value };
    case "TEXT":
    case "CATEGORY":
      return { key, numericValue: null, textValue: input.value, booleanValue: null };
    default: {
      const exhaustive: never = input;
      throw new FeatureValueTypeMismatchError(`Unhandled feature value type: ${JSON.stringify(exhaustive)}`);
    }
  }
}

/** Reads back a stored Feature row as a plain JS value matching its declared type. */
export function readFeatureValue(row: FeatureRowData): number | string | boolean | null {
  if (row.numericValue !== null) return row.numericValue;
  if (row.booleanValue !== null) return row.booleanValue;
  if (row.textValue !== null) return row.textValue;
  return null;
}

export { FeatureValueType };
