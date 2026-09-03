---
description: Workflow for evaluating and recording any architectural, data, AI/LLM, or frontend decision using the formal decision record protocol.
---

# ADR Decision Workflow

## Process

1. **Trigger:** An agent encounters a decision point during any stage of development, OR the user explicitly requests a decision evaluation.
2. **Load Skill:** Load the `adr-generator` skill.
3. **Registry Classification:** Identify which registry (ADR for Architecture, DDR for Data, AIDR for AI/LLM, FDR for Frontend) this decision belongs to based on the domain.
4. **Index Check:** Check existing indexes (e.g. `docs/adr/ADR-INDEX.md`) for duplicates or supersession needs. Ensure we are not re-litigating a solved problem unless requirements changed.
5. **Web Research:** Perform targeted web research on current best practices, library versions, and community consensus to ground the evaluation.
6. **Generate Approaches:** Generate 3-5 candidate approaches with full evaluation using the 17 quality controls.
7. **Run Mandatory Gates:** Filter the approaches through the 10 mandatory gates. Any approach failing a gate must be marked ineligible.
8. **Present Recommendation:** Output the comparison table and the final recommendation to the user.
9. **STOP:** Halt execution and wait for explicit user acceptance.
10. **On Acceptance:** 
    - Update the relevant INDEX (e.g., ADR-INDEX.md).
    - Update `.agents/state/decisions.md`.
    - Create the final decision file: `ADR-NNN-slug.md` (or DDR/AIDR/FDR).
11. **On Rejection:** Ask the user for specific feedback and either revise the options or abandon the decision.
