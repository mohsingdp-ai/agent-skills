# AI SDK Integration

## Critical: Override fetch

The AI SDK uses `globalThis.fetch`. Override it with workflow's durable fetch.

```typescript
import { fetch } from "workflow";
import { generateText, generateObject } from "ai";

export async function aiWorkflow(prompt: string) {
  "use workflow";

  // CRITICAL: Must override for durability
  globalThis.fetch = fetch;

  const { text } = await generateText({
    model: "openai/gpt-4o",
    prompt,
  });

  return text;
}
```

## Structured Output with generateObject

```typescript
import { fetch } from "workflow";
import { generateObject } from "ai";
import { z } from "zod";

export async function analyzeWorkflow(content: string) {
  "use workflow";
  globalThis.fetch = fetch;

  const { object } = await generateObject({
    model: "openai/gpt-4o",
    schema: z.object({
      sentiment: z.enum(["positive", "negative", "neutral"]),
      keywords: z.array(z.string()),
      summary: z.string(),
    }),
    prompt: `Analyze: ${content}`,
  });

  return object;
}
```

## DurableAgent with Tools

Full agentic workflow with tool calling.

```typescript
import { DurableAgent } from "@workflow/ai/agent";
import { getWritable, FatalError } from "workflow";
import { convertToModelMessages, type UIMessage, type UIMessageChunk } from "ai";
import { z } from "zod";

export async function agentWorkflow(messages: UIMessage[]) {
  "use workflow";

  const writable = getWritable<UIMessageChunk>();

  const agent = new DurableAgent({
    model: "anthropic/claude-4-opus",
    system: "You are a helpful assistant with access to weather data.",
    tools: {
      getWeather: {
        description: "Get current weather for a city",
        inputSchema: z.object({ city: z.string() }),
        execute: getWeather,
      },
      searchDatabase: {
        description: "Search the knowledge base",
        inputSchema: z.object({ query: z.string() }),
        execute: searchDatabase,
      },
    },
  });

  await agent.stream({
    messages: convertToModelMessages(messages),
    writable,
  });
}

// Tool implementations as steps
async function getWeather({ city }: { city: string }) {
  "use step";

  if (Math.random() < 0.3) {
    throw new Error("Weather service unavailable");  // Will retry
  }

  const response = await fetch(`https://api.weather.com/v1/${city}`);
  if (!response.ok) throw new FatalError("City not found");

  return response.json();
}

async function searchDatabase({ query }: { query: string }) {
  "use step";
  // Query your database
  return await db.query(`SELECT * FROM knowledge WHERE content LIKE '%${query}%'`);
}
```

## RAG Agent (Knowledge Base)

```typescript
import { DurableAgent } from "@workflow/ai/agent";
import { getWritable } from "workflow";
import { z } from "zod";

export async function ragAgent(messages: UIMessage[]) {
  "use workflow";

  const writable = getWritable<UIMessageChunk>();

  const agent = new DurableAgent({
    model: "openai/gpt-4o",
    system: `You are a helpful assistant. Check your knowledge base before answering.
             If information isn't in the knowledge base, tell the user.`,
    tools: {
      addResource: {
        description: "Add information to the knowledge base",
        inputSchema: z.object({ content: z.string() }),
        execute: async ({ content }) => {
          await createResource({ content });
          return `Added "${content}" to knowledge base`;
        },
      },
      getInformation: {
        description: "Search the knowledge base for relevant information",
        inputSchema: z.object({ question: z.string() }),
        execute: async ({ question }) => {
          return await findRelevant(question);
        },
      },
    },
  });

  await agent.stream({
    messages: convertToModelMessages(messages),
    writable,
  });
}

// Nested steps for RAG operations
async function createResource(input: { content: string }) {
  "use step";
  const resource = await insertResource(input.content);
  const embeddings = await generateEmbeddings(input.content);
  await insertEmbeddings(resource.id, embeddings);
}

async function findRelevant(query: string) {
  "use step";
  const embedding = await generateEmbedding(query);
  return await vectorSearch(embedding);
}
```

## Streaming API Route for AI Chat

```typescript
import { createUIMessageStreamResponse, type UIMessage } from "ai";
import { start, getRun } from "workflow/api";
import { agentWorkflow } from "@/workflows/agent";

// Start new chat
export async function POST(request: Request) {
  const { messages }: { messages: UIMessage[] } = await request.json();

  const run = await start(agentWorkflow, [messages]);

  return createUIMessageStreamResponse({
    stream: run.readable,
    headers: { "x-workflow-run-id": run.runId },
  });
}

// Reconnect to existing chat
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const runId = searchParams.get("runId")!;
  const startIndex = parseInt(searchParams.get("startIndex") ?? "0");

  const run = getRun(runId);
  const stream = run.getReadable({ startIndex });

  return createUIMessageStreamResponse({ stream });
}
```

## Vercel AI Gateway

The AI Gateway provides a unified API for switching between models and providers without code changes. Models are specified as `provider/model-name` strings.

### Basic Usage (Plain Strings)

```typescript
import { fetch } from "workflow";
import { generateText } from "ai";

export async function gatewayWorkflow(prompt: string) {
  "use workflow";
  globalThis.fetch = fetch;

  // Switch models by changing the string
  const { text } = await generateText({
    model: "openai/gpt-4o",  // or "anthropic/claude-sonnet-4", "xai/grok-3", etc.
    prompt,
  });

  return text;
}
```

### Custom Gateway Provider Instance

Create a custom provider for different API keys or base URLs (e.g., corporate proxy):

```typescript
import { createGateway } from "@ai-sdk/gateway";

const gateway = createGateway({
  apiKey: process.env.CUSTOM_GATEWAY_KEY,  // Different env var
  baseURL: "https://proxy.company.com/ai",  // Custom base URL
});

export async function customGatewayWorkflow(prompt: string) {
  "use workflow";
  globalThis.fetch = fetch;

  const { text } = await generateText({
    model: gateway("anthropic/claude-sonnet-4"),
    prompt,
  });

  return text;
}
```

### Set Default Provider Globally

In `instrumentation.ts` (runs before AI SDK calls):

```typescript
import { gateway } from "@ai-sdk/gateway";
import { experimental_setDefaultProvider } from "ai";

export function register() {
  experimental_setDefaultProvider(gateway);
}
```

Then use models without specifying provider each time:

```typescript
const { text } = await generateText({
  model: "anthropic/claude-sonnet-4",  // Uses default gateway
  prompt,
});
```

### Model Providers

```typescript
// OpenAI
model: "openai/gpt-5"
model: "openai/gpt-4o"
model: "openai/gpt-4o-mini"
model: "openai/o4-mini"

// Anthropic
model: "anthropic/claude-opus-4"
model: "anthropic/claude-sonnet-4"

// Google
model: "google/gemini-2.5-flash"

// xAI
model: "xai/grok-3"

// Same model, different providers (format: hosted-provider@creator/model)
model: "openai@xai/grok-3"  // Grok hosted on OpenAI
model: "xai/grok-3"         // Grok on xAI directly
```

### Gateway Embeddings

```typescript
import { embed, embedMany } from "ai";
import { gateway } from "@ai-sdk/gateway";

// Single embedding via Gateway
const { embedding } = await embed({
  model: gateway.textEmbeddingModel("openai/text-embedding-3-small"),
  value: "Hello world",
});

// Batch embeddings
const { embeddings } = await embedMany({
  model: gateway.textEmbeddingModel("openai/text-embedding-3-small"),
  values: ["Hello", "World"],
});
```

### List Available Models

```typescript
import { gateway } from "@ai-sdk/gateway";

const models = await gateway.listModels();

// Filter by type
const languageModels = models.filter(m => m.type === "language");
const embeddingModels = models.filter(m => m.type === "embedding");
```

