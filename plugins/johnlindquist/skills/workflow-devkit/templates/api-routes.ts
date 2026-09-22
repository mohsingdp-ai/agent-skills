/**
 * API Route Templates for Workflow DevKit
 *
 * Copy these patterns into your Next.js/Hono/etc routes.
 */

// ============================================================
// 1. START WORKFLOW (Fire-and-Forget)
// ============================================================

import { start } from "workflow/api";
import { basicWorkflow } from "@/workflows/basic-workflow";

export async function POST_start(request: Request) {
  const { input } = await request.json();

  const run = await start(basicWorkflow, [input]);

  return Response.json({
    runId: run.runId,
    message: "Workflow started",
  });
}

// ============================================================
// 2. START WORKFLOW (Wait for Result)
// ============================================================

import { FatalError } from "workflow";

export async function POST_blocking(request: Request) {
  try {
    const { input } = await request.json();
    const run = await start(basicWorkflow, [input]);

    // Blocks until workflow completes
    const result = await run.returnValue;

    return Response.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    const isFatal = error instanceof FatalError;

    return Response.json(
      { error: message, fatal: isFatal },
      { status: isFatal ? 400 : 500 }
    );
  }
}

// ============================================================
// 3. STREAMING (AI Chat)
// ============================================================

import { createUIMessageStreamResponse, type UIMessage } from "ai";
import { aiAgentWorkflow } from "@/workflows/ai-agent-workflow";

export async function POST_stream(request: Request) {
  const { messages }: { messages: UIMessage[] } = await request.json();

  const run = await start(aiAgentWorkflow, [messages]);

  return createUIMessageStreamResponse({
    stream: run.readable,
    headers: {
      "x-workflow-run-id": run.runId,
    },
  });
}

// ============================================================
// 4. RECONNECT TO STREAM
// ============================================================

import { getRun } from "workflow/api";

export async function GET_reconnect(request: Request) {
  const { searchParams } = new URL(request.url);
  const runId = searchParams.get("runId");
  const startIndex = parseInt(searchParams.get("startIndex") ?? "0");

  if (!runId) {
    return Response.json({ error: "runId required" }, { status: 400 });
  }

  const run = getRun(runId);
  const stream = run.getReadable({ startIndex });

  return createUIMessageStreamResponse({ stream });
}

// ============================================================
// 5. ACTOR - START
// ============================================================

import { actorWorkflow } from "@/workflows/actor-workflow";

export async function POST_actor_start(request: Request) {
  const body = await request.json();
  const initialState = body.initialState;

  const run = await start(actorWorkflow, [initialState]);

  // Don't await returnValue - actors run indefinitely
  return Response.json({
    actorId: run.runId,
    message: "Actor started",
  });
}

// ============================================================
// 6. ACTOR - SEND EVENT
// ============================================================

import { actorHook, type ActorEvent } from "@/workflows/actor-workflow";

export async function POST_actor_event(
  request: Request,
  actorId: string
) {
  const event: ActorEvent = await request.json();

  const result = await actorHook.resume(`actor:${actorId}`, event);

  if (result) {
    return Response.json({ success: true, runId: result.runId });
  }

  return Response.json(
    { error: "Actor not found" },
    { status: 404 }
  );
}

// ============================================================
// 7. ACTOR - GET STATE
// ============================================================

import { getActorState } from "@/workflows/actor-workflow";

export async function GET_actor_state(actorId: string) {
  const state = getActorState(actorId);

  if (!state) {
    return Response.json(
      { error: "Actor not found" },
      { status: 404 }
    );
  }

  return Response.json({ actorId, state });
}
