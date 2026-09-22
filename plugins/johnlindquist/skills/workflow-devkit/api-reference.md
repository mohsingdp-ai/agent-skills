# API Reference

## Starting Workflows

### Fire-and-Forget

```typescript
import { start } from "workflow/api";
import { myWorkflow } from "@/workflows/my-workflow";

export async function POST(request: Request) {
  const { input } = await request.json();
  const run = await start(myWorkflow, [input]);
  return Response.json({ runId: run.runId, message: "Started" });
}
```

### Wait for Result (Blocking)

```typescript
import { start } from "workflow/api";
import { FatalError } from "workflow";

export async function POST(request: Request) {
  try {
    const run = await start(myWorkflow, [input]);
    const result = await run.returnValue;  // Blocks until complete
    return Response.json(result);
  } catch (error) {
    const isFatal = error instanceof FatalError;
    return Response.json(
      { error: error.message, fatal: isFatal },
      { status: isFatal ? 400 : 500 }
    );
  }
}
```

## Streaming

### Initial Stream

```typescript
import { createUIMessageStreamResponse } from "ai";
import { start } from "workflow/api";

export async function POST(request: Request) {
  const run = await start(streamingWorkflow, [input]);

  return createUIMessageStreamResponse({
    stream: run.readable,
    headers: { "x-workflow-run-id": run.runId },
  });
}
```

### Reconnect to Existing Stream

```typescript
import { getRun } from "workflow/api";
import { createUIMessageStreamResponse } from "ai";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const runId = searchParams.get("runId")!;
  const startIndex = parseInt(searchParams.get("startIndex") ?? "0");

  const run = getRun(runId);
  const stream = run.getReadable({ startIndex });

  return createUIMessageStreamResponse({ stream });
}
```

### Binary Streaming (Files)

```typescript
import { Readable } from "node:stream";
import { start } from "workflow/api";

export async function POST(request: Request) {
  const run = await start(fileWorkflow, [input]);
  const webReadable = run.readable;

  const nodeReadable = Readable.fromWeb(webReadable);

  return new Response(nodeReadable, {
    headers: {
      "Content-Type": "audio/mp4",
      "Content-Disposition": 'attachment; filename="output.mp4"',
    },
  });
}
```

## Utility Functions

### sleep

```typescript
import { sleep } from "workflow";

await sleep("5s");              // Duration string
await sleep(5000);              // Milliseconds
await sleep(new Date(...));    // Until specific date
```

### Metadata

```typescript
import { getWorkflowMetadata, getStepMetadata } from "workflow";

// In workflow
const { workflowRunId } = getWorkflowMetadata();

// In step
const { attempt } = getStepMetadata();  // Current retry attempt (1, 2, 3...)
```

### Durable Fetch

```typescript
import { fetch } from "workflow";

// Override globalThis for AI SDK compatibility
globalThis.fetch = fetch;

// Or use directly
const response = await fetch("https://api.example.com/data");
```

## Hooks (Custom Tokens)

### createHook (One-Time)

```typescript
import { createHook } from "workflow";

export async function myWorkflow() {
  "use workflow";

  const hook = createHook<{ status: string }>({ token: `callback:${id}` });

  await triggerExternalService(hook.token);

  const payload = await hook;  // Waits for hook.resume()
  return payload.status;
}
```

### defineHook (Reusable, Multi-Event)

```typescript
import { defineHook } from "workflow";

export type MyEvent = { type: "start" } | { type: "stop" };
export const myHook = defineHook<MyEvent>();

export async function myActor() {
  "use workflow";

  const receive = myHook.create({ token: `actor:${id}` });

  for await (const event of receive) {
    // Process multiple events
  }
}
```

### Resume Hook (from API Route)

```typescript
import { myHook, type MyEvent } from "@/workflows/my-actor";

export async function POST(request: Request) {
  const event: MyEvent = await request.json();
  const result = await myHook.resume(`actor:${id}`, event);
  return Response.json({ success: !!result });
}
```

## State Management

### In-Memory Map

```typescript
// lib/store.ts
export const store = new Map<string, any>();

// workflow.ts
store.set(id, { status: "processing" });
const result = await processData();
store.set(id, { status: "complete", result });

// api/status/route.ts
return Response.json(store.get(id) ?? { status: "not_found" });
```

### PostgreSQL with Drizzle

```typescript
import { pgTable, text, jsonb, timestamp, vector, index } from "drizzle-orm/pg-core";

export const workflowRuns = pgTable("workflow_runs", {
  id: text("id").primaryKey(),
  status: text("status").notNull(),
  result: jsonb("result"),
  createdAt: timestamp("created_at").defaultNow(),
});

// With embeddings (RAG)
export const embeddings = pgTable("embeddings", {
  id: text("id").primaryKey(),
  content: text("content").notNull(),
  embedding: vector("embedding", { dimensions: 1536 }).notNull(),
}, (table) => ({
  idx: index("idx_embedding").using("hnsw", table.embedding.op("vector_cosine_ops")),
}));
```

## Error Types

| Type | Behavior | When to Use |
|------|----------|-------------|
| `Error` | Auto-retried with exponential backoff | Transient failures (network, timeout) |
| `FatalError` | Stops immediately, no retry | Unrecoverable (bad credentials, invalid data) |
| `RetryableError` | Custom retry timing | Rate limits, quota exceeded |

```typescript
import { FatalError, RetryableError, getStepMetadata } from "workflow";

async function apiCall() {
  "use step";
  const { attempt } = getStepMetadata();

  const res = await fetch("https://api.example.com");

  if (res.status === 401) throw new FatalError("Invalid credentials");
  if (res.status === 429) throw new RetryableError("Rate limited", { retryAfter: "60s" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);  // Will retry

  return res.json();
}
```
