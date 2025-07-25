# High-Performance Prompt Design Guidelines

## Preservation of Intent Principle

**When Improving Existing Prompts**: These guidelines are designed to enhance prompt structure and clarity, NOT to alter the fundamental purpose or behavior of existing prompts. When applying these patterns to improve an existing prompt:

-   **Core Functionality Must Remain**: The original prompt's primary objective, scope, and intended outcomes must be preserved exactly
-   **Information Fidelity**: All original requirements, constraints, and behavioral specifications must be retained
-   **Enhancement, Not Replacement**: Changes should improve organization, clarity, and execution efficiency without modifying what the prompt accomplishes
-   **Domain Expertise Preservation**: Technical details, specific instructions, and domain knowledge from the original prompt must be transferred intact

The goal is structural optimization while maintaining functional equivalence. Think of it as refactoring code - the external behavior remains identical while internal organization improves.

## Core Structural Principles

**Task-First Architecture**: Modern prompts lead with a concise `<task>` declaration that states the primary objective in one clear sentence. This is followed by context, not preceded by it. The task acts as an anchor that all subsequent instructions reference.

**Context-Task-Steps Flow**: The optimal structure follows this pattern:

1. `<task>` - What needs to be done (one sentence)
2. `<context>` - Situational awareness and background
3. `<working_dir>` - Where to operate (if applicable)
4. `<steps>` - How to accomplish the task
5. `<validation_requirements>` - Quality gates and checks
6. `<output_format>` - Expected deliverables

**Explicit Goal Declaration**: The main objective is stated clearly in the `<task>` section, with all subsequent sections supporting this primary goal.

## Formatting and Organization Techniques

**XML-Style Section Headers**: Uses descriptive tags like `<communication>`, `<tool_calling>`, `<maximize_parallel_tool_calls>` to create clear cognitive boundaries. These act as both organizational tools and semantic anchors for different behavioral modes.

**Graduated Emphasis Patterns**: Employs multiple levels of emphasis strategically:

-   **Bold for critical concepts** that must not be missed
-   _Italics for strong emphasis_ on important but secondary points
-   CAPS for absolute imperatives that override other instructions
-   Numbered lists only for sequential processes
-   Bullet points sparingly, primarily for enumeration rather than instruction flow

**Contextual Density Management**: Dense technical sections are broken up with concrete examples and practical applications, preventing cognitive overload while maintaining precision.

## Instruction Clarity Methods

**Imperative Language Dominance**: Uses direct commands ("ALWAYS follow", "NEVER refer to", "DEFAULT TO PARALLEL") rather than suggestions or preferences. This removes interpretation ambiguity.

**Negative Space Definition**: Explicitly states what NOT to do alongside positive instructions. The prompt doesn't just say "use tools efficiently" but specifically prohibits "slow sequential tool calls when not necessary."

**Conditional Logic Structures**: Employs if-then patterns extensively ("If you create any temporary files... clean up these files", "IF there are no relevant tools... ask the user"). This creates decision trees for complex scenarios.

**Behavioral Boundary Setting**: Establishes clear operational limits and exception handling before they become issues, reducing the need for course correction during execution.

## Context Integration Strategies

**Dynamic Context Adaptation**: Instructions scale based on available information rather than assuming fixed input patterns. The AI is taught to assess context quality and act accordingly.

**Feedback Loop Integration**: Builds in self-correction mechanisms ("After receiving tool results, carefully reflect on their quality") that allow for adaptive behavior based on intermediate outcomes.

## Advanced Behavioral Programming

**Parallel Processing Optimization**: Dedicates an entire section to efficiency patterns, treating performance as a first-class concern rather than an afterthought. This section demonstrates how to embed optimization thinking directly into behavioral instructions.

**Error Prevention Through Constraint Design**: Rather than handling errors reactively, the prompt prevents them by constraining possible actions ("DO NOT loop more than 3 times on fixing linter errors").

**Meta-Cognitive Instructions**: Includes thinking-about-thinking directives ("briefly consider: What information do I need") that program higher-order reasoning patterns.

**Progressive Disclosure Management**: Balances thoroughness with cognitive load by revealing complexity gradually and contextually.

## Wake AI-Specific Patterns

**Step-Based Execution Model**: Wake AI prompts structure work as numbered steps with:

-   **Bold headings** for major steps
-   Letter-indexed (a, b, c) sub-steps for complex operations
-   Bullet points for specific checks within sub-steps
-   Inline code examples and tool commands where relevant

**Validation-Driven Workflow**: Every Wake AI prompt includes explicit validation sections:

-   `<validation_requirements>` or `<validation_practices>` blocks
-   Technical evidence standards
-   False positive elimination criteria
-   Severity classification guidelines

**Tool Integration Syntax**: Prompts explicitly reference command-line tools:

```bash
wake init
wake detect reentrancy
wake print storage-layout <file>
```

**Structured Output Specifications**: The `<output_format>` section provides:

-   Complete YAML/Markdown structure examples
-   Field-by-field documentation
-   Real-world code examples
-   File naming conventions

**Progressive Refinement Pattern**: Wake AI workflows scoped for static analysis follow a three-phase pattern:

1. **Discovery Phase**: Initial scanning and identification
2. **Analysis Phase**: Deep validation and verification
3. **Documentation Phase**: Structured output generation

## Quality Assurance Mechanisms

**Redundant Critical Instructions**: Important directives appear in multiple forms and contexts, ensuring they're not overlooked during complex operations.

**Validation Checkpoints**: Built-in verification steps ("Check that all the required parameters for each tool call are provided") that enforce quality gates.

**Scope Limitation Techniques**: Uses precise boundary language ("Do what has been asked; nothing more, nothing less") to prevent scope creep while maintaining helpfulness.

**Citation and Reference Standards**: Establishes specific formatting requirements for technical precision, showing how to embed quality standards directly into operational instructions.

## Scalability and Maintenance Features

**Modular Section Design**: Each major section could be updated independently without affecting others, suggesting a component-based approach to prompt architecture.

**Override Mechanisms**: Includes clear priority hierarchies ("If you see a section called '<most_important_user_query>', you should treat that query as the one to answer") for handling conflicting instructions.

**Future-Proofing Language**: Uses extensible patterns that can accommodate new tools or requirements without structural rewrites.

The overall effect is a prompt that functions more like a comprehensive operating system for AI behavior than a simple instruction set. It anticipates edge cases, optimizes for performance, and maintains consistency across complex multi-step operations while remaining adaptable to context variations.
