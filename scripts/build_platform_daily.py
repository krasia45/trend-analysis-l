# -*- coding: utf-8 -*-
"""
최종 분석 대상 '일별 시계열' 테이블을 조립한다.
소스:
  - eventhub_daily_timeseries.csv       (카탈로그 기반: active/new_events 등)
  - eventhub_event_daily_engagement.csv (시뮬레이션: 조회수/좋아요, 이벤트x일 단위)
  - eventhub_reviews_simulated.csv      (시뮬레이션: 리뷰/별점)
출력: eventhub_platform_daily.csv  (분석의 핵심 시계열 데이터셋)
"""
import numpy as np
import pandas as pd

BASE = "/home/claude/eventhub-trend-analysis/data/"

catalog = pd.read_csv(BASE + "eventhub_daily_timeseries.csv", parse_dates=["date"])
engagement = pd.read_csv(BASE + "eventhub_event_daily_engagement.csv", parse_dates=["date"])
reviews = pd.read_csv(BASE + "eventhub_reviews_simulated.csv", parse_dates=["review_date"])

# ---- 조회수/좋아요 일별 집계 (+카테고리별) ----
daily_eng = engagement.groupby("date").agg(
    total_views=("views", "sum"),
    total_likes=("likes", "sum"),
).reset_index()

cat_pivot = engagement.pivot_table(index="date", columns="category", values="views", aggfunc="sum", fill_value=0)
cat_pivot.columns = [f"views_{c}" for c in cat_pivot.columns]
cat_pivot = cat_pivot.reset_index()

merchant_pivot = engagement.pivot_table(index="date", columns="merchant_type", values="views", aggfunc="sum", fill_value=0)
merchant_pivot.columns = [f"views_{'brand' if c=='브랜드' else 'merchant'}" for c in merchant_pivot.columns]
merchant_pivot = merchant_pivot.reset_index()

# ---- 리뷰 일별 집계 ----
daily_rev = reviews.groupby("review_date").agg(
    review_count=("review_id", "count"),
    avg_rating=("rating", "mean"),
    rating_sum=("rating", "sum"),
).reset_index().rename(columns={"review_date": "date"})

sent_pivot = reviews.pivot_table(index="review_date", columns="rating_sentiment", values="review_id",
                                  aggfunc="count", fill_value=0).reset_index().rename(columns={"review_date": "date"})
for col in ["positive", "neutral", "negative"]:
    if col not in sent_pivot.columns:
        sent_pivot[col] = 0
sent_pivot = sent_pivot.rename(columns={"positive": "review_positive", "neutral": "review_neutral", "negative": "review_negative"})

# ---- 병합 ----
df = catalog.merge(daily_eng, on="date", how="left") \
            .merge(cat_pivot, on="date", how="left") \
            .merge(merchant_pivot, on="date", how="left") \
            .merge(daily_rev, on="date", how="left") \
            .merge(sent_pivot[["date", "review_positive", "review_neutral", "review_negative"]], on="date", how="left")

fill0_cols = [c for c in df.columns if c.startswith("views_") or c in
              ["total_views", "total_likes", "review_count", "review_positive", "review_neutral",
               "review_negative", "rating_sum"]]
df[fill0_cols] = df[fill0_cols].fillna(0)

df["ma7_views"] = df["total_views"].rolling(7, min_periods=1).mean()
df["like_rate"] = (df["total_likes"] / df["total_views"].replace(0, np.nan))
df["review_positive_ratio"] = df["review_positive"] / df["review_count"].replace(0, np.nan)

# 리뷰가 없는 날의 avg_rating은 NaN이 정상(관측치 부재)이므로, 별도로
# '트레일링 7일 가중평균 별점'을 리뷰 건수 기준 가중치로 계산해 결측 영향을 줄인다.
roll_rating_sum = df["rating_sum"].rolling(7, min_periods=1).sum()
roll_review_cnt = df["review_count"].rolling(7, min_periods=1).sum()
df["avg_rating_7d"] = (roll_rating_sum / roll_review_cnt.replace(0, np.nan))

out_path = BASE + "eventhub_platform_daily.csv"
df.to_csv(out_path, index=False, encoding="utf-8-sig")

print(f"최종 일별 시계열 shape: {df.shape}")
print(f"컬럼: {list(df.columns)}")
print()
print(df[["date", "active_events", "total_views", "ma7_views", "review_count", "avg_rating"]].head(8))
print("...")
print(df[["date", "active_events", "total_views", "ma7_views", "review_count", "avg_rating"]].tail(8))
print()
print("결측치 체크:")
print(df.isna().sum()[df.isna().sum() > 0])
