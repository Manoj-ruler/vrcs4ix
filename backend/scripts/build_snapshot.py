"""Download the raw Elexon rows for the configured window and store them as the bundled snapshot.

The snapshot holds the unmodified API rows (all forecast versions). It is only a fallback when the
live API is unreachable; the cutoff rule is still applied at runtime.

    cd backend && python -m scripts.build_snapshot
"""

import asyncio

from app.clients.elexon import ElexonClient
from app.core.config import get_settings
from app.services.analysis import build_dataset, fetch_live, write_raw_file


async def main() -> None:
    s = get_settings()
    raw = await fetch_live(s, ElexonClient(s.elexon_base_url, s.http_timeout_s, s.http_max_retries, s.http_concurrency))
    q = build_dataset(raw, s).quality
    write_raw_file(s.snapshot_path, raw, s)
    print(f"wrote {s.snapshot_path} fuelhh={len(raw.fuelhh)} windfor={len(raw.windfor)} matched={q.matched_pairs}")


if __name__ == "__main__":
    asyncio.run(main())
