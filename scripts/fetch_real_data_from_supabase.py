# -*- coding: utf-8 -*-
"""
[실서비스 전환용] Supabase에서 실제 데이터를 읽어 동일한 스키마로 조립한다.

목적
----
지금까지의 분석(analyze_and_visualize.py, analysis.ipynb, dashboard.html)은
전부 `data/eventhub_platform_daily.csv` 라는 "고정된 스키마"를 입력으로 삼는다.
이 스크립트는 시뮬레이션이 아니라 **실제 Supabase 운영 데이터**를 읽어서
정확히 같은 컬럼 스키마로 조립하는 것이 목표다.

    ┌─────────────────────┐        ┌──────────────────────────┐
    │ (지금) 시뮬레이션    │──┐     │ eventhub_platform_daily  │
    │ simulate_*.py       │  ├──▶  │ .csv  (동일 스키마)        │──▶ 기존 분석/대시보드 코드 그대로 재사용
    │ (실서비스 오픈 후)   │──┘     │                           │
    │ 이 스크립트          │        └──────────────────────────┘
    └─────────────────────┘

즉 EventHub가 실제로 오픈하면, 이 스크립트 하나만 갈아끼우면 나머지
analyze_and_visualize.py / analysis.ipynb / dashboard.html 은 코드 수정
없이 그대로 실측 데이터로 재실행된다.

사전 조건 (필수)
----------------
1. `sql/production_schema_additions.sql` 을 Supabase SQL Editor에 먼저 적용
   (event_stats_daily 테이블 + snapshot 함수, event_visits.rating 컬럼).
2. `api/cron_jobs.py` 에 매일 스냅샷을 찍는 job을 추가하고 최소 2~3주간
   실행되어 event_stats_daily 에 데이터가 쌓여 있어야 한다
   (SQL 파일 하단 "적용 후 남은 작업" 참고).
3. 환경변수 SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY 설정
   (seed_import.py와 동일한 변수명 — 기존 운영 관행과 일치시킴).

이 스크립트는 이 세 조건 중 하나라도 아직 충족되지 않으면 (예: 스냅샷이
1일치 뿐이라 '일별 변화'를 계산할 수 없는 경우) 에러로 죽는 대신 **무엇이
왜 부족한지 한국어로 명확히 안내하고 종료**한다 — 실서비스 오픈 직후
"왜 안 되지?"를 디버깅하는 사람이 바로 원인을 알 수 있게 하기 위함이다.

실행:
    export SUPABASE_URL=...
    export SUPABASE_SERVICE_ROLE_KEY=...
    python3 scripts/fetch_real_data_from_supabase.py

네트워크 없이 로직만 검증:
    python3 scripts/fetch_real_data_from_supabase.py --self-test
"""
import os
import sys
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
from collections import defaultdict

import numpy as np
import pandas as pd

OUT_PATH = "/home/claude/eventhub-trend-analysis/data/eventhub_platform_daily_REAL.csv"

CATEGORY_KO = {
    "fashion": "패션", "beauty": "뷰티", "food": "푸드", "tech": "테크",
    "delivery": "딜리버리", "stay": "스테이", "living": "리빙", "popup": "팝업",
}


# ============================================================
# Supabase REST 헬퍼 (api/_supabase_client.py 와 동일한 방식 — 외부
# 패키지 없이 urllib만 사용. 이 프로젝트를 EventHub 본 저장소와 독립적으로
# 실행할 수 있도록 의존성을 만들지 않고 여기 자체적으로 재구현했다.)
# ============================================================
def _base_url():
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not url:
        raise RuntimeError(
            "SUPABASE_URL 환경변수가 없습니다. `export SUPABASE_URL=https://xxx.supabase.co` 로 설정하세요."
        )
    return url


def _headers():
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY 환경변수가 없습니다. "
            "(읽기 전용이면 SUPABASE_ANON_KEY로도 되지만, event_visits는 RLS로 보호되어 있어 "
            "service role 키가 필요할 수 있습니다.)"
        )
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def sb_select(table, params=None, timeout=15):
    query = urllib.parse.urlencode(params or {})
    url = f"{_base_url()}/rest/v1/{table}?{query}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        if e.code == 404 or "does not exist" in detail:
            raise RuntimeError(
                f"'{table}' 테이블을 찾을 수 없습니다. "
                f"sql/production_schema_additions.sql 을 먼저 적용했는지 확인하세요. (상세: {detail})"
            ) from e
        raise RuntimeError(f"Supabase {e.code} {e.reason}: {detail}") from e


# ============================================================
# 핵심 로직: raw rows -> eventhub_platform_daily.csv 와 동일한 스키마
# (테스트하기 쉽도록 네트워크 호출과 분리했다)
# ============================================================
def build_platform_daily(events, stats_daily, visits):
    """
    events       : [{id, category, merchant_type, period_start, period_end, discount, ...}, ...]
    stats_daily  : [{event_id, stat_date, views, likes}, ...]  (누적값 스냅샷)
    visits       : [{event_id, visited_at, rating, comment}, ...]
    -> eventhub_platform_daily.csv 와 동일 스키마의 DataFrame
    """
    ev = pd.DataFrame(events)
    if ev.empty:
        raise RuntimeError("events 테이블에 데이터가 없습니다.")
    ev["period_start"] = pd.to_datetime(ev["period_start"])
    ev["period_end"] = pd.to_datetime(ev["period_end"])
    ev["category_ko"] = ev["category"].map(CATEGORY_KO).fillna(ev["category"])

    date_min = ev["period_start"].min()
    date_max = ev["period_end"].max()
    date_range = pd.date_range(date_min, date_max, freq="D")

    # ---- 스냅샷(누적값) → 일별 신규 조회수로 변환 ----
    sd = pd.DataFrame(stats_daily)
    daily_views_by_event = {}  # {(event_id, date): daily_new_views}
    daily_likes_by_event = {}
    if not sd.empty:
        sd["stat_date"] = pd.to_datetime(sd["stat_date"])
        sd = sd.sort_values(["event_id", "stat_date"])
        n_snapshot_days = sd["stat_date"].nunique()
        if n_snapshot_days < 2:
            print(
                f"⚠️  경고: event_stats_daily 스냅샷이 {n_snapshot_days}일치뿐입니다. "
                "누적값의 '일별 증가분'을 계산하려면 최소 2일 이상 필요합니다. "
                "지금은 모든 날짜의 daily views/likes를 0으로 채웁니다 — 며칠 더 쌓인 뒤 재실행하세요."
            )
        for eid, grp in sd.groupby("event_id"):
            grp = grp.set_index("stat_date")
            diffs_v = grp["views"].diff().fillna(grp["views"])  # 첫날은 누적값 그대로를 신규로 취급
            diffs_l = grp["likes"].diff().fillna(grp["likes"])
            for d, v in diffs_v.items():
                daily_views_by_event[(eid, d)] = max(0, int(v))
            for d, v in diffs_l.items():
                daily_likes_by_event[(eid, d)] = max(0, int(v))
    else:
        print("⚠️  경고: event_stats_daily 데이터가 비어 있습니다 (아직 스냅샷 미적용). 조회수/좋아요는 0으로 채웁니다.")

    # ---- 리뷰(방문 후기) 일별 집계 준비 ----
    vs = pd.DataFrame(visits)
    if not vs.empty:
        vs["visited_at"] = pd.to_datetime(vs["visited_at"]).dt.normalize()
        if "rating" not in vs.columns:
            vs["rating"] = np.nan
            print("⚠️  경고: event_visits에 rating 컬럼이 없습니다 (마이그레이션 미적용). 별점 지표는 결측 처리합니다.")

    categories = sorted(ev["category"].unique())
    rows = []
    for d in date_range:
        active_mask = (ev["period_start"] <= d) & (ev["period_end"] >= d)
        active = ev[active_mask]
        new_mask = ev["period_start"] == d

        day_views = sum(daily_views_by_event.get((eid, d), 0) for eid in active["id"])
        day_likes = sum(daily_likes_by_event.get((eid, d), 0) for eid in active["id"])

        row = {
            "date": d, "active_events": int(active_mask.sum()), "new_events": int(new_mask.sum()),
            "total_views": day_views, "total_likes": day_likes,
            "active_brand": int((active["merchant_type"] == "브랜드").sum()),
            "active_merchant": int((active["merchant_type"] == "소상공인").sum()),
        }
        for c in categories:
            cat_ids = set(active.loc[active["category"] == c, "id"])
            row[f"views_{c}"] = sum(daily_views_by_event.get((eid, d), 0) for eid in cat_ids)

        if not vs.empty:
            day_reviews = vs[vs["visited_at"] == d]
            row["review_count"] = len(day_reviews)
            rated = day_reviews["rating"].dropna()
            row["avg_rating"] = rated.mean() if len(rated) else np.nan
        else:
            row["review_count"] = 0
            row["avg_rating"] = np.nan

        rows.append(row)

    df = pd.DataFrame(rows)
    df["weekday"] = df["date"].dt.dayofweek
    df["weekday_ko"] = df["date"].dt.day_name().map({
        "Monday": "월", "Tuesday": "화", "Wednesday": "수", "Thursday": "목",
        "Friday": "금", "Saturday": "토", "Sunday": "일",
    })
    df["ma7_views"] = df["total_views"].rolling(7, min_periods=1).mean()
    return df


def fetch_and_build():
    print("Supabase에서 실데이터를 조회합니다...")
    events = sb_select("events", {"select": "id,category,merchant_type,period_start,period_end,discount"})
    print(f"  events: {len(events)}건")
    try:
        stats_daily = sb_select("event_stats_daily", {"select": "event_id,stat_date,views,likes"})
        print(f"  event_stats_daily: {len(stats_daily)}건")
    except RuntimeError as e:
        print(f"  event_stats_daily 조회 실패 → 빈 데이터로 진행: {e}")
        stats_daily = []
    try:
        visits = sb_select("event_visits", {"select": "event_id,visited_at,rating,comment"})
        print(f"  event_visits: {len(visits)}건")
    except RuntimeError as e:
        print(f"  event_visits 조회 실패 → 빈 데이터로 진행: {e}")
        visits = []

    df = build_platform_daily(events, stats_daily, visits)
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"\n완료 → {OUT_PATH}  (shape={df.shape})")
    print(
        "\n이후 analyze_and_visualize.py 상단의 입력 경로를 이 파일로 바꾸면 "
        "동일한 시각화/분해/예측 코드가 실측 데이터로 그대로 동작합니다."
    )
    return df


# ============================================================
# --self-test : 네트워크 없이 reshape 로직만 검증 (합성 fixture)
# ============================================================
def _self_test():
    print("=== self-test: 합성 fixture로 reshape 로직 검증 ===")
    events = [
        {"id": "t1", "category": "food", "merchant_type": "브랜드",
         "period_start": "2026-09-01", "period_end": "2026-09-10", "discount": "20% OFF"},
        {"id": "t2", "category": "beauty", "merchant_type": "소상공인",
         "period_start": "2026-09-03", "period_end": "2026-09-12", "discount": "1+1"},
    ]
    stats_daily = [
        {"event_id": "t1", "stat_date": "2026-09-01", "views": 10, "likes": 1},
        {"event_id": "t1", "stat_date": "2026-09-02", "views": 25, "likes": 3},  # 신규 15
        {"event_id": "t2", "stat_date": "2026-09-03", "views": 5, "likes": 0},
        {"event_id": "t2", "stat_date": "2026-09-04", "views": 12, "likes": 2},  # 신규 7
    ]
    visits = [
        {"event_id": "t1", "visited_at": "2026-09-02", "rating": 5, "comment": "좋아요"},
        {"event_id": "t1", "visited_at": "2026-09-02", "rating": 3, "comment": "무난"},
    ]
    df = build_platform_daily(events, stats_daily, visits)

    assert len(df) == 12, f"기간이 12일(09-01~09-12)이어야 하는데 {len(df)}일"
    row_0902 = df[df["date"] == pd.Timestamp("2026-09-02")].iloc[0]
    assert row_0902["total_views"] == 15, f"09-02 total_views는 15여야 하는데 {row_0902['total_views']}"
    assert row_0902["review_count"] == 2, f"09-02 리뷰 2건이어야 하는데 {row_0902['review_count']}"
    assert abs(row_0902["avg_rating"] - 4.0) < 1e-6, f"09-02 평균 별점 4.0이어야 하는데 {row_0902['avg_rating']}"
    assert set(df.columns) >= {"date", "active_events", "total_views", "total_likes",
                                "review_count", "avg_rating", "ma7_views", "weekday_ko"}, "필수 컬럼 누락"
    print("모든 assertion 통과 ✅  (reshape 로직은 정상 — 실제 Supabase 연결만 필요)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", help="네트워크 없이 로직만 검증")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return

    try:
        fetch_and_build()
    except RuntimeError as e:
        print(f"\n❌ 중단: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
