# -*- coding: utf-8 -*-
"""
templates/dashboard_template.html + 데이터(csv) → dashboard.html 을 조립한다.

이 스크립트를 분리해둔 이유: EventHub가 실제로 오픈해서
scripts/fetch_real_data_from_supabase.py 로 실측 데이터를 받으면,
--daily 인자만 그 파일로 바꿔서 다시 실행하면 대시보드가 자동으로
"LIVE DATA" 배지로 바뀌고 실측 데이터로 갱신된다. 즉 대시보드를 손으로
다시 만들 필요가 없다.

사용:
    # 지금 (시뮬레이션 데이터)
    python3 scripts/build_dashboard.py

    # 실서비스 오픈 후 (실측 데이터로 교체)
    python3 scripts/fetch_real_data_from_supabase.py
    python3 scripts/build_dashboard.py \\
        --daily data/eventhub_platform_daily_REAL.csv \\
        --reviews data/eventhub_reviews_REAL.csv \\
        --mode real
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BASE = str(Path(__file__).resolve().parent.parent) + "/"

CAT_KO = {"food": "푸드", "popup": "팝업", "beauty": "뷰티", "fashion": "패션",
          "delivery": "딜리버리", "living": "리빙", "tech": "테크", "stay": "스테이"}


def build_dashboard_json(daily_csv, reviews_csv):
    df = pd.read_csv(daily_csv, parse_dates=["date"])
    cat_cols = [c for c in df.columns if c.startswith("views_") and c not in ("views_brand", "views_merchant")]

    daily = []
    for _, r in df.iterrows():
        row = {
            "date": r["date"].strftime("%Y-%m-%d"),
            "weekday": r.get("weekday_ko", ""),
            "views": int(r.get("total_views", 0) or 0),
            "likes": int(r.get("total_likes", 0) or 0),
            "ma7": round(float(r.get("ma7_views", 0) or 0), 1),
            "active": int(r.get("active_events", 0) or 0),
            "reviews": int(r.get("review_count", 0) or 0),
            "rating": None if pd.isna(r.get("avg_rating")) else round(float(r["avg_rating"]), 2),
        }
        for c in cat_cols:
            key = c.replace("views_", "")
            ko = CAT_KO.get(key, key)
            row[ko] = int(r.get(c, 0) or 0)
        daily.append(row)

    categories = [CAT_KO.get(c.replace("views_", ""), c.replace("views_", "")) for c in cat_cols]

    rating_json = []
    try:
        reviews = pd.read_csv(reviews_csv)
        rating_col = "category_ko" if "category_ko" in reviews.columns else "category"
        rating_by_cat = reviews.groupby(rating_col)["rating"].agg(["mean", "count"]).round(2)
        rating_json = [{"category": k, "rating": float(v["mean"]), "count": int(v["count"])}
                        for k, v in rating_by_cat.iterrows()]
    except FileNotFoundError:
        print(f"⚠️  리뷰 파일을 찾을 수 없습니다 ({reviews_csv}) → 별점 차트는 비워둡니다.")

    return {"daily": daily, "ratingByCategory": rating_json, "categories": categories}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", default=BASE + "data/eventhub_platform_daily.csv")
    ap.add_argument("--reviews", default=BASE + "data/eventhub_reviews_simulated.csv")
    ap.add_argument("--mode", choices=["simulated", "real"], default="simulated")
    ap.add_argument("--out", default=BASE + "dashboard.html")
    args = ap.parse_args()

    data = build_dashboard_json(args.daily, args.reviews)
    meta = {
        "mode": args.mode,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "sourceNote": "Supabase 실측 데이터" if args.mode == "real" else "카탈로그 기반 시뮬레이션",
    }

    with open(BASE + "templates/dashboard_template.html", encoding="utf-8") as f:
        html = f.read()
    with open(BASE + "scripts/_vendor_chart.umd.js", encoding="utf-8") as f:
        chartjs = f.read()

    html = html.replace("__CHARTJS_VENDORED__", chartjs)
    html = html.replace("__DASHBOARD_DATA_JSON__", json.dumps(data, ensure_ascii=False))
    html = html.replace("__DASHBOARD_META_JSON__", json.dumps(meta, ensure_ascii=False))

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"dashboard.html 생성 완료 ({args.mode} 모드) → {args.out}")
    print(f"  일별 데이터 {len(data['daily'])}행, 카테고리 {len(data['categories'])}개, "
          f"별점 항목 {len(data['ratingByCategory'])}개")


if __name__ == "__main__":
    main()
