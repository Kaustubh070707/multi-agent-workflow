"""Guards: step limit, loop detection, cost breaker."""
MAX_STEPS = 25

def should_stop(steps: int, cost_usd: float, max_cost: float = 0.50) -> bool:
    return steps >= MAX_STEPS or cost_usd >= max_cost
