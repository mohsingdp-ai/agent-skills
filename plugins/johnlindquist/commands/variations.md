---
description: Generate multiple variations of a topic with guidance and present them for selection
allowed-tools: AskUserQuestion, Read, Glob, Grep
argument-hint: [amount] [guidance] [topic]
---

# Generate Variations

Create multiple variations of a specified topic using guidance to steer the results, and present them to the user for selection.

## Arguments

- **amount**: Number of variations to generate (e.g., 3, 5, 10)
- **guidance**: Instructions to steer the variations (e.g., "make it more concise", "use conventional commit style", "focus on performance", "make it more descriptive")
- **topic**: What to create variations of (e.g., "commit message", "function name", "API endpoint design", "component structure")
  - If no topic is provided, use the selected text from the IDE extension

## Your Task

1. **Parse Arguments**
   - Extract the amount (number of variations)
   - Extract the guidance (how to steer the variations)
   - Extract the topic (what to create variations for)
   - If no topic is provided, check for selected text from the IDE extension and use that as the topic
   - If arguments are missing or unclear, ask the user for clarification

2. **Gather Context**
   - If the topic refers to code, read relevant files to understand the context
   - Use Glob/Grep to find related code if needed
   - Consider the current codebase style and conventions

3. **Generate Variations**
   - Create exactly the number of variations specified in the amount argument
   - Apply the guidance to steer all variations in the specified direction
   - Each variation should be distinct and viable while following the guidance
   - Variations should follow best practices and maintain consistency with the existing codebase
   - Consider different approaches, styles, or perspectives for each variation within the guidance constraints

4. **Present for Selection**
   - Use the AskUserQuestion tool to present all variations to the user
   - Format each option clearly with:
     - The variation itself
     - A brief description of its characteristics or benefits
   - Enable multiSelect if it makes sense for the topic (e.g., selecting multiple naming options)

## Examples

### Example 1: Commit Messages with Style Guidance
```
/variations 3 "use conventional commit format" "commit message for adding user authentication"
```
Generates 3 commit message variations all following conventional commit style

### Example 2: Function Names with Brevity Guidance
```
/variations 5 "keep it concise, under 20 characters" "function name for fetching user data with caching"
```
Generates 5 short function name options

### Example 3: Component Structure with Performance Focus
```
/variations 4 "optimize for performance and lazy loading" "React component structure for a dashboard"
```
Generates 4 architectural approaches focused on performance

### Example 4: Using Selected Text
```
// Select some code in the IDE, then run:
/variations 3 "make it more readable"
```
Generates 3 variations of the selected code with readability improvements

## Quality Guidelines

- **Guidance-Driven**: All variations must follow the guidance provided
- **Diversity**: Each variation should offer a meaningfully different approach within the guidance constraints
- **Viability**: All variations should be production-ready options
- **Context-Aware**: Consider the existing codebase patterns and conventions
- **Clear Differentiation**: Make it obvious what distinguishes each variation
- **Practical**: Focus on real-world applicable options, not theoretical extremes

## Begin

Parse the $ARGUMENTS to extract the amount, guidance, and topic. If no topic is provided, use the selected text from the IDE. Gather necessary context, generate the specified number of variations following the guidance, and present them to the user for selection.
