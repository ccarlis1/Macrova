import type { RunError, RunStatus } from "@tiny-fish/sdk";

export class TinyFishClientError extends Error {
  readonly runId?: string;
  readonly status?: RunStatus;
  readonly runError?: RunError | null;

  constructor(
    message: string,
    details?: {
      runId?: string;
      status?: RunStatus;
      error?: RunError | null;
    },
  ) {
    super(message);
    this.name = "TinyFishClientError";
    this.runId = details?.runId;
    this.status = details?.status;
    this.runError = details?.error;
  }
}
