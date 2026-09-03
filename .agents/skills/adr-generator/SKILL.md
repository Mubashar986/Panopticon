---
name: adr-generator
description: Generates formal, rigorous decision records (ADR, DDR, AIDR, FDR) for any architectural, data modeling, AI/LLM/RAG, or frontend decision point. Use whenever a WBS task surfaces an undecided technology choice, library selection, data schema design, AI pipeline configuration, or frontend architecture question. Evaluates 3-5 candidate approaches against 17 quality controls and 10 mandatory gates, performs live web research for current best practices, and produces a formal record for user acceptance.
---

# ADR Generator Skill

This is a comprehensive decision-engineering skill that produces formal decision records.

## 1. When to use this skill
Use this skill whenever a decision point surfaces during any stage of development. Triggers include:
- A WBS task surfaces an undecided technology choice.
- Selection of a new library or tool.
- Data schema design choices or migrations.
- AI pipeline configuration (e.g. LLM prompts, RAG strategy).
- Frontend architecture questions (e.g. state management, API integration, routing).

If a choice will impact the system's architecture, security, maintainability, or data integrity, do NOT guess. Halt implementation and use this skill.

## 2. The Standard 4-Part Decision Protocol
When invoking this skill, you must follow the 4-part decision protocol exactly:
1. **What is the decision?** (Exact problem statement & boundary. State clearly what is being decided and what is out of scope).
2. **Why do we need this decision?** (PRD drivers, risk of drift. Detail what product requirements are forcing this choice and the risks if we choose poorly).
3. **What are the candidate approaches?** (3-5 evaluated with web research. Explore the solution space, ensuring at least one standard/boring approach and one modern/alternative approach).
4. **How is it implemented in our system?** (Concrete blueprint. Map the theoretical choice to the actual codebase).

## 3. 4 Decision Record Types
Based on the domain of the decision, classify the output into one of the following record types:
- **ADR (Architecture Decision Record):** Architecture & Infrastructure. Use for database choices, caching layers, deployment strategies, and auth mechanisms.
- **DDR (Data Decision Record):** Data Modeling & Storage. Use for schemas, migrations, isolation, consistency models, and transaction management.
- **AIDR (AI Decision Record):** AI/LLM/RAG/Agents. Use for prompt management, RAG pipeline design, structured output handling, and LLM evaluation strategies.
- **FDR (Frontend Decision Record):** Frontend Architecture. Use for framework selection, global state, styling paradigms, and API integration patterns.

## 4. The 17 Quality Controls
Evaluate every option against these 17 controls using a score of 1-5, providing a 1-line justification for each score:
1. PRD alignment
2. Correctness
3. Security
4. Privacy
5. Maintainability
6. Scalability
7. Performance
8. Reliability
9. Data integrity
10. Explainability
11. Auditability
12. Extensibility
13. AI safety
14. MVP fit
15. Cost
16. Implementation effort
17. Risk

## 5. The 10 Mandatory Gates
These are pass/fail gates. If an option fails ANY gate, it cannot be recommended.
1. LLM output must not directly become official learning state.
2. Student state must be isolated per student and exam.
3. Learning-state transitions must be valid and auditable.
4. Generated questions must be validated before student use.
5. Source-grounded answers must use retrieval before generation.
6. Role-based access must be enforced server-side.
7. Uploaded files must be treated as untrusted.
8. The system must not silently advance a student after critical failure.
9. Important decisions must be explainable.
10. Provider-specific logic must not be embedded in core learning logic.

*Note: Any option that fails a gate is automatically ineligible for recommendation, regardless of score. Assumptions used to justify a gate pass must be listed explicitly.*

## 6. Scoring Rubric
Every score (1-5) must map to this exact rubric and include a 1-line justification referencing a PRD/SRS section or explicitly stated assumption.
- **1:** Fails outright / violates a mandatory gate / actively unsafe
- **2:** Weak — workable only with major rework
- **3:** Adequate — meets the stated PRD requirement, nothing more
- **4:** Strong — meets the requirement with margin, some evidence
- **5:** Excellent — evidenced, exceeds the requirement without overengineering

## 7. Priority Order for Breaking Ties
When two options are close in score, use the following priority order to break ties (fixed order, do not change):
1. AI safety / Security / Privacy — non-negotiable floor
2. Correctness / Data integrity / Reliability
3. Auditability / Explainability
4. PRD alignment / MVP fit
5. Maintainability / Extensibility
6. Scalability / Performance
7. Cost / Implementation effort

The recommendation must state *which tier* broke the tie.

## 8. Required Output Format per Option
For each of the 3-5 evaluated candidate approaches, provide:
1. Option name
2. Short description
3. How it works
4. PRD/SRS traceability
5. Pros
6. Cons
7. Risks
8. Mandatory gate table: gate # → pass/fail → verification method
9. Quality score 1–5 for all 17 controls, each with a one-line justification
10. MVP suitability
11. Long-term suitability
12. Reversibility (cost/effort to undo later)

## 9. Required Final Output
The final generated record MUST include:
1. Comparison table (all options × all quality controls + gate pass/fail)
2. Recommended option
3. Why recommended (citing priority order)
4. Why others were rejected (citing failed gates or specific tier weakness)
5. Consequences of the recommendation
6. Implementation notes (concrete blueprint)
7. Rollback plan for the recommendation
8. Consistency check against prior ADRs
9. Open risks
10. Follow-up decisions
11. Machine-readable YAML summary block

## 10. Machine-Readable YAML Summary Block
Append this block at the bottom of the decision record file:
```yaml
adr_id: ADR-XXX
title: ""
decision_level: ""
status: proposed        # proposed | accepted | superseded
date: ""
depends_on: []
supersedes: []
gates:
  - id: 1
    result: pass        # pass | fail
    evidence: ""
recommended_option: ""
priority_tier_used_for_tiebreak: ""
open_assumptions: []
```

## 11. Living Decision Evolution Protocol
Decisions are not written in stone. Use the following status lifecycle:
- **PROPOSED:** Initial generation. Waiting for explicit user acceptance.
- **ACCEPTED:** User approved. The implementation can proceed based on this record.
- **SUPERSEDED:** A later decision overrides this one. The YAML block must point to the new ID, and the old record is kept for historical context.

## 12. Anti-patterns (Forbidden regardless of score)
- Storing raw LLM output as canonical learning state.
- Trusting client-supplied role/permission flags.
- Serving generated questions without a validation step.
- Embedding provider-specific SDK calls inside core domain/learning logic.
- Treating uploaded file content as executable or trusted input.
- Silent retries or advancement past a critical failure state.

## 13. Web Research Requirements
Before generating the 3-5 approaches, YOU MUST perform live web research:
- Search for current library versions and known issues.
- Search for current best practices relevant to the problem.
- Include benchmarks or community consensus where applicable.
- Do not rely purely on training data.
