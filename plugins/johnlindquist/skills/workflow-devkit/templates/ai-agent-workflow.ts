/**
 * AI Agent Workflow Template
 *
 * A durable AI agent with tool calling capabilities.
 * Uses DurableAgent from @workflow/ai/agent.
 */

import { DurableAgent } from "@workflow/ai/agent";
import { getWritable, FatalError } from "workflow";
import { convertToModelMessages, type UIMessage, type UIMessageChunk } from "ai";
import { z } from "zod";

// Main workflow function
export async function aiAgentWorkflow(messages: UIMessage[]) {
  "use workflow";

  const writable = getWritable<UIMessageChunk>();

  const agent = new DurableAgent({
    model: "openai/gpt-4o",
    system: "You are a helpful assistant with access to various tools.",
    tools: {
      getWeather: {
        description: "Get current weather for a city",
        inputSchema: z.object({
          city: z.string().describe("The city name"),
        }),
        execute: getWeather,
      },
      searchKnowledge: {
        description: "Search the knowledge base for information",
        inputSchema: z.object({
          query: z.string().describe("The search query"),
        }),
        execute: searchKnowledge,
      },
    },
  });

  await agent.stream({
    messages: convertToModelMessages(messages),
    writable,
  });
}

// Tool implementations as durable steps

async function getWeather({ city }: { city: string }) {
  "use step";

  const response = await fetch(
    `https://api.weatherapi.com/v1/current.json?q=${encodeURIComponent(city)}`
  );

  if (!response.ok) {
    if (response.status === 404) {
      throw new FatalError(`City "${city}" not found`);
    }
    throw new Error(`Weather API error: ${response.status}`);
  }

  const data = await response.json();
  return `Weather in ${city}: ${data.current.condition.text}, ${data.current.temp_c}°C`;
}

async function searchKnowledge({ query }: { query: string }) {
  "use step";

  // Replace with your actual database query
  console.log(`Searching for: ${query}`);

  return `Found relevant information about "${query}"`;
}
