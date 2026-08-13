/**
 * Shared action-state shapes + initial values for useActionState().
 *
 * Deliberately NOT in a "use server" file: files with a "use server"
 * directive may only export async functions, so plain constants/types like
 * these must live separately from the action functions that use them.
 */

export interface ImportActionState {
  status: "idle" | "success" | "error";
  message: string;
  rowErrors: { row: number; message: string }[];
  racesCreated?: number;
  runnersCreated?: number;
}

export const INITIAL_IMPORT_STATE: ImportActionState = {
  status: "idle",
  message: "",
  rowErrors: [],
};

export interface ResultActionState {
  status: "idle" | "success" | "error";
  message: string;
}

export const INITIAL_RESULT_STATE: ResultActionState = { status: "idle", message: "" };

export interface CreateRaceActionState {
  status: "idle" | "error";
  message: string;
}

export const INITIAL_CREATE_RACE_STATE: CreateRaceActionState = { status: "idle", message: "" };

export interface Lucky15ActionState {
  status: "idle" | "success" | "error";
  message: string;
}

export const INITIAL_LUCKY15_STATE: Lucky15ActionState = { status: "idle", message: "" };
