# -*- coding: utf-8 -*-
"""
[고도화] 확장 카탈로그(1년, 401건)에 대해 기존 시뮬레이션 엔진을 그대로 재실행한다.

기존 simulate_engagement_and_reviews.py 의 핵심 함수(simulate_event_daily_views,
simulate_reviews, novelty_decay, discount_boost 등)를 그대로 import 해서 재사용한다
— 로직을 복붙하지 않고, "같은 엔진에 더 넓은 입력을 넣었을 때" 결과가 어떻게
바뀌는지를 보기 위함이다 (엔진 자체는 원본과 동일해야 비교가 공정하다).

출력:
  data/eventhub_events_extended.csv          (재사용: category_ko 채움)
  data/eventhub_event_daily_engagement_extended.csv
  data/eventhub_reviews_extended.csv
  data/eventhub_platform_daily_extended.csv  ★ 확장 시나리오 최종 데이터셋 (365일)
"""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/claude/eventhub-trend-analysis/scripts")
from simulate_engagement_and_reviews import simulate_event_daily_views, simulate_reviews  # noqa: E402

BASE = "/home/claude/eventhub-trend-analysis/data/"
CATEGORY_KO = {
    "fashion": "패션", "beauty": "뷰티", "food": "푸드", "tech": "테크",
    "delivery": "딜리버리", "stay": "스테이", "living": "리빙", "popup": "팝업",
}


def build_catalog_daily(events: pd.DataFrame) -> pd.DataFrame:
    """build_timeseries.py 의 카탈로그 집계 로직 (활성/신규/카테고리별) 재사용."""
    date_min, date_max = events["period_start"].min(), events["period_end"].max()
    date_range = pd.date_range(date_min, date_max, freq="D")
    categories = sorted(events["category"].unique())

    rows = []
    for d in date_range:
        active_mask = (events["period_start"] <= d) & (events["period_end"] >= d)
        active = events[active_mask]
        row = {
            "date": d,
            "active_events": int(active_mask.sum()),
            "new_events": int((events["period_start"] == d).sum()),
            "active_brand": int((active["merchant_type"] == "브랜드").sum()),
            "active_merchant": int((active["merchant_type"] == "소상공인").sum()),
        }
        for c in categories:
            row[f"active_{c}"] = int((active["category"] == c).sum())
        rows.append(row)

    daily = pd.DataFrame(rows)
    daily["weekday"] = daily["date"].dt.dayofweek
    daily["weekday_ko"] = daily["date"].dt.day_name().map({
        "Monday": "월", "Tuesday": "화", "Wednesday": "수", "Thursday": "목",
        "Friday": "금", "Saturday": "토", "Sunday": "일",
    })
    return daily


def main():
    events = pd.read_csv(BASE + "eventhub_events_extended.csv", parse_dates=["period_start", "period_end"])
    events["category_ko"] = events["category"].map(CATEGORY_KO)
    events.to_csv(BASE + "eventhub_events_extended.csv", index=False, encoding="utf-8-sig")
    print(f"확장 카탈로그: {len(events)}건 (실제 {int(events['is_real'].sum())}건 + "
          f"백필 {int((~events['is_real']).sum())}건)")

    catalog_daily = build_catalog_daily(events)

    print("\n[1/2] 관심도(조회수/좋아요) 시뮬레이션 실행 중...")
    event_daily = simulate_event_daily_views(events)
    event_daily.to_csv(BASE + "eventhub_event_daily_engagement_extended.csv", index=False, encoding="utf-8-sig")
    print(f"  이벤트x일 레코드: {len(event_daily)}건, 총 조회수: {event_daily['views'].sum():,}")

    print("[2/2] 리뷰 시뮬레이션 실행 중...")
    reviews = simulate_reviews(events, event_daily)
    reviews.to_csv(BASE + "eventhub_reviews_extended.csv", index=False, encoding="utf-8-sig")
    print(f"  리뷰: {len(reviews)}건")

    # ---- 병합 (build_platform_daily.py와 동일한 방식) ----
    daily_eng = event_daily.groupby("date").agg(total_views=("views", "sum"), total_likes=("likes", "sum")).reset_index()

    cat_pivot = event_daily.pivot_table(index="date", columns="category", values="views", aggfunc="sum", fill_value=0)
    cat_pivot.columns = [f"views_{c}" for c in cat_pivot.columns]
    cat_pivot = cat_pivot.reset_index()

    daily_rev = reviews.groupby("review_date").agg(
        review_count=("review_id", "count"), avg_rating=("rating", "mean"), rating_sum=("rating", "sum"),
    ).reset_index().rename(columns={"review_date": "date"})
    daily_rev["date"] = pd.to_datetime(daily_rev["date"])

    df = catalog_daily.merge(daily_eng, on="date", how="left").merge(cat_pivot, on="date", how="left") \
                       .merge(daily_rev, on="date", how="left")

    fill0 = [c for c in df.columns if c.startswith("views_") or c in
             ("total_views", "total_likes", "review_count", "rating_sum")]
    df[fill0] = df[fill0].fillna(0)
    df["ma7_views"] = df["total_views"].rolling(7, min_periods=1).mean()
    df["ma30_views"] = df["total_views"].rolling(30, min_periods=1).mean()
    df["is_real_period"] = df["date"] >= pd.Timestamp("2026-05-01")

    roll_sum = df["rating_sum"].rolling(7, min_periods=1).sum()
    roll_cnt = df["review_count"].rolling(7, min_periods=1).sum()
    df["avg_rating_7d"] = roll_sum / roll_cnt.replace(0, np.nan)

    df.to_csv(BASE + "eventhub_platform_daily_extended.csv", index=False, encoding="utf-8-sig")
    print(f"\n확장 최종 데이터셋: {df.shape}  (기존 112일 → 이번 {len(df)}일, "
          f"{len(df)/112:.1f}배 확장)")
    print(f"기간: {df['date'].min().date()} ~ {df['date'].max().date()}")


if __name__ == "__main__":
    main()
