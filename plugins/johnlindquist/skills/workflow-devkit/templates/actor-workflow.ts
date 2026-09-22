/**
 * Actor Workflow Template
 *
 * A long-running workflow that processes events sequentially.
 * Perfect for chat sessions, game loops, or stateful agents.
 */

import { defineHook, getWorkflowMetadata } from "workflow";

// Define the actor's state
export interface ActorState {
  count: number;
  lastUpdated: string;
  history: Array<{ action: string; timestamp: string }>;
}

// Define events the actor can receive
export type ActorEvent =
  | { type: "increment"; amount?: number }
  | { type: "decrement"; amount?: number }
  | { type: "reset" }
  | { type: "shutdown" };

// Export hook for use in API routes
export const actorHook = defineHook<ActorEvent>();

// In-memory state store (use Redis/database in production)
const stateStore = new Map<string, ActorState>();

// Main actor workflow
export async function actorWorkflow(initialState?: ActorState) {
  "use workflow";

  const { workflowRunId } = getWorkflowMetadata();
  const actorId = workflowRunId;

  // Initialize state
  let state: ActorState = initialState ?? {
    count: 0,
    lastUpdated: new Date().toISOString(),
    history: [],
  };
  stateStore.set(actorId, state);

  // Create event receiver
  const receive = actorHook.create({
    token: `actor:${actorId}`,
  });

  console.log(`Actor ${actorId} started`);

  // Event loop - processes events sequentially forever
  for await (const event of receive) {
    console.log(`Actor ${actorId} received:`, event);

    if (event.type === "shutdown") {
      console.log(`Actor ${actorId} shutting down`);
      break;
    }

    // Process event and update state
    state = await processEvent(state, event);
    stateStore.set(actorId, state);

    console.log(`Actor ${actorId} state:`, state);
  }

  return { actorId, finalState: state };
}

// Step function for processing events
async function processEvent(state: ActorState, event: ActorEvent): Promise<ActorState> {
  "use step";

  const timestamp = new Date().toISOString();
  let newCount = state.count;
  let action = "";

  switch (event.type) {
    case "increment":
      newCount += event.amount ?? 1;
      action = `increment by ${event.amount ?? 1}`;
      break;
    case "decrement":
      newCount -= event.amount ?? 1;
      action = `decrement by ${event.amount ?? 1}`;
      break;
    case "reset":
      newCount = 0;
      action = "reset";
      break;
  }

  return {
    count: newCount,
    lastUpdated: timestamp,
    history: [...state.history, { action, timestamp }].slice(-10),
  };
}

// Helper to get actor state (for API routes)
export function getActorState(actorId: string): ActorState | undefined {
  return stateStore.get(actorId);
}
