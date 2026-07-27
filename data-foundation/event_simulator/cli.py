import argparse
from pathlib import Path

from . import config
from .simulator import run

DEFAULT_OUTPUT = Path(__file__).parent / "output"


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic Aurora Games events.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                         help=f"Output directory (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--days", type=int, default=config.NUM_DAYS)
    args = parser.parse_args()

    manifest = run(args.output, seed=args.seed, num_days=args.days)

    print(f"Wrote {manifest['total_events']:,} events for {manifest['num_players']:,} players "
          f"across {args.days} days to {args.output}")
    print(f"Scenario manifest: {args.output / 'scenario_manifest.json'}")
    print(f"  Retention drop: {manifest['retention_drop']['client_site_id']} "
          f"{manifest['retention_drop']['start_date']} -> {manifest['retention_drop']['end_date']}")
    print(f"  Arbitrage ring: {len(manifest['arbitrage_ring']['player_ids'])} players on "
          f"{manifest['arbitrage_ring']['client_site_id']}, active "
          f"{manifest['arbitrage_ring']['start_date']} -> {manifest['arbitrage_ring']['end_date']}")


if __name__ == "__main__":
    main()
