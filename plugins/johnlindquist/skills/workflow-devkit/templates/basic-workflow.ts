/**
 * Basic Workflow Template
 *
 * A simple durable workflow with steps.
 * Steps are automatically retried on failure.
 */

import { sleep, FatalError } from "workflow";

// Main workflow function
export async function basicWorkflow(input: string) {
  "use workflow";

  // Step 1: Validate input
  const validated = await validateInput(input);

  // Step 2: Process data
  const result = await processData(validated);

  // Wait 5 seconds (doesn't consume resources)
  await sleep("5s");

  // Step 3: Finalize
  await finalizeResult(result);

  return { success: true, result };
}

// Steps must be in the SAME FILE as the workflow

async function validateInput(input: string) {
  "use step";

  if (!input || input.trim().length === 0) {
    // FatalError stops immediately, no retry
    throw new FatalError("Input cannot be empty");
  }

  return input.trim().toLowerCase();
}

async function processData(data: string) {
  "use step";

  // Simulate processing
  const response = await fetch(`https://api.example.com/process?data=${data}`);

  if (!response.ok) {
    // Regular errors are automatically retried
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

async function finalizeResult(result: unknown) {
  "use step";

  console.log("Finalizing result:", result);
  // Save to database, send notification, etc.
}
