# 18/04 — Code Review

## Reviewer Checklist

### Correctness
- [ ] Logic matches the FR it implements
- [ ] Edge cases handled (empty input, null, max size)
- [ ] No off-by-one errors
- [ ] No race conditions in async code
- [ ] No SQL injection / XSS / SSRF

### Performance
- [ ] No N+1 queries
- [ ] Hot path uses async I/O
- [ ] Caching considered
- [ ] No unnecessary LLM calls

### Security
- [ ] No secrets in code
- [ ] Inputs validated (Pydantic)
- [ ] Outputs sanitized
- [ ] Auth checked on every endpoint
- [ ] Rate limit on sensitive endpoints

### Maintainability
- [ ] Naming clear (no abbreviations)
- [ ] Single responsibility per function
- [ ] No magic numbers (use constants)
- [ ] Tests cover the change
- [ ] PR size < 500 lines

### Schema
- [ ] If schema changed: migration added
- [ ] If schema changed: downstream services updated
- [ ] JSON outputs validate against schema

### LLM-specific
- [ ] Prompts include Turkish market context
- [ ] Prompts have failure mode defined
- [ ] Hallucination guards in place
- [ ] Cost budget reasonable

## Review SLA

- First review within 4 hours (business hours)
- Approval within 24 hours
- If blocked > 48 hours, escalate to lead
