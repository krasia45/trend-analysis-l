# -*- coding: utf-8 -*-
"""
NAVER Search Trend API 응답(JSON)을 정제된 시계열 CSV로 변환한다.

원본 데이터:
  - 출처: NAVER API HUB - Search Trend API (POST /search-trend/v1/search)
  - 수집일: 2026-08-25
  - 기간: 2025-08-25 ~ 2026-08-25 (365일)
  - 키워드: 성수동 / 팝업스토어 / 할인 (3개 그룹, 상대 검색량 지수 0~100)
  - 값(ratio)의 의미: 조회 구간 내 최댓값을 100으로 둔 상대 지수. 실제 검색 "건수"가
    아니라 "그 기간 안에서 상대적으로 얼마나 많이 검색됐는지"를 나타낸다.
"""
import json
from pathlib import Path
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = PROJECT_ROOT / "data" / "naver_search_trend_raw.json"
OUT_WIDE_CSV = PROJECT_ROOT / "data" / "naver_trend_daily.csv"


def main():
    with open(RAW_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    print(f"수집 기간: {raw['startDate']} ~ {raw['endDate']} (timeUnit={raw['timeUnit']})")
    print(f"키워드 그룹: {[r['title'] for r in raw['results']]}")

    # ---- 롱 포맷 -> 와이드 포맷 (날짜 x 키워드) ----
    frames = []
    for group in raw["results"]:
        df = pd.DataFrame(group["data"])
        df["date"] = pd.to_datetime(df["period"])
        df = df.rename(columns={"ratio": group["title"]})[["date", group["title"]]]
        frames.append(df.set_index("date"))

    wide = pd.concat(frames, axis=1).reset_index()
    wide = wide.sort_values("date").reset_index(drop=True)

    # ---- 데이터 기본 정보 ----
    print(f"\n총 일수: {len(wide)}")
    print(f"컬럼: {list(wide.columns)}")

    # ---- 결측치 확인 ----
    missing = wide.isna().sum()
    print(f"\n결측치:\n{missing[missing > 0] if missing.sum() else '없음'}")

    # 날짜 연속성 확인 (누락된 날짜가 있는지)
    full_range = pd.date_range(wide["date"].min(), wide["date"].max(), freq="D")
    missing_dates = set(full_range) - set(wide["date"])
    print(f"날짜 공백: {len(missing_dates)}일 {'(없음, 완전 연속)' if not missing_dates else sorted(missing_dates)[:5]}")

    # ---- 이상치 확인 (IQR 기준, 참고용 — 제거하지 않고 기록만) ----
    print("\n이상치 후보 (IQR 1.5배 기준, 키워드별):")
    for col in ["성수동", "팝업스토어", "할인"]:
        q1, q3 = wide[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outliers = wide[(wide[col] < lo) | (wide[col] > hi)]
        print(f"  {col}: {len(outliers)}건 (정상 범위 밖 급등/급락 — 아래 분석에서 그대로 유지, "
              f"할인 이벤트처럼 실제 사건을 반영할 가능성이 높아 제거하지 않음)")

    # ---- 파생 컬럼 ----
    wide["weekday"] = wide["date"].dt.dayofweek  # 0=월
    wide["weekday_ko"] = wide["date"].dt.day_name().map({
        "Monday": "월", "Tuesday": "화", "Wednesday": "수", "Thursday": "목",
        "Friday": "금", "Saturday": "토", "Sunday": "일",
    })
    wide["month"] = wide["date"].dt.month

    for col in ["성수동", "팝업스토어", "할인"]:
        wide[f"{col}_ma7"] = wide[col].rolling(7, min_periods=1).mean()
        wide[f"{col}_pct_change"] = wide[col].pct_change() * 100

    wide.to_csv(OUT_WIDE_CSV, index=False, encoding="utf-8-sig")
    print(f"\n저장 완료: {OUT_WIDE_CSV} (shape={wide.shape})")


if __name__ == "__main__":
    main()
