# -*- coding: utf-8 -*-
"""
성수동 검색 트렌드 분석 — 시각화 + 시계열 분해(보너스A) + 베이스라인 예측(보너스B)
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path
from statsmodels.tsa.seasonal import seasonal_decompose

for f in fm.fontManager.ttflist:
    if "NanumGothic" in f.name:
        plt.rcParams["font.family"] = f.name
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMG = PROJECT_ROOT / "images"
IMG.mkdir(exist_ok=True)

ORANGE = "#FF6F00"
TEAL = "#2A8A7F"
CORAL = "#E15B3E"
PALETTE = {"성수동": ORANGE, "팝업스토어": TEAL, "할인": CORAL}
WD_ORDER = ["월", "화", "수", "목", "금", "토", "일"]

df = pd.read_csv(PROJECT_ROOT / "data" / "naver_trend_daily.csv", parse_dates=["date"])

# =========================================================
# 1) 3개 키워드 전체 추이 + 7일 이동평균
# =========================================================
fig, ax = plt.subplots(figsize=(12, 5.5))
for kw in ["성수동", "팝업스토어", "할인"]:
    ax.plot(df["date"], df[f"{kw}_ma7"], color=PALETTE[kw], linewidth=2, label=f"{kw} (7일 이동평균)")
peak_y = df["성수동_ma7"].max()
ax.axvline(pd.Timestamp("2026-05-01"), color="grey", linestyle=":", linewidth=1)
ax.annotate("5/1 최고점", xy=(pd.Timestamp("2026-05-01"), peak_y),
            xytext=(pd.Timestamp("2026-06-05"), peak_y - 2), fontsize=9, color="grey",
            arrowprops=dict(arrowstyle="->", color="grey", lw=0.8))
ax.set_title("네이버 검색어 트렌드: 성수동 · 팝업스토어 · 할인 (2025-08-25~2026-08-25)", fontsize=13, fontweight="bold")
ax.set_ylabel("상대 검색량 지수 (0~100)")
ax.legend(loc="upper right", fontsize=9)
ax.grid(alpha=0.3)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(IMG / "01_trend_overview.png")
plt.close(fig)

# =========================================================
# 2) 요일별 평균 검색량 (성수동)
# =========================================================
wd_avg = df.groupby("weekday_ko")["성수동"].mean().reindex(WD_ORDER)
fig, ax = plt.subplots(figsize=(8, 5))
colors = [ORANGE if d in ("토", "일") else "#B0BEC5" for d in WD_ORDER]
bars = ax.bar(wd_avg.index, wd_avg.values, color=colors)
for b, v in zip(bars, wd_avg.values):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.2, f"{v:.1f}", ha="center", fontsize=9)
ax.set_title("요일별 평균 '성수동' 검색량 지수", fontsize=13, fontweight="bold")
ax.set_ylabel("평균 지수")
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMG / "02_weekday_pattern.png")
plt.close(fig)

# =========================================================
# 3) 월별 평균 검색량 (계절성)
# =========================================================
monthly = df.groupby(df["date"].dt.to_period("M"))["성수동"].mean()
fig, ax = plt.subplots(figsize=(10, 5))
labels = [str(m) for m in monthly.index]
colors_m = [ORANGE if v == monthly.max() else "#B0BEC5" for v in monthly.values]
bars = ax.bar(labels, monthly.values, color=colors_m)
for b, v in zip(bars, monthly.values):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.3, f"{v:.1f}", ha="center", fontsize=8)
ax.set_title("월별 평균 '성수동' 검색량 지수 — 계절성 확인", fontsize=13, fontweight="bold")
ax.set_ylabel("월 평균 지수")
plt.xticks(rotation=45, ha="right")
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMG / "03_monthly_seasonality.png")
plt.close(fig)

# =========================================================
# 4) 3개 키워드 간 상관관계 히트맵
# =========================================================
corr = df[["성수동", "팝업스토어", "할인"]].corr()
fig, ax = plt.subplots(figsize=(6, 5.5))
im = ax.imshow(corr.values, cmap="Oranges", vmin=-1, vmax=1)
ax.set_xticks(range(3)); ax.set_xticklabels(corr.columns)
ax.set_yticks(range(3)); ax.set_yticklabels(corr.columns)
for i in range(3):
    for j in range(3):
        ax.text(j, i, f"{corr.values[i,j]:.2f}", ha="center", va="center",
                 color="white" if abs(corr.values[i, j]) > 0.5 else "black", fontsize=13, fontweight="bold")
ax.set_title("키워드 간 상관관계 (피어슨 상관계수)", fontsize=13, fontweight="bold")
fig.colorbar(im, fraction=0.046, pad=0.04)
fig.tight_layout()
fig.savefig(IMG / "04_correlation_heatmap.png")
plt.close(fig)

# =========================================================
# 5) [보너스 A] 시계열 분해 (추세/계절성/잔차)
# =========================================================
ts = df.set_index("date")["성수동"]
decomp = seasonal_decompose(ts, model="additive", period=7, extrapolate_trend="freq")
fig, axes = plt.subplots(4, 1, figsize=(11, 9), sharex=True)
axes[0].plot(ts.index, decomp.observed, color="#2C3E50"); axes[0].set_title("관측값 (Observed)")
axes[1].plot(ts.index, decomp.trend, color=ORANGE); axes[1].set_title("추세 (Trend)")
axes[2].plot(ts.index, decomp.seasonal, color=TEAL); axes[2].set_title("주간 계절성 (Seasonal, 주기=7일)")
axes[3].plot(ts.index, decomp.resid, color="#B0BEC5", marker=".", linestyle="none"); axes[3].set_title("잔차 (Residual)")
for a in axes:
    a.grid(alpha=0.3)
fig.suptitle("'성수동' 검색량 시계열 분해 (Additive, period=7)", fontsize=13, fontweight="bold", y=1.01)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(IMG / "05_decomposition.png", bbox_inches="tight")
plt.close(fig)

# =========================================================
# 6) [보너스 B] 베이스라인 예측 (Seasonal-Naive, 최근 14일 테스트)
# =========================================================
test_days = 14
test = ts.iloc[-test_days:]
pred = ts.shift(7).iloc[-test_days:]
mae = (test - pred).abs().mean()
mape = ((test - pred).abs() / test.replace(0, np.nan)).mean() * 100

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(ts.index[-45:], ts.values[-45:], color="#B0BEC5", linewidth=1.2, label="전체 실측(최근45일)")
ax.plot(test.index, test.values, color="#2C3E50", linewidth=2.2, marker="o", label="실측(테스트, 최근14일)")
ax.plot(pred.index, pred.values, color=ORANGE, linewidth=2.2, marker="x", linestyle="--", label="Seasonal-Naive 예측(전주 동요일)")
ax.axvline(test.index[0], color="grey", linestyle=":", linewidth=1)
ax.set_title(f"베이스라인 예측 vs 실측 — MAE={mae:.2f}, MAPE={mape:.1f}%", fontsize=12, fontweight="bold")
ax.set_ylabel("상대 검색량 지수")
ax.legend(loc="upper left", fontsize=9)
ax.grid(alpha=0.3)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(IMG / "06_forecast_baseline.png")
plt.close(fig)

print("=== 시각화 6종 생성 완료 ===")
print(f"[분해] 주간 계절성 진폭: {decomp.seasonal.max()-decomp.seasonal.min():.2f}")
print(f"[예측] Seasonal-Naive MAE={mae:.2f}, MAPE={mape:.1f}%")
print(f"[상관] 성수동-팝업스토어: {corr.loc['성수동','팝업스토어']:.3f}, 성수동-할인: {corr.loc['성수동','할인']:.3f}")
