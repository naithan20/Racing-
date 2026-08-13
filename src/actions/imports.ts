"use server";

import { revalidatePath } from "next/cache";

import { ImportSourceType } from "@/generated/prisma/enums";
import { parseCsvToRecords } from "@/lib/csv";
import {
  CSV_IMPORT_TEMPLATE_HEADER,
  groupImportRowsByRace,
  JsonImportDocumentSchema,
  validateCsvRecords,
} from "@/data/importSchema";
import { importRaces } from "@/data/importRaces";
import type { ImportActionState } from "@/actions/state";

export async function importCsvAction(
  _prevState: ImportActionState,
  formData: FormData
): Promise<ImportActionState> {
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return { status: "error", message: "Choose a CSV file to import.", rowErrors: [] };
  }

  const text = await file.text();
  const records = parseCsvToRecords(text);
  if (records.length === 0) {
    return { status: "error", message: "CSV file has no data rows.", rowErrors: [] };
  }

  const { validRows, errors } = validateCsvRecords(records);
  if (validRows.length === 0) {
    return {
      status: "error",
      message: `No valid rows found (${errors.length} row error(s)).`,
      rowErrors: errors,
    };
  }

  const races = groupImportRowsByRace(validRows);
  const result = await importRaces(races, { sourceType: ImportSourceType.CSV, filename: file.name });

  revalidatePath("/races");
  revalidatePath("/import");

  return {
    status: errors.length > 0 ? "success" : "success",
    message: `Imported ${result.racesCreated} race(s), ${result.runnersCreated} runner(s).${
      errors.length > 0 ? ` ${errors.length} row(s) skipped due to validation errors.` : ""
    }`,
    rowErrors: errors,
    racesCreated: result.racesCreated,
    runnersCreated: result.runnersCreated,
  };
}

export async function importJsonAction(
  _prevState: ImportActionState,
  formData: FormData
): Promise<ImportActionState> {
  const file = formData.get("file");
  const rawText = formData.get("jsonText");

  const text = file instanceof File && file.size > 0 ? await file.text() : typeof rawText === "string" ? rawText : "";

  if (!text.trim()) {
    return { status: "error", message: "Provide a JSON file or paste JSON content.", rowErrors: [] };
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { status: "error", message: "Could not parse JSON — check the file is valid JSON.", rowErrors: [] };
  }

  const validation = JsonImportDocumentSchema.safeParse(parsed);
  if (!validation.success) {
    const rowErrors = validation.error.issues.map((issue, index) => ({
      row: index + 1,
      message: `${issue.path.join(".")}: ${issue.message}`,
    }));
    return { status: "error", message: "JSON document failed validation.", rowErrors };
  }

  const result = await importRaces(validation.data.races, {
    sourceType: ImportSourceType.JSON,
    filename: file instanceof File ? file.name : "pasted-json",
  });

  revalidatePath("/races");
  revalidatePath("/import");

  return {
    status: "success",
    message: `Imported ${result.racesCreated} race(s), ${result.runnersCreated} runner(s).`,
    rowErrors: [],
    racesCreated: result.racesCreated,
    runnersCreated: result.runnersCreated,
  };
}

export async function getCsvTemplate(): Promise<string> {
  return CSV_IMPORT_TEMPLATE_HEADER;
}
