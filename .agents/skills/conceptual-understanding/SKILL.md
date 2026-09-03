---
name: concept-to-code-bridge
description: Creates a Stage 1 Understanding Artifact for any project. Bridges abstract engineering concepts to concrete code in the current repository using visuals, physical analogies, data-flow traces, and stack-aware explanations. Best for users who learn through diagrams, analogies, and why-first reasoning.
---

# Concept-to-Code Bridge Skill

This is **Stage 1** of the generic task lifecycle. It must happen before design and implementation for any non-trivial task. Its purpose is to help the user understand the concept deeply before touching code.

This skill is **stack-adaptive**. Use the current repository's real language, framework, package manager, runtime, files, endpoints, components, and commands. Do not reuse examples from another project unless they genuinely match this codebase.

---

## Core Principles (Non-Negotiable)

1. **Visuals are mandatory.** Include at least two Mermaid diagrams. If an image-generation tool is available, also create and embed:
   - One architecture infographic showing the system-level concept.
   - One data-flow diagram showing how one user action/request travels through the system.
   If image generation is unavailable, clearly say so and use Mermaid diagrams instead.

2. **Physical analogies are mandatory.** Map every major concept to a real-world scenario such as post offices, hotel check-in desks, traffic lights, bouncers, receptionists, notebooks, warehouses, or assembly lines.

3. **Never explain "what" without "why".** For every technical decision, explain:
   - Why does this exist?
   - What problem does it solve?
   - What breaks if we skip it?

4. **Reference the current codebase, not textbooks.** Every concrete example should point to actual files, functions, classes, components, routes, schemas, or configuration in the current workspace.

5. **Do not write implementation code.** This stage is for understanding only.

---

## Required Document Structure

Save as `task_X_Y_understanding.md` in the artifact directory.

### Section 1: Visual Architecture

- Put the main architecture visual at the top.
- Use Mermaid if image generation is unavailable.
- The diagram should show the user, UI/API entry point, major application layers, data/storage, external services, and response path when relevant.

### Section 2: The Physical Analogy

Open with a 3-5 sentence analogy that maps the concept to a physical-world scenario.

Example:

> Token refresh is like using a short-lived visitor badge plus a longer-lived renewal pass. The visitor badge gets you through doors for a short time. When it expires, the renewal pass lets reception issue a fresh badge without making you register again.

### Section 3: Why & What

Explain:

- **Why are we doing this task?** User/business/product motivation.
- **What is the concept?** Plain-language definition.
- **What breaks if we skip it?** Concrete failure scenarios.

### Section 4: Abstraction Level Map

Adapt the levels to the current stack:

```markdown
| Level | What Lives Here | Current Project Example |
|-------|-----------------|-------------------------|
| Product/User Experience | User goals, screens, workflows | e.g. Login page, dashboard, admin flow |
| Application | Business rules, route handlers, state, services | e.g. service function, React hook, API route |
| Framework | Web/server/UI framework primitives | e.g. FastAPI router, React component, Express middleware |
| Library | Reusable packages and SDKs | e.g. axios, SQLAlchemy, TanStack Query, pytest |
| Runtime | Browser, Node.js, Python, JVM, Go runtime, etc. | e.g. browser event loop, ASGI server |
| OS/Infrastructure | Processes, files, sockets, containers, databases | e.g. local server, Docker, PostgreSQL |
```

Mark which levels the current task touches.

### Section 5: Mermaid Diagrams

Include at least two diagrams:

1. A `sequenceDiagram` tracing one complete user action/request.
2. A `flowchart` or `graph TD` showing component relationships or decision branches.

Use real names from the repository when known.

### Section 6: Data Flow Trace-Through

Walk through one complete path step by step. Adapt the path to the task.

Example format:

1. User clicks a button or sends a request.
2. UI/router/middleware receives it.
3. Validation runs.
4. State/service/API call executes.
5. Database/cache/external API is used if relevant.
6. Response returns.
7. UI/state updates.
8. Errors are surfaced if something fails.

### Section 7: Cognitive Model → Code Mapping

Map human thinking to actual code concepts:

```markdown
| Cognitive Stage | Mental Model | Code Concept in This Project | Enforcement/Guardrail |
|-----------------|--------------|------------------------------|-----------------------|
| 1. Analogy | "A bouncer checks your wristband" | Auth guard / middleware / protected route | Blocks unauthenticated users |
| 2. Constraint | "Only admins enter this room" | Role check / permission function | Prevents unauthorized actions |
| 3. State change | "Renew the wristband before it expires" | Token refresh / session update | Keeps user logged in safely |
```

### Section 8: Language/Stack Context

Explain how the concept appears in this specific stack:

- Language-specific patterns.
- Framework-specific lifecycle.
- Package/library responsibilities.
- Actual function signatures, component props, schemas, endpoints, or configuration references.

Examples by stack:

- React: components, hooks, context/store, router loaders/actions, query cache, form validation.
- FastAPI: routers, dependencies, Pydantic schemas, services, repositories, middleware.
- Node/Express: middleware, controllers, services, validation schemas.
- Rust: ownership, `Result`, async runtime, extractors, traits.

### Section 9: Five Alternative Approaches

```markdown
| # | Alternative | Pros | Cons | When to Choose |
|---|-------------|------|------|----------------|
| 1 | ... | ... | ... | ... |
| 2 | ... | ... | ... | ... |
| 3 | ... | ... | ... | ... |
| 4 | ... | ... | ... | ... |
| 5 | ... | ... | ... | ... |
```

### Section 10: Production Rationale & Consequences

Split into two sub-sections:

**Why This Is Standard:**

- Explain industry/common-practice rationale.
- Mention standards or well-known patterns when relevant.

**What Happens If We Skip This:**

- Describe at least two concrete failure scenarios.
- Include user impact, developer impact, and system impact.

---

## Workflow Checklist

Before marking the Understanding Artifact as complete, verify:

- [ ] At least 2 Mermaid diagrams included.
- [ ] Image visuals added if an image-generation tool is available, or limitation stated if unavailable.
- [ ] Physical analogy included.
- [ ] Why/what/what-breaks explained.
- [ ] Abstraction level table filled in with current-project examples.
- [ ] Data-flow trace-through completed.
- [ ] Cognitive model to code mapping table completed.
- [ ] Stack-specific context included.
- [ ] 5 alternatives compared.
- [ ] At least 2 failure/disaster scenarios described.
- [ ] Current codebase references are accurate and clickable where possible.
