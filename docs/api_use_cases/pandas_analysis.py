"""
A5 Part 3 — Alternative use #2: notebook/pandas-style analysis.

Who would use this: a classmate or stakeholder doing a quick data pass on
CozyDay's public numbers in a notebook, without touching the database.

What it produces: loads the public /api/summary/ endpoint into pandas
DataFrames and prints grouped statistics (average items per category,
busiest scheduled day).
"""

import requests
import pandas as pd

API_URL = "http://127.0.0.1:8000/api/summary/"  # swap for the production URL before the final screenshot


def main():
    payload = requests.get(API_URL, timeout=5).json()

    categories_df = pd.DataFrame(payload["category_counts"])
    activity_df = pd.DataFrame(payload["activity_over_time"])

    print("Category counts:")
    print(categories_df)

    if not categories_df.empty:
        print(f"\nAverage plan items per category: {categories_df['item_count'].mean():.2f}")

    if not activity_df.empty:
        activity_df["date"] = pd.to_datetime(activity_df["date"])
        busiest_day = activity_df.loc[activity_df["count"].idxmax()]
        print(f"\nBusiest scheduled day: {busiest_day['date'].date()} with {busiest_day['count']} item(s)")
        print(f"Total scheduled items across {len(activity_df)} day(s): {activity_df['count'].sum()}")


if __name__ == "__main__":
    main()