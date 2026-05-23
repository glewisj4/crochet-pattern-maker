"""Stagger increase/decrease positions to avoid stacked corners."""


def stagger_positions(previous_count: int, operations: int, round_number: int) -> tuple[int, ...]:
    if previous_count <= 0 or operations <= 0:
        return ()

    operations = min(operations, previous_count)
    step = previous_count / operations
    offset = (round_number * 0.37 * step) % step
    positions = sorted({max(1, min(previous_count, int(round(offset + i * step)) + 1)) for i in range(operations)})

    probe = 1
    while len(positions) < operations and probe <= previous_count:
        if probe not in positions:
            positions.append(probe)
        probe += 1

    return tuple(sorted(positions[:operations]))

