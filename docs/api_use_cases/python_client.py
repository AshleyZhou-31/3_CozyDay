"""
A5 Part 3 — Alternative use #1: a plain Python client.

Who would use this: an external script, cron job, or another tool that
wants CozyDay's category/activity summary without a login or direct
database access — e.g. a personal dashboard aggregator.

What it produces: fetches the public /api/summary/ endpoint and prints a
short, human-readable digest of category counts and scheduled activity.
"""

import sys
import requests

API_URL = "http://127.0.0.1:8000/api/summary/"  # swap for the production URL before the final screenshot


def main():
    response = requests.get(API_URL, timeout=5)
    response.raise_for_status()
    payload = response.json()

    category_counts = payload["category_counts"]
    activity_over_time = payload["activity_over_time"]

    print(f"Fetched CozyDay public summary from {API_URL}")
    print(f"Categories tracked: {len(category_counts)}")
    for row in category_counts:
        print(f"  - {row['name']}: {row['item_count']} plan item(s)")

    total_scheduled = sum(row["count"] for row in activity_over_time)
    print(f"Total scheduled plan items across {len(activity_over_time)} day(s): {total_scheduled}")

    if category_counts:
        busiest = max(category_counts, key=lambda row: row["item_count"])
        print(f"Busiest category: {busiest['name']} ({busiest['item_count']} items)")


if __name__ == "__main__":
    sys.exit(main())