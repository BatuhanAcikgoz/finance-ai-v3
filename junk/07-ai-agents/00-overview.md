# 07 — AI Agents Overview

> 14 files: this overview + 13 agent specs. Every agent is a stateless service that receives a task, produces a structured output, and logs to OTel.

## Agent Catalog

| #  | Agent         | Role                                       | Phase | LLM model         |
|----|---------------|--------------------------------------------|-------|-------------------|
| 01 | Supervisor    | Top-level orchestrator, evidence aggregator | P2   | MiniMax M3        |
| 02 | Technical     | Technical analysis interpretation           | P1   | MiniMax M3        |
| 03 | Fundamental   | Financial statements, ratios, peers        | P2   | MiniMax M3        |
| 04 | Macro         | TCMB/TÜİK/BDDK interpretation, regime       | P2   | MiniMax M3        |
| 05 | News          | News classification, ticker extraction      | P2   | MiniMax M3        |
| 06 | Sentiment     | Turkish NLP sentiment                       | P2   | MiniMax M3        |
| 07 | Sector        | Sector rotation, relative strength          | P2   | MiniMax M3        |
| 08 | Risk          | VaR/CVaR/beta computation (deterministic)   | P2   | None (rule-based) |
| 09 | Portfolio     | Exposure, position sizing, drift            | P2   | None (rule-based) |
| 10 | Backtest      | Hit-rate, calibration, weight proposal      | P3   | MiniMax M3        |
| 11 | Compliance    | Disclaimer, forbidden language, evidence    | P3   | MiniMax M3        |
| 12 | Memory        | Embedding, similarity search                | P2   | None (rule-based) |
| 13 | Report        | Narrative generation, action items          | P2   | MiniMax M3        |

## Common Anatomy

Every agent file MUST define:
1. **Role** — one sentence
2. **Responsibilities** — bulleted list
3. **Inputs** — schema references
4. **Outputs** — schema references
5. **Tools** — functions/APIs available
6. **Prompt strategy** — reference to `08-prompts/`
7. **Hallucination guards** — specific to this agent
8. **Quality checks** — automatic validators
9. **Escalation rules** — when to flag for human review
10. **Cost budget** — max LLM tokens/cost per call
