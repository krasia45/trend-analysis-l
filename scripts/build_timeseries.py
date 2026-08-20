# -*- coding: utf-8 -*-
"""
seed_events.json (EventHub 플랫폼의 할인 이벤트 160건, 레코드 단위)를
일별(daily) 시계열 데이터로 변환한다.

각 이벤트는 period_start ~ period_end 구간을 갖는 '진행 기간형' 데이터이므로,
날짜별로 penetrate(순회)하며 다음 지표를 집계한다:
  - active_events      : 해당 날짜에 '진행 중'인 이벤트 수
  - new_events         : 해당 날짜에 '시작'하는 이벤트 수
  - ended_events       : 해당 날짜에 '종료'하는 이벤트 수
  - avg_discount_pct   : 해당 날짜 활성 이벤트 중 정률(%) 할인들의 평균 할인율
  - active_brand       : 활성 이벤트 중 '브랜드' 유형 수
  - active_merchant    : 활성 이벤트 중 '소상공인' 유형 수
  - active_<category>  : 카테고리별 활성 이벤트 수 (8개 카테고리)
"""
import json
import re
import pandas as pd
import numpy as np

RAW_PATH = "/home/claude/eventhub-trend-analysis/data/eventhub_seed_events_raw.json"
OUT_EVENTS_CSV = "/home/claude/eventhub-trend-analysis/data/eventhub_events_clean.csv"
OUT_DAILY_CSV = "/home/claude/eventhub-trend-analysis/data/eventhub_daily_timeseries.csv"

CATEGORY_KO = {
    "fashion": "패션", "beauty": "뷰티", "food": "푸드", "tech": "테크",
    "delivery": "딜리버리", "stay": "스테이", "living": "리빙", "popup": "팝업",
}


def parse_period(period_str: str):
    m = re.findall(r"(\d{4})\.(\d{2})\.(\d{2})", period_str or "")
    if len(m) >= 2:
        s = f"{m[0][0]}-{m[0][1]}-{m[0][2]}"
        e = f"{m[1][0]}-{m[1][1]}-{m[1][2]}"
        return s, e
    if len(m) == 1:
        d = f"{m[0][0]}-{m[0][1]}-{m[0][2]}"
        return d, d
    return None, None


def parse_discount(discount_str: str):
    """'40% OFF', '최대 70% OFF' -> (40.0, 'percent') 등으로 정규화."""
    s = discount_str or ""
    pct_match = re.search(r"(\d+)\s*%", s)
    if pct_match:
        return float(pct_match.group(1)), "percent"
    if "+1" in s:
        return np.nan, "bundle"          # 1+1, 2+1 등
    if "원" in s:
        return np.nan, "amount"          # 정액 할인
    return np.nan, "other"               # 사은품/쿠폰/체험 등


def main():
    with open(RAW_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    rows = []
    for ev in raw:
        p_start, p_end = parse_period(ev.get("period", ""))
        d_pct, d_type = parse_discount(ev.get("discount", ""))
        rows.append({
            "id": ev["id"],
            "category": ev["category"],
            "category_ko": CATEGORY_KO.get(ev["category"], ev["category"]),
            "brand": ev["brand"],
            "merchant_type": ev.get("merchantType", "브랜드"),
            "title": ev.get("title", ""),
            "discount_raw": ev.get("discount", ""),
            "discount_pct": d_pct,
            "discount_type": d_type,
            "period_raw": ev.get("period", ""),
            "period_start": p_start,
            "period_end": p_end,
        })

    events = pd.DataFrame(rows)
    events["period_start"] = pd.to_datetime(events["period_start"])
    events["period_end"] = pd.to_datetime(events["period_end"])
    events["duration_days"] = (events["period_end"] - events["period_start"]).dt.days + 1

    # 결측치 체크
    missing = events.isna().sum()
    print("=== 결측치 체크 (이벤트 단위) ===")
    print(missing[missing > 0])

    # 이상치 체크: 기간이 음수이거나 비정상적으로 긴 이벤트
    odd = events[(events["duration_days"] <= 0) | (events["duration_days"] > 60)]
    print(f"\n=== 이상치 후보 (기간<=0 또는 >60일): {len(odd)}건 ===")
    if len(odd):
        print(odd[["id", "brand", "period_raw", "duration_days"]])

    events.to_csv(OUT_EVENTS_CSV, index=False, encoding="utf-8-sig")

    # ---- 일별 시계열 생성 ----
    date_min = events["period_start"].min()
    date_max = events["period_end"].max()
    date_range = pd.date_range(date_min, date_max, freq="D")
    print(f"\n분석 기간: {date_min.date()} ~ {date_max.date()}  (총 {len(date_range)}일)")

    daily_rows = []
    categories = sorted(events["category"].unique())
    for d in date_range:
        active_mask = (events["period_start"] <= d) & (events["period_end"] >= d)
        active = events[active_mask]
        new_mask = events["period_start"] == d
        end_mask = events["period_end"] == d

        pct_active = active[active["discount_type"] == "percent"]["discount_pct"]

        row = {
            "date": d,
            "active_events": int(active_mask.sum()),
            "new_events": int(new_mask.sum()),
            "ended_events": int(end_mask.sum()),
            "avg_discount_pct": pct_active.mean() if len(pct_active) else np.nan,
            "active_brand": int((active["merchant_type"] == "브랜드").sum()),
            "active_merchant": int((active["merchant_type"] == "소상공인").sum()),
        }
        for c in categories:
            row[f"active_{c}"] = int((active["category"] == c).sum())
        daily_rows.append(row)

    daily = pd.DataFrame(daily_rows)
    daily["weekday"] = daily["date"].dt.dayofweek  # 0=Mon
    daily["weekday_ko"] = daily["date"].dt.day_name().map({
        "Monday": "월", "Tuesday": "화", "Wednesday": "수", "Thursday": "목",
        "Friday": "금", "Saturday": "토", "Sunday": "일",
    })
    daily["ma7_active"] = daily["active_events"].rolling(7, min_periods=1).mean()
    daily["merchant_share"] = daily["active_merchant"] / daily["active_events"].replace(0, np.nan)

    daily.to_csv(OUT_DAILY_CSV, index=False, encoding="utf-8-sig")

    print(f"\n일별 시계열 데이터 포인트 수: {len(daily)}  (요구조건: 100개 이상 -> {'충족' if len(daily) >= 100 else '미충족'})")
    print(daily[["date", "active_events", "new_events", "avg_discount_pct"]].head(10))
    print("...")
    print(daily[["date", "active_events", "new_events", "avg_discount_pct"]].tail(5))


if __name__ == "__main__":
    main()
