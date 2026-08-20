# -*- coding: utf-8 -*-
"""
EventHub 서비스는 2026년 8월 현재 정식 오픈 전(가동 준비 중) 상태이므로,
실제 사용자 트래픽/리뷰 데이터가 아직 존재하지 않는다.

이 스크립트는 "만약 서비스가 실제로 운영되고 있다면" 을 가정하여,
실제 이벤트 카탈로그(eventhub_events_clean.csv, 160건, 실제 카테고리·할인율·기간 값)를
기반으로 사용자 관심도(조회수/좋아요) 및 리뷰(별점/텍스트)를 통계적으로 '시뮬레이션'한다.

>>> 이 데이터는 실측(real-world observed) 데이터가 아니라,
>>> 아래에 명시한 가정(assumption) 기반의 합성(synthetic) 데이터다.
>>> REPORT.md의 '데이터 설명 / 한계점' 섹션에 이 사실과 생성 로직을 투명하게 공개한다.

시뮬레이션 가정 (근거: 국내 소비자 할인앱 일반적 이용 패턴에 대한 통상적 가정)
  1) 카테고리별 기본 관심도 가중치가 다르다 (푸드/팝업/뷰티가 상대적으로 高관심).
  2) 주말(토/일) 트래픽이 평일보다 높다 (플랫폼 공통 요일 계수).
  3) 이벤트는 '시작 직후 관심도가 가장 높고 이후 감쇠'하는 노벨티(novelty) 패턴을 보인다.
  4) 할인율이 높을수록(정률 할인 한정) 조회 유인이 커진다.
  5) 좋아요/리뷰 발생량은 조회수에 비례하되 카테고리별로 전환율이 다르다.
  6) 별점은 카테고리 기본 만족도 + 할인 매력도 + 잡음(noise)의 함수이며, 텍스트는 별점 구간에
     맞는 문장 템플릿 풀에서 카테고리 어휘를 섞어 생성한다 (10%는 의도적으로 별점-텍스트 톤을 섞어
     현실적 잡음을 반영).
"""
import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)  # 재현성을 위한 고정 시드

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVENTS_PATH = PROJECT_ROOT / "data" / "eventhub_events_clean.csv"
OUT_EVENT_DAILY = PROJECT_ROOT / "data" / "eventhub_event_daily_engagement.csv"
OUT_REVIEWS = PROJECT_ROOT / "data" / "eventhub_reviews_simulated.csv"

# ---- 가정 1: 카테고리 기본 관심도 가중치 ----
CATEGORY_WEIGHT = {
    "food": 1.30, "popup": 1.25, "beauty": 1.15, "fashion": 1.10,
    "delivery": 1.00, "living": 0.85, "tech": 0.80, "stay": 0.75,
}
# 카테고리별 좋아요 전환율 (조회수 대비)
CATEGORY_LIKE_RATE = {
    "food": 0.075, "popup": 0.070, "beauty": 0.065, "fashion": 0.055,
    "delivery": 0.050, "living": 0.045, "tech": 0.045, "stay": 0.040,
}
# 카테고리 기본 만족도(별점 베이스라인, 5점 만점)
CATEGORY_BASE_RATING = {
    "food": 4.15, "beauty": 4.05, "stay": 4.10, "popup": 3.95,
    "fashion": 3.90, "living": 3.95, "tech": 3.85, "delivery": 3.80,
}

# ---- 가정 2: 요일 계수 (0=월 ... 6=일) ----
WEEKDAY_MULT = {0: 0.90, 1: 0.85, 2: 0.90, 3: 0.95, 4: 1.15, 5: 1.35, 6: 1.25}

BASE_VIEWS = 55.0  # 이벤트 1건의 하루 기준 조회수 스케일


def novelty_decay(days_since_start: int) -> float:
    """가정 3: 시작 직후 피크, 이후 지수적으로 감쇠 (바닥 0.5배)."""
    return 0.5 + 0.85 * np.exp(-days_since_start / 4.0)


def discount_boost(discount_pct, discount_type) -> float:
    """가정 4: 정률 할인율이 높을수록 관심도 증가 (30% 기준 중립)."""
    if discount_type == "percent" and pd.notna(discount_pct):
        return float(np.clip(1.0 + (discount_pct - 30.0) / 100.0, 0.6, 1.9))
    return 1.0  # 1+1/사은품/쿠폰형은 중립값


def simulate_event_daily_views(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, ev in events.iterrows():
        d_boost = discount_boost(ev["discount_pct"], ev["discount_type"])
        cat_w = CATEGORY_WEIGHT.get(ev["category"], 1.0)
        merchant_w = 0.85 if ev["merchant_type"] == "소상공인" else 1.0  # 브랜드 인지도 프리미엄 가정
        date_range = pd.date_range(ev["period_start"], ev["period_end"], freq="D")
        for d in date_range:
            t = (d - ev["period_start"]).days
            noise = RNG.lognormal(mean=0.0, sigma=0.35)
            weekday_mult = WEEKDAY_MULT[d.dayofweek]
            views = BASE_VIEWS * cat_w * merchant_w * d_boost * novelty_decay(t) * weekday_mult * noise
            views = max(0, round(views))
            like_rate = CATEGORY_LIKE_RATE.get(ev["category"], 0.05)
            likes = int(np.round(views * like_rate * RNG.uniform(0.7, 1.3)))
            rows.append({
                "date": d, "event_id": ev["id"], "category": ev["category"],
                "category_ko": ev["category_ko"], "brand": ev["brand"],
                "merchant_type": ev["merchant_type"], "discount_pct": ev["discount_pct"],
                "discount_type": ev["discount_type"], "views": views, "likes": likes,
            })
    return pd.DataFrame(rows)


# ---------------- 리뷰 시뮬레이션 (가정 6) ----------------
POS_TEMPLATES = [
    "{brand} {noun} 진짜 만족스러웠어요, {discount} 받고 완전 이득!",
    "가격 대비 퀄리티 최고예요. {brand} 다음에도 또 이용할래요.",
    "{noun} 상태도 좋고 직원분도 친절해서 기분 좋게 다녀왔습니다.",
    "이 정도 할인이면 무조건 가야죠. 강력 추천합니다!",
    "성수동에서 이런 이벤트 찾기 힘든데 완전 만족했어요.",
]
NEU_TEMPLATES = [
    "{noun} 나쁘지 않은데 특별히 인상적이지도 않았어요.",
    "할인은 괜찮은데 대기줄이 좀 길었습니다.",
    "그냥 무난했어요. 재방문은 고민 중입니다.",
    "{brand} 처음 이용해봤는데 보통이었어요.",
]
NEG_TEMPLATES = [
    "기대했던 것보다 별로였어요. {noun} 아쉬웠습니다.",
    "재고가 이미 없어서 할인 혜택을 못 받았어요, 실망.",
    "설명이랑 실제가 달라서 불편했습니다.",
    "직원 응대가 다소 불친절했어요.",
]
CATEGORY_NOUN = {
    "fashion": "옷", "beauty": "제품", "food": "음식", "tech": "제품",
    "delivery": "배달", "stay": "숙소", "living": "제품", "popup": "공간",
}

POS_LEX = ["만족", "좋", "최고", "추천", "친절", "이득", "강력", "완전"]
NEG_LEX = ["실망", "아쉬", "불편", "불친절", "별로", "없어서", "대기줄"]


def rule_based_sentiment(text: str) -> str:
    """review_dashboard(Project C) 프로젝트의 키워드 룰 방식을 간이화해 재사용."""
    pos = sum(1 for w in POS_LEX if w in text)
    neg = sum(1 for w in NEG_LEX if w in text)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def simulate_reviews(events: pd.DataFrame, event_daily: pd.DataFrame) -> pd.DataFrame:
    total_views = event_daily.groupby("event_id")["views"].sum().to_dict()
    rows = []
    rid = 1
    for _, ev in events.iterrows():
        ev_views = total_views.get(ev["id"], 0)
        expected_reviews = max(0.3, ev_views / 380.0)  # 관심도(조회수) 대비 리뷰 전환
        n_reviews = RNG.poisson(expected_reviews)
        if n_reviews == 0:
            continue
        base_rating = CATEGORY_BASE_RATING.get(ev["category"], 3.9)
        d_boost = discount_boost(ev["discount_pct"], ev["discount_type"])
        review_window_start = ev["period_start"] + pd.Timedelta(days=1)
        review_window_end = ev["period_end"] + pd.Timedelta(days=5)
        span = max(1, (review_window_end - review_window_start).days)
        noun = CATEGORY_NOUN.get(ev["category"], "제품")

        for _ in range(n_reviews):
            offset = int(RNG.integers(0, span + 1))
            r_date = review_window_start + pd.Timedelta(days=offset)
            rating = base_rating + (d_boost - 1.0) * 1.2 + RNG.normal(0, 0.55)
            rating = int(np.clip(round(rating), 1, 5))

            tone = "pos" if rating >= 4 else ("neu" if rating == 3 else "neg")
            # 10% 확률로 톤을 한 단계 어긋나게 섞어 현실적 잡음 반영
            if RNG.random() < 0.10:
                tone = RNG.choice(["pos", "neu", "neg"])
            template_pool = {"pos": POS_TEMPLATES, "neu": NEU_TEMPLATES, "neg": NEG_TEMPLATES}[tone]
            text = RNG.choice(template_pool).format(
                brand=ev["brand"], noun=noun, discount=ev["discount_raw"]
            )
            rows.append({
                "review_id": f"r{rid:04d}", "event_id": ev["id"], "brand": ev["brand"],
                "category": ev["category"], "category_ko": ev["category_ko"],
                "merchant_type": ev["merchant_type"], "review_date": r_date.date().isoformat(),
                "rating": rating, "review_text": text,
                "rating_sentiment": "positive" if rating >= 4 else ("neutral" if rating == 3 else "negative"),
                "text_sentiment": rule_based_sentiment(text),
            })
            rid += 1
    return pd.DataFrame(rows)


def main():
    events = pd.read_csv(EVENTS_PATH, parse_dates=["period_start", "period_end"])

    event_daily = simulate_event_daily_views(events)
    event_daily.to_csv(OUT_EVENT_DAILY, index=False, encoding="utf-8-sig")
    print(f"이벤트x일 단위 관심도 레코드: {len(event_daily)}건")
    print(f"전체 기간 총 조회수: {event_daily['views'].sum():,} / 총 좋아요: {event_daily['likes'].sum():,}")

    reviews = simulate_reviews(events, event_daily)
    reviews.to_csv(OUT_REVIEWS, index=False, encoding="utf-8-sig")
    print(f"\n생성된 리뷰 수: {len(reviews)}건")
    agree = (reviews["rating_sentiment"] == reviews["text_sentiment"]).mean()
    print(f"별점 기반 감정 vs 텍스트 키워드 기반 감정 일치율: {agree:.1%}")
    print(reviews["rating"].describe())


if __name__ == "__main__":
    main()
