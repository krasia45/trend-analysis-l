# -*- coding: utf-8 -*-
"""
EventHub 일별 관심도(조회수) 시계열 분석 + 시각화 생성 + 시계열 분해 + 베이스라인 예측.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from statsmodels.tsa.seasonal import seasonal_decompose

# ---- 한글 폰트 설정 ----
for f in fm.fontManager.ttflist:
    if "NanumGothic" in f.name:
        plt.rcParams["font.family"] = f.name
        break
else:
    plt.rcParams["font.family"] = "Noto Sans CJK KR"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130

BASE = "/home/claude/eventhub-trend-analysis/"
IMG = BASE + "images/"

ORANGE = "#FF6F00"  # EventHub 브랜드 컬러
PALETTE = ["#FF6F00", "#2C3E50", "#F4A261", "#457B9D", "#E76F51", "#2A9D8F", "#8D5B4C", "#6D6875"]

df = pd.read_csv(BASE + "data/eventhub_platform_daily.csv", parse_dates=["date"])
reviews = pd.read_csv(BASE + "data/eventhub_reviews_simulated.csv")
eng = pd.read_csv(BASE + "data/eventhub_event_daily_engagement.csv", parse_dates=["date"])
events = pd.read_csv(BASE + "data/eventhub_events_clean.csv", parse_dates=["period_start", "period_end"])

WD_ORDER = ["월", "화", "수", "목", "금", "토", "일"]
CAT_COLS = [c for c in df.columns if c.startswith("views_") and c not in ("views_brand", "views_merchant")]
CAT_KO = {"views_food": "푸드", "views_popup": "팝업", "views_beauty": "뷰티", "views_fashion": "패션",
          "views_delivery": "딜리버리", "views_living": "리빙", "views_tech": "테크", "views_stay": "스테이"}

# =========================================================
# 1) 일별 조회수 추이 + 7일 이동평균
# =========================================================
fig, ax = plt.subplots(figsize=(11, 5))
ax.bar(df["date"], df["total_views"], color="#FFD9A8", width=0.9, label="일별 조회수")
ax.plot(df["date"], df["ma7_views"], color=ORANGE, linewidth=2.5, label="7일 이동평균")
ax.set_title("EventHub 플랫폼 일별 조회수 추이 (2026-05-01 ~ 2026-08-20)", fontsize=13, fontweight="bold")
ax.set_ylabel("조회수")
ax.legend(loc="upper right")
ax.grid(axis="y", alpha=0.3)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(IMG + "01_daily_views_trend.png")
plt.close(fig)

# =========================================================
# 2) 요일별 평균 조회수 (주말 효과)
# =========================================================
wd_avg = df.groupby("weekday_ko")["total_views"].mean().reindex(WD_ORDER)
fig, ax = plt.subplots(figsize=(8, 5))
colors = [ORANGE if d in ("토", "일") else "#B0BEC5" for d in WD_ORDER]
bars = ax.bar(wd_avg.index, wd_avg.values, color=colors)
for b, v in zip(bars, wd_avg.values):
    ax.text(b.get_x() + b.get_width() / 2, v + 15, f"{v:,.0f}", ha="center", fontsize=9)
ax.set_title("요일별 평균 조회수 — 주말이 평일 대비 1.37배 높음", fontsize=13, fontweight="bold")
ax.set_ylabel("평균 조회수")
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMG + "02_weekday_pattern.png")
plt.close(fig)

# =========================================================
# 3) 카테고리별 조회수 점유율
# =========================================================
cat_sum = df[CAT_COLS].sum().sort_values(ascending=False)
cat_sum.index = [CAT_KO[c] for c in cat_sum.index]
fig, ax = plt.subplots(figsize=(9, 5))
bars = ax.barh(cat_sum.index[::-1], cat_sum.values[::-1], color=PALETTE[:len(cat_sum)][::-1])
total = cat_sum.sum()
for b, v in zip(bars, cat_sum.values[::-1]):
    ax.text(v + 200, b.get_y() + b.get_height() / 2, f"{v/total:.1%}", va="center", fontsize=9)
ax.set_title("카테고리별 누적 조회수 점유율 (전체 기간)", fontsize=13, fontweight="bold")
ax.set_xlabel("누적 조회수")
fig.tight_layout()
fig.savefig(IMG + "03_category_share.png")
plt.close(fig)

# =========================================================
# 4) 최근 4주 vs 이전 4주 카테고리별 증감률 (트렌딩 탐지)
# =========================================================
df_sorted = df.sort_values("date")
last4 = df_sorted.tail(28)[CAT_COLS].sum()
prev4 = df_sorted.iloc[-56:-28][CAT_COLS].sum()
change = ((last4 - prev4) / prev4 * 100).sort_values()
change.index = [CAT_KO[c] for c in change.index]
fig, ax = plt.subplots(figsize=(9, 5))
colors = ["#2A9D8F" if v >= 0 else "#E76F51" for v in change.values]
bars = ax.barh(change.index, change.values, color=colors)
for b, v in zip(bars, change.values):
    ax.text(v + (2 if v >= 0 else -2), b.get_y() + b.get_height() / 2, f"{v:+.0f}%",
            va="center", ha="left" if v >= 0 else "right", fontsize=9)
ax.axvline(0, color="black", linewidth=0.8)
ax.set_title("카테고리별 조회수 증감률 (최근 4주 vs 이전 4주)", fontsize=13, fontweight="bold")
ax.set_xlabel("증감률 (%)")
fig.tight_layout()
fig.savefig(IMG + "04_category_trending.png")
plt.close(fig)

# =========================================================
# 5) 이벤트 시작 후 경과일별 관심도 감쇠 (노벨티 효과)
# =========================================================
eng2 = eng.merge(events[["id", "period_start"]], left_on="event_id", right_on="id", how="left")
eng2["days_since_start"] = (eng2["date"] - eng2["period_start"]).dt.days
decay = eng2[eng2.days_since_start.between(0, 14)].groupby("days_since_start")["views"].mean()
fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(decay.index, decay.values, marker="o", color=ORANGE, linewidth=2.5)
ax.fill_between(decay.index, decay.values, alpha=0.15, color=ORANGE)
ax.set_title("이벤트 시작 후 경과일별 평균 조회수 (노벨티 감쇠 패턴)", fontsize=13, fontweight="bold")
ax.set_xlabel("이벤트 시작 후 경과일")
ax.set_ylabel("이벤트 1건당 평균 조회수")
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(IMG + "05_novelty_decay.png")
plt.close(fig)

# =========================================================
# 6) 카테고리별 평균 별점
# =========================================================
rating_by_cat = reviews.groupby("category_ko")["rating"].agg(["mean", "count"]).sort_values("mean", ascending=False)
fig, ax = plt.subplots(figsize=(9, 5))
bars = ax.bar(rating_by_cat.index, rating_by_cat["mean"], color=PALETTE[:len(rating_by_cat)])
for b, (m, c) in zip(bars, zip(rating_by_cat["mean"], rating_by_cat["count"])):
    ax.text(b.get_x() + b.get_width() / 2, m + 0.05, f"{m:.2f}\n(n={int(c)})", ha="center", fontsize=8)
ax.set_ylim(0, 5.5)
ax.axhline(reviews["rating"].mean(), color="grey", linestyle="--", linewidth=1, label=f"전체 평균 {reviews['rating'].mean():.2f}")
ax.set_title("카테고리별 평균 리뷰 별점 (시뮬레이션)", fontsize=13, fontweight="bold")
ax.set_ylabel("평균 별점 (5점 만점)")
ax.legend()
fig.tight_layout()
fig.savefig(IMG + "06_rating_by_category.png")
plt.close(fig)

# =========================================================
# 7) 시계열 분해 (보너스 A: STL/seasonal_decompose, 주기=7일)
# =========================================================
ts = df.set_index("date")["total_views"]
decomp = seasonal_decompose(ts, model="additive", period=7, extrapolate_trend="freq")
fig, axes = plt.subplots(4, 1, figsize=(11, 9), sharex=True)
axes[0].plot(ts.index, decomp.observed, color="#2C3E50"); axes[0].set_title("관측값 (Observed)")
axes[1].plot(ts.index, decomp.trend, color=ORANGE); axes[1].set_title("추세 (Trend)")
axes[2].plot(ts.index, decomp.seasonal, color="#2A9D8F"); axes[2].set_title("주간 계절성 (Seasonal, 주기=7일)")
axes[3].plot(ts.index, decomp.resid, color="#B0BEC5", marker=".", linestyle="none"); axes[3].set_title("잔차 (Residual)")
for a in axes:
    a.grid(alpha=0.3)
fig.suptitle("일별 조회수 시계열 분해 (Additive, period=7)", fontsize=13, fontweight="bold", y=1.01)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(IMG + "07_decomposition.png", bbox_inches="tight")
plt.close(fig)

seasonal_amp = decomp.seasonal.max() - decomp.seasonal.min()
resid_std = decomp.resid.std()

# =========================================================
# 8) 베이스라인 예측 (보너스 B: 7일 전 값을 그대로 쓰는 Seasonal-Naive)
# =========================================================
test_days = 14
train = ts.iloc[:-test_days]
test = ts.iloc[-test_days:]
pred = ts.shift(7).iloc[-test_days:]  # 지난주 같은 요일 값으로 예측

mae = (test - pred).abs().mean()
mape = ((test - pred).abs() / test.replace(0, np.nan)).mean() * 100
naive_mae = (test - test.shift(1).fillna(train.iloc[-1])).abs().mean()  # 비교용: 전일값 예측

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(ts.index, ts.values, color="#B0BEC5", linewidth=1.2, label="전체 실측")
ax.plot(test.index, test.values, color="#2C3E50", linewidth=2.2, marker="o", label="실측 (테스트 구간, 최근 14일)")
ax.plot(pred.index, pred.values, color=ORANGE, linewidth=2.2, marker="x", linestyle="--",
        label="베이스라인 예측 (Seasonal-Naive, 전주 동요일값)")
ax.axvline(test.index[0], color="grey", linestyle=":", linewidth=1)
ax.set_title(f"베이스라인(Seasonal-Naive) 예측 vs 실측  —  MAE={mae:.1f}, MAPE={mape:.1f}%", fontsize=12, fontweight="bold")
ax.set_ylabel("조회수")
ax.legend(loc="upper left", fontsize=9)
ax.grid(alpha=0.3)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(IMG + "08_forecast_baseline.png")
plt.close(fig)

print("=== 시각화 8종 생성 완료 (images/) ===")
print(f"\n[분해] 주간 계절성 진폭(최대-최소): {seasonal_amp:.1f}, 잔차 표준편차: {resid_std:.1f}")
print(f"[예측] Seasonal-Naive(전주 동요일) MAE={mae:.2f}, MAPE={mape:.2f}%")
print(f"[예측] 비교 baseline(전일값) MAE={naive_mae:.2f}  -> Seasonal-Naive가 {'더 나음' if mae<naive_mae else '더 나쁨'}")
