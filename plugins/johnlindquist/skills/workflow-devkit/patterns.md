# Workflow Patterns

## Sequential Pipeline

Multi-step processing with quality checks.

```typescript
export async function sequentialWorkflow(input: string) {
  "use workflow";
  globalThis.fetch = fetch;

  const { text } = await generateText({ model: "openai/gpt-4o", prompt: input });
  const { object } = await generateObject({
    model: "openai/gpt-4o",
    schema: z.object({ score: z.number(), feedback: z.string() }),
    prompt: `Evaluate: ${text}`,
  });

  return { output: text, quality: object };
}
```

## Parallel Operations

Concurrent execution with Promise.all.

```typescript
export async function parallelWorkflow(code: string) {
  "use workflow";
  globalThis.fetch = fetch;

  const [security, performance, style] = await Promise.all([
    reviewSecurity(code),
    reviewPerformance(code),
    reviewStyle(code),
  ]);

  return { security, performance, style };
}

async function reviewSecurity(code: string) {
  "use step";
  const { object } = await generateObject({
    model: "openai/gpt-4o",
    schema: z.object({ vulnerabilities: z.array(z.string()), risk: z.enum(["low", "medium", "high"]) }),
    prompt: `Security review: ${code}`,
  });
  return object;
}
```

## Dynamic Routing

Route to different handlers based on classification.

```typescript
export async function routingWorkflow(query: string) {
  "use workflow";
  globalThis.fetch = fetch;

  const { object } = await generateObject({
    model: "openai/gpt-4o",
    schema: z.object({ type: z.enum(["general", "technical", "billing"]) }),
    prompt: `Classify this query: ${query}`,
  });

  const handlers = { general: handleGeneral, technical: handleTechnical, billing: handleBilling };
  return handlers[object.type](query);
}
```

## Evaluator Loop

Iterative refinement until quality threshold.

```typescript
export async function evaluatorWorkflow(input: string) {
  "use workflow";
  globalThis.fetch = fetch;

  let result = await generateInitial(input);

  for (let i = 0; i < 3; i++) {
    const { object: evaluation } = await generateObject({
      model: "openai/gpt-4o",
      schema: z.object({ score: z.number(), improvements: z.array(z.string()) }),
      prompt: `Evaluate: ${result}`,
    });

    if (evaluation.score >= 8) break;

    result = await improve(result, evaluation.improvements);
  }

  return result;
}
```

## Webhooks (Human-in-the-Loop)

Pause workflow until external callback.

```typescript
import { createWebhook } from "workflow";

export async function approvalWorkflow(userId: string) {
  "use workflow";

  const webhook = createWebhook();

  await sendEmail({
    to: "manager@example.com",
    approveUrl: `${webhook.url}?action=approve`,
    rejectUrl: `${webhook.url}?action=reject`,
  });

  // PAUSES until webhook called
  const response = await webhook;
  const action = new URL(response.url).searchParams.get("action");

  return { approved: action === "approve" };
}
```

## Multiple Concurrent Webhooks

```typescript
export async function rsvpWorkflow(emails: string[]) {
  "use workflow";

  const webhooks = emails.map(() => createWebhook());
  await Promise.all(emails.map((email, i) => sendRsvpEmail(email, webhooks[i].url)));

  const responses = await Promise.all(
    webhooks.map(wh => wh.then(req => new URL(req.url).searchParams.get("reply")))
  );

  return responses;
}
```

## Actor Pattern (Event-Driven)

Long-running workflow processing events sequentially.

```typescript
import { defineHook, getWorkflowMetadata } from "workflow";

export type Event = { type: "increment" } | { type: "decrement" } | { type: "reset" };
export const counterHook = defineHook<Event>();

export async function counterActor(initialCount: number) {
  "use workflow";

  const { workflowRunId } = getWorkflowMetadata();
  let count = initialCount;

  const receive = counterHook.create({ token: `counter:${workflowRunId}` });

  for await (const event of receive) {
    switch (event.type) {
      case "increment": count++; break;
      case "decrement": count--; break;
      case "reset": count = 0; break;
    }
  }
}
```

### Send Events to Actor (API Route)

```typescript
import { counterHook, type Event } from "@/workflows/counter-actor";

export async function POST(req: Request, { params }: { params: { id: string } }) {
  const event: Event = await req.json();
  const result = await counterHook.resume(`counter:${params.id}`, event);
  return Response.json({ success: !!result });
}
```

## Batching

Process items in chunks.

```typescript
export async function batchWorkflow(items: string[]) {
  "use workflow";

  const chunks = chunk(items, 10);

  for (const batch of chunks) {
    await Promise.all(batch.map(processItem));
  }
}

async function processItem(item: string) {
  "use step";
  return await doWork(item);
}

function chunk<T>(arr: T[], size: number): T[][] {
  return Array.from({ length: Math.ceil(arr.length / size) }, (_, i) =>
    arr.slice(i * size, i * size + size)
  );
}
```

## Streaming Progress

Real-time updates to frontend.

```typescript
import { getWritable } from "workflow";

export async function progressWorkflow(taskId: string) {
  "use workflow";

  const writable = getWritable<{ step: number; message: string }>();
  const writer = writable.getWriter();

  await writer.write({ step: 1, message: "Starting..." });
  await step1();

  await writer.write({ step: 2, message: "Processing..." });
  await step2();

  await writer.close();
  return { success: true };
}
```
