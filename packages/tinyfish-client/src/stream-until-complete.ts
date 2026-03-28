import {
  EventType,
  RunStatus,
  type AgentRunParams,
  type StreamOptions,
  type TinyFish,
} from "@tiny-fish/sdk";

import { TinyFishClientError } from "./errors.js";

/**
 * Runs `/run-sse` via the SDK stream API and returns the structured `result` object.
 * All automation + navigation stays inside TinyFish; callers only pass goals and URLs.
 */
export async function streamUntilComplete(
  client: TinyFish,
  params: AgentRunParams,
  streamOptions?: StreamOptions,
): Promise<Record<string, unknown>> {
  const stream = await client.agent.stream(params, streamOptions);
  try {
    for await (const event of stream) {
      if (event.type !== EventType.COMPLETE) {
        continue;
      }
      if (event.status === RunStatus.COMPLETED) {
        if (event.result === null) {
          throw new TinyFishClientError(
            "TinyFish completed without a structured result",
            { runId: event.run_id, status: event.status },
          );
        }
        return event.result;
      }
      const msg = event.error?.message ?? "TinyFish run failed";
      throw new TinyFishClientError(msg, {
        runId: event.run_id,
        status: event.status,
        error: event.error,
      });
    }
  } finally {
    await stream.close();
  }
  throw new TinyFishClientError("SSE stream ended before COMPLETE event");
}
