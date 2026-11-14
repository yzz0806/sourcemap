"""Which claims get paid lookups: widest intervals first (docs/domain.md §4 step 5, ADR 0003).

Seeded randomness only.
"""

import random
from collections.abc import Hashable, Mapping, Sequence

from sourcemap.domain.model import Interval


def _width(iv: Interval | None) -> float:
    return 1.0 if iv is None else iv.hi - iv.lo


def pick_lookups(
    cells: Mapping[Hashable, Interval | None],
    claims_by_cell: Mapping[Hashable, Sequence[int]],
    already_valid: set[int],
    budget_n: int,
    seed: int = 0,
) -> list[int]:
    """Up to `budget_n` claim ids: cells ordered by interval width (unmeasured = 1.0) widest first,
    one claim per cell in turn, skipping claims that already have a valid verdict."""
    rng = random.Random(seed)
    order = sorted(cells, key=lambda k: (-_width(cells[k]), str(k)))
    pools = []
    for k in order:
        pool = sorted(c for c in claims_by_cell.get(k, ()) if c not in already_valid)
        rng.shuffle(pool)
        pools.append(pool)
    picked: list[int] = []
    seen: set[int] = set()
    while len(picked) < budget_n and any(pools):
        for pool in pools:
            while pool and pool[0] in seen:
                pool.pop(0)
            if pool and len(picked) < budget_n:
                c = pool.pop(0)
                picked.append(c)
                seen.add(c)
    return picked
