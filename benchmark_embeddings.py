from pathlib import Path
from statistics import mean, quantiles
from time import perf_counter

from pydantic import ValidationError

from consumer.embed import embed_description, load_model
from consumer.json_parser import CompanyUpserted, event_parser, parse_updated_at


def main() -> None:
    started = perf_counter()
    model = load_model()
    load_seconds = perf_counter() - started

    timings = []
    feed_path = Path(__file__).resolve().parent / "data" / "feed.jsonl"
    with feed_path.open("rb") as feed:
        for line in feed:
            try:
                event = event_parser.validate_json(line)
                parse_updated_at(event.updatedAt)
            except (ValidationError, ValueError, OverflowError, OSError):
                continue

            if not isinstance(event, CompanyUpserted):
                continue

            description = event.data.natureOfBusiness
            if not description or not description.strip():
                continue

            started = perf_counter()
            embed_description(model, description)
            timings.append(perf_counter() - started)

    print(f"Model load: {load_seconds:.2f} s")
    print(f"Descriptions embedded: {len(timings)}")
    if timings:
        print(f"Total embedding time: {sum(timings):.2f} s")
        print(f"Mean per description: {mean(timings) * 1000:.1f} ms")
    if len(timings) >= 2:
        p95 = quantiles(timings, n=100, method="inclusive")[94]
        print(f"P95 per description: {p95 * 1000:.1f} ms")


if __name__ == "__main__":
    main()
