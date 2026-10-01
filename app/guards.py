"""Guards: step limit, loop detection, cost breaker. Single source of truth.

Both app/main.py and app/graph.py read these — never duplicate the numbers.
"""
MAX_STEPS = 25
MAX_COST_USD_PER_RUN = 0.50
# Placeholder pricing per tool call until real LLM billing plugs in (SKILL.md).
COST_PER_SEARCH = 0.01
COST_PER_EXEC = 0.001
# Consecutive failures before giving up with status error (guard is the backstop).
MAX_RETRIES = 3


def should_stop(steps: int, cost_usd: float, max_cost: float = MAX_COST_USD_PER_RUN) -> bool:
    return steps >= MAX_STEPS or cost_usd >= max_cost
