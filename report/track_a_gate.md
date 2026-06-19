# Track A gate report

Generated: 2026-06-19T16:34:23.708907+00:00

## SPRT (SearchScorer vs pool)
- Search wins: 8/24 (33.3%)
- Heuristic wins: 20/24 (83.3%)
- SPRT decision: **continue** (log_ratio=-1.263)
- Gate passed: **False**

## Packaging
- Package: (not built)

## Suggested submit command (DO NOT run automatically)
```
(none — gate failed)
```

## Notes
gate not passed; no package built

Wire SearchScorer in submission by replacing default agent factory:
```python
from agent.search_policy import SearchScorer
from agent.agent import build_agent
_AGENT = build_agent(scorer=SearchScorer())
```
