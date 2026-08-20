# EventHub 관심도 인텔리전스 — 일별 트렌드 분석

> **[AI 데이터 분석] 데이터 기반 트렌드 분석** 미션 결과물
> "EventHub가 실제로 운영되고 있다면, 사람들은 지금 무엇에 관심이 있을까?"를
> 실제 이벤트 카탈로그 + 시뮬레이션 관심도 데이터로 분석합니다.

📄 **분석 리포트**: [`REPORT.md`](./REPORT.md)
📓 **분석 코드(노트북, 실행결과 포함)**: [`analysis.ipynb`](./analysis.ipynb)
🖥️ **인터랙티브 대시보드**: [`dashboard.html`](./dashboard.html) — 스크린샷: [`docs/DASHBOARD_SCREENSHOTS.md`](./docs/DASHBOARD_SCREENSHOTS.md)
🛠️ **실서비스 전환 준비물**: [`sql/production_schema_additions.sql`](./sql/production_schema_additions.sql) · [`scripts/fetch_real_data_from_supabase.py`](./scripts/fetch_real_data_from_supabase.py)

---

## 0. 먼저 답하는 세 가지 질문

**Q1. 과제 요구사항 전부와 보너스 과제 전부를 만족하나요?**
네. §9 체크리스트에 항목별로 정리했습니다. 필수 요구사항(데이터 100개 이상, 질문 3개
이상, 정제, 기법 2개 이상, 시각화 2개 이상, 인사이트 3개 이상, REPORT.md, 코드,
재현성, AI 사용 로그) 전부와 보너스 두 가지(서비스화, 시계열 심화) 모두 충족합니다.
GitHub 저장소만 예외인데, 이 저장소를 실제로 어느 계정에 올릴지는 제출자(당신)의
선택이라 로컬 git 커밋까지만 준비해뒀습니다 (§10 참고).

**Q2. EventHub를 실제로 서비스 운영한다고 했을 때도 작동하나요?**
**부분적으로 네, 그리고 그 격차를 메우는 작업까지 해뒀습니다.** 정직하게 말하면:
- 지금 이 리포트의 조회수·좋아요·리뷰는 **시뮬레이션**입니다 (EventHub가 아직 오픈 전이라
  실측 데이터 자체가 없습니다).
- 실제 EventHub Supabase 스키마를 조사해보니, `event_stats` 테이블은 조회수/좋아요의
  **누적 총합**만 저장하고 날짜별 기록이 없어서, 지금 당장 실측 데이터를 넣어도 "일별
  추이"를 만들 수 없는 구조였습니다. 리뷰도 별점 없이 자유 텍스트(`event_visits.comment`)
  만 존재합니다.
- 그래서 **이 격차를 메우는 추가 스키마(`sql/production_schema_additions.sql`)와 실데이터
  어댑터(`scripts/fetch_real_data_from_supabase.py`)를 함께 만들었습니다.** 이 두 개를
  적용하면, 서비스 오픈 후 몇 주 뒤 이 분석 파이프라인의 **다른 코드는 한 줄도 안 고치고**
  실측 데이터로 그대로 재실행됩니다. §5에서 이 부분을 자세히 설명합니다.

**Q3. 더 고도화한 부분이 있나요?**
네, 아래가 이번에 추가/개선한 것들입니다:
1. (신규) **데이터 폭 확장** — "1년간 운영했다면" 시나리오. 실제 160건은 그대로 두고,
   그 이전 253일을 실제 데이터의 경험적 분포로 통계적 백필해 401건·365일로 확장 (§11)
2. (신규) 실서비스 전환 경로 — SQL 마이그레이션 + Supabase 어댑터 + self-test (§5)
3. (개선) 대시보드를 완전히 오프라인 동작하게 변경 — Chart.js를 CDN이 아니라 파일에
   직접 내장(vendoring), 템플릿/데이터 분리로 재생성 자동화 (§4)
4. (신규) 대시보드 3가지 필터 시나리오를 실제 헤드리스 브라우저로 렌더링한 스크린샷 증빙
5. (신규) 이전 팀 프로젝트(`review_dashboard`, Project C)의 리뷰 감정분석 방식을 이번
   분석에 재사용 — 별점 기반 감정과 키워드 기반 감정을 이중 산출해 교차 검증
6. (버그 수정) 전체 스크립트(10개)가 `/home/claude/...` 절대경로를 하드코딩하고 있어서
   **다른 경로에 클론하면 조용히 원래 경로에 파일을 쓰거나 실패하는 재현성 버그**를
   발견해 고쳤다. `Path(__file__).resolve().parent.parent` 기준 상대경로로 전환하고,
   실제로 완전히 다른 디렉터리에 복사해 전체 9단계 파이프라인 + 노트북 실행까지
   처음부터 재현되는 것을 검증했다 (§8 참고).

---

## 1. 왜 이런 방식으로 접근했는가

EventHub는 2026년 8월 현재 **정식 오픈 전(가동 준비 중)** 상태라 실측 트래픽이 없습니다.
그렇다고 아무 시계열 데이터(주가, 날씨 등)를 가져와 분석하면 "EventHub와 무관한 과제"가
되어버립니다. 그래서:

1. EventHub의 **실제 이벤트 카탈로그**(`github.com/krasia45/eventhub` 의 `seed_events.json`,
   160건 — 실제 카테고리/브랜드/할인율/진행기간 값)를 데이터의 뼈대로 삼고,
2. "만약 서비스가 실제로 운영되고 있다면" 이라는 가정 하에, 그 카탈로그를 사람들이 보고
   좋아요를 누르고 리뷰를 남기는 과정을 **통계적으로 시뮬레이션**했습니다.
3. 이전에 만들었던 팀 프로젝트 `review_dashboard`(리뷰 감정분석 대시보드)의 접근 방식
   (별점 vs 텍스트 키워드 기반 감정을 이중 산출해 교차 검증)을 리뷰 시뮬레이션에 재사용해,
   "리뷰"라는 데이터 유형도 분석에 포함시켰습니다.

이렇게 하면 EventHub의 실제 사업 모델("지금 사람들이 무엇에 관심 있는지 데이터로 짚어
기업/소상공인에게 인사이트로 제공")을 데이터로 미리 시연해볼 수 있습니다. 이 접근의
정직성을 지키기 위해, **어디까지가 실제 데이터이고 어디부터가 시뮬레이션인지**를
REPORT.md·README·대시보드 세 곳 모두에 명시했습니다.

---

## 2. 전체 파이프라인 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│  A. 실제 데이터                                                    │
│  eventhub_seed_events_raw.json (160건, EventHub 실제 카탈로그)      │
└───────────────────────────┬───────────────────────────────────────┘
                             ▼
                  scripts/build_timeseries.py
                  (레코드 → 일별 시계열, 결측치/이상치 점검)
                             ▼
              data/eventhub_daily_timeseries.csv  (112일)
                             │
                             ▼
        scripts/simulate_engagement_and_reviews.py
        (B. 시뮬레이션: 카테고리 가중치·요일 계수·노벨티 감쇠·
         할인율 효과 기반 조회수/좋아요/리뷰 생성, 시드 고정)
                             │
        ┌────────────────────┴────────────────────┐
        ▼                                          ▼
data/..._event_daily_engagement.csv       data/..._reviews_simulated.csv
        └────────────────────┬────────────────────┘
                             ▼
              scripts/build_platform_daily.py
              (병합 + 7일 가중평균 별점 등 지표 계산)
                             ▼
           data/eventhub_platform_daily.csv  ★ 최종 분석 데이터셋
                             │
         ┌───────────────────┼───────────────────────┐
         ▼                   ▼                        ▼
scripts/analyze_and_    scripts/make_notebook.py   scripts/build_dashboard.py
visualize.py            → analysis.ipynb              (templates/dashboard_
→ images/*.png 8종       (nbconvert --execute로       template.html + Chart.js
  + 시계열분해 + 예측       결과 내장)                   vendoring)
                                                          ▼
                                                    dashboard.html
                                                    (완전 오프라인 동작)

─────────────────────────────────────────────────────────────────────
C. 실서비스 전환 경로 (오픈 후, 위 B를 대체)
─────────────────────────────────────────────────────────────────────
sql/production_schema_additions.sql  (Supabase에 1회 적용)
             │
             ▼
scripts/fetch_real_data_from_supabase.py
(실측 events/event_stats_daily/event_visits → 동일 스키마로 reshape)
             │
             ▼
data/eventhub_platform_daily_REAL.csv   ← 위 "최종 분석 데이터셋"과 완전히 동일한 컬럼
             │
             ▼
   (analyze_and_visualize.py / make_notebook.py / build_dashboard.py 를
    입력 경로만 바꿔서 재실행 → 코드 수정 없이 실측 데이터로 전체 리포트 재생성)
```

**설계 원칙**: B(시뮬레이션)와 C(실데이터)가 **동일한 출력 스키마**
(`eventhub_platform_daily.csv`)를 만들어내도록 설계했습니다. 그래서 데이터 소스가
바뀌어도 그 뒤(시각화·노트북·대시보드) 코드는 전혀 손댈 필요가 없습니다 — 이것이
"실제로 서비스 운영했을 때도 작동하는가"라는 질문에 대한 구체적인 답입니다.

---

## 3. 시뮬레이션 방법론 (요약 — 전체 가정은 REPORT.md §3, 코드 주석 참고)

`scripts/simulate_engagement_and_reviews.py` 의 핵심 가정:

| 요소 | 가정 |
|---|---|
| 카테고리 가중치 | 푸드(1.30) > 팝업(1.25) > 뷰티(1.15) > 패션(1.10) > 딜리버리(1.00) > 리빙(0.85) > 테크(0.80) > 스테이(0.75) |
| 요일 계수 | 토(1.35) > 일(1.25) > 금(1.15) > 목(0.95) ≈ 수(0.90) ≈ 월(0.90) > 화(0.85) |
| 노벨티 감쇠 | `0.5 + 0.85·exp(-경과일/4)` — 시작 직후 최고, 이후 지수적으로 감쇠해 바닥 0.5배 수렴 |
| 할인율 효과 | 정률 할인 30% 기준 중립, 높을수록(최대 1.9배) 관심 증가 / 1+1·사은품형은 중립값 |
| 좋아요 전환율 | 카테고리별 4.0~7.5% (조회수 대비) |
| 별점 | 카테고리 기본 만족도(3.8~4.15) + 할인 매력도 보정 + 정규분포 잡음, 1~5 반올림 |
| 재현성 | `np.random.default_rng(42)` 고정 시드 — 동일 입력이면 항상 동일 출력 |

**리뷰 텍스트 + 이중 감정 라벨링** (review_dashboard 프로젝트 방식 재사용):
- 별점 구간(긍정≥4 / 중립=3 / 부정≤2)에 맞는 한국어 문장 템플릿 풀에서 생성
  (10%는 의도적으로 톤을 섞어 현실적 잡음 반영)
- `rating_sentiment`(별점 기반)와 `text_sentiment`(키워드 규칙 기반, POS_LEX/NEG_LEX)를
  각각 독립적으로 계산해 **일치율 88.3%**를 교차 검증 지표로 제시 — review_dashboard의
  "별점과 감정의 상관관계" 기능을 간이화해 재사용한 것

---

## 4. 대시보드 — 어떻게 완전히 오프라인으로 만들었나

처음 버전은 Chart.js를 `<script src="https://cdnjs.../chart.js">` 로 CDN에서 불러왔는데,
검증 과정에서 두 가지 문제를 발견하고 고쳤습니다.

1. **문제**: 이 개발 환경의 네트워크 정책상 cdnjs.cloudflare.com에 접근할 수 없어
   `wkhtmltoimage`(구형 WebKit) 헤드리스 렌더링 시 차트가 완전히 빈 화면으로 나왔습니다.
   → **해결**: `npm pack chart.js@4.4.4`로 UMD 번들을 받아 `dashboard.html` 안에
   직접 인라인(vendoring)했습니다. 이제 인터넷 연결 없이도 항상 동일하게 작동합니다
   (실제 사용자 환경에서도 CDN 장애/차단에 영향받지 않는 부수 효과).
2. **검증**: Playwright(Chromium 헤드리스)로 실제 렌더링해 콘솔 에러 0건, 필터 클릭 시
   차트가 정상적으로 갱신되는 것까지 확인했습니다 (`docs/DASHBOARD_SCREENSHOTS.md`).

**구조 분리**: `templates/dashboard_template.html`(placeholder 포함) +
`scripts/build_dashboard.py`(데이터 주입) 로 나눠서, 데이터 소스가 시뮬레이션→실측으로
바뀌어도 `--daily`, `--mode real` 인자만 바꿔 재실행하면 대시보드가 자동으로
"LIVE DATA" 배지로 전환되도록 만들었습니다 (§2 다이어그램의 C 경로).

---

## 5. 실서비스 전환 가이드 (핵심)

### 5-1. 지금 실제 EventHub 스키마로 무엇이 되고, 무엇이 안 되는가

`krasia45/eventhub` 의 `schema.sql`을 직접 읽고 확인한 사실:

| 테이블 | 있는 것 | 이 분석에 필요하지만 없는 것 |
|---|---|---|
| `event_stats` | 이벤트별 조회수·좋아요 **누적 총합** | 날짜별 기록 (일별 시계열 불가) |
| `event_visits` | 방문 후기 자유 텍스트(`comment`) | 별점(`rating`) 컬럼 |
| (cron) | 후보 스캔(주1회), 링크 점검(일1회) | 통계 스냅샷 cron 없음 |

즉 **지금 당장 실측 데이터를 연결해도 이 리포트와 같은 "일별 조회수 추이"는 만들 수
없습니다** — 누적 카운터에는 시간 정보가 없기 때문입니다. 이것이 정직한 현재 상태입니다.

### 5-2. 그래서 준비한 것

**`sql/production_schema_additions.sql`** (Supabase SQL Editor에서 1회 실행, idempotent):
- `event_stats_daily(event_id, stat_date, views, likes, site_visits)` 테이블 신설 —
  매일 1회 `event_stats`의 누적값을 스냅샷으로 복사해 쌓는다.
- `snapshot_event_stats_daily()` 함수 — cron이 매일 호출하면 위 스냅샷을 만든다.
- `event_visits.rating` 컬럼 추가 (1~5, nullable — 기존 텍스트 후기와 호환).
- SQL 파일 하단에 "이후 코드 쪽에서 남은 작업"(cron 등록, 후기 폼에 별점 UI 추가)을
  구체적으로 안내.

**`scripts/fetch_real_data_from_supabase.py`**:
- `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` 환경변수로 접속 (기존 `seed_import.py`와
  동일한 변수명 — 운영 관행과 일치).
- `events`, `event_stats_daily`, `event_visits`를 읽어 **`eventhub_platform_daily.csv`와
  완전히 동일한 컬럼 스키마**로 재조립.
- 스냅샷이 아직 1일치뿐이거나 마이그레이션이 안 됐으면 죽지 않고 **무엇이 왜 부족한지
  한국어로 안내**하고 안전하게 종료.
- `--self-test`: 네트워크 없이 합성 fixture로 reshape 로직(일별 신규 조회수 = 오늘 누적 −
  어제 누적, 리뷰 집계 등)의 정확성을 assertion으로 검증. **실행 결과, 전부 통과했습니다**
  (본 저장소에는 실제 Supabase 자격증명이 없어 라이브 연결 자체는 테스트 불가 — 이 점은
  한계로 남습니다. 로직 정확성만 self-test로 보증합니다).

### 5-3. 오픈 후 실행 순서 (미래 시점)

```bash
# 1) Supabase SQL Editor에 sql/production_schema_additions.sql 적용
# 2) api/cron_jobs.py 에 스냅샷 job 추가 (SQL 파일 하단 안내 참고), 2~3주 데이터 축적
# 3) 실데이터 가져오기
export SUPABASE_URL=https://xxx.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=xxx
python3 scripts/fetch_real_data_from_supabase.py
#    → data/eventhub_platform_daily_REAL.csv 생성

# 4) 기존 분석 파이프라인을 입력만 바꿔 재실행
python3 scripts/analyze_and_visualize.py   # (내부 경로를 _REAL.csv로 수정)
python3 scripts/build_dashboard.py --daily data/eventhub_platform_daily_REAL.csv \
    --mode real
#    → dashboard.html이 "LIVE DATA" 배지로 자동 전환되어 재생성됨
```

---

## 6. 데이터 폭 확장 — "1년간 운영했다면" 시나리오 (Q. 실제 데이터가 부족하다는 우려에 대한 답)

### 6-1. 왜 필요했는가

본문 분석(§1~5)은 실제 카탈로그 그대로인 **112일(160건)**에 근거한다. 정직하되,
이 폭만으로는 두 가지가 아쉬웠다:
- 월별 계절성을 볼 수 없다 (112일 = 약 3.7개월).
- 카테고리당 표본이 20건뿐이라 트렌드 지표(REPORT.md §6 인사이트 2)가 관측 시점에
  따라 크게 흔들린다.

### 6-2. 접근 — "실제 데이터를 부풀리지 않고, 시간축으로만 확장한다"

실제 160건을 단 1건도 수정하지 않고 그대로 보존한 채, **그 이전 253일
(2025-08-21~2026-04-30)만** 실제 데이터의 경험적 분포로 통계적으로 백필했다.

```
┌───────────────────────────────┬─────────────────────────────────┐
│ 2025-08-21 ~ 2026-04-30 (253일) │ 2026-05-01 ~ 2026-08-20 (112일)  │
│ 백필 — 실제 160건에서 추정한      │ 실제 카탈로그 그대로 (160건,        │
│ 경험적 분포로 시뮬레이션 생성       │ 100% 실측, 단 1건도 수정 안 함)     │
└───────────────────────────────┴─────────────────────────────────┘
```

백필 이벤트의 카테고리별 할인율 분포·진행기간 분포·소상공인 비율·브랜드 풀은 전부
실제 160건에서 부트스트랩 추정했다 (`scripts/simulate_extended_catalog.py`). 신규
이벤트 유입률은 초기 0.5건/일 → 실제 구간 진입 시점 관측값(1.43건/일)까지 선형
증가하도록 설계했다 — 초기 스타트업이 이벤트 소싱 파이프라인을 늘려온 성장 곡선이라는
가정이며, **검증되지 않은 가정임을 명시**한다.

결과: **401건 · 365일**로 확장 (원본 대비 데이터 폭 3.3배).

![1년 전체 추이](images/extended/e01_full_year_trend.png)

### 6-3. 이 확장으로 실제로 무엇이 좋아졌는가 — 가설을 검증해봤다

REPORT.md §5-8에서 "신규 이벤트가 지속적으로 유입되면 예측이 더 안정적일 것"이라는
가설을 세웠었다. 이번에 데이터가 생겼으니 실제로 테스트했다. 3-way로 공정하게
비교해야 한다는 걸 검증 과정에서 깨달았다 — 단순히 ①(원본)과 ②(확장 전체)만
비교하면 답이 안 나온다. 왜냐하면 백필은 **과거 방향으로만** 확장했기 때문에, 8월
말단부의 "신규 이벤트가 끊기는" 문제 자체는 ②에도 그대로 남아있다. 그래서 ③(연속
공급이 보장된 중간 구간)까지 추가해야 공정한 비교가 된다.

![예측 가설 검증](images/extended/e03_forecast_comparison.png)

| 구간 | MAPE |
|---|---|
| ① 원본(112일) 말단 | 86.4% |
| ② 확장(365일) 말단 — 8월 공급단절 여전 | 89.9% |
| ③ 확장(365일) 중간 — 연속 공급 보장 | **24.5%** |

**결론**: "데이터가 많으면 예측이 좋아진다"가 아니라 **"공급이 끊기지 않는 구간에서만
예측이 안정적이다"**가 정확한 결론이었다. 처음 세운 가설을 한 단계 더 정교하게
다듬어준 검증이었다 — 이런 식으로 가설이 부분적으로만 맞고, 왜 그런지까지 밝혀내는
것이 이 확장 작업에서 얻은 가장 큰 소득이다.

### 6-4. 월별 추이 (이제 가능해진 것)

![월별 조회수](images/extended/e02_monthly_views.png)

### 6-5. 정직한 한계

- 백필 구간은 **통계적 시뮬레이션**이다. 실측이 아니다.
- 성장 곡선 가정(0.5→1.43건/일 선형 증가)은 검증되지 않았다.
- 카테고리 트렌드 안정성 비교(원본 28일 창 vs 확장 90일 창)는 비교 구간 길이 자체가
  달라서 "표본이 크면 안정된다"는 엄밀한 통제 실험이 아니다 — "작은 표본 스냅샷의
  트렌드는 관측 시점에 따라 크게 흔들린다"는 정성적 근거로만 해석해야 한다
  (`scripts/analyze_extended_scenario.py` 실행 로그 참고).
- 결국 **가장 신뢰할 수 있는 데이터는 여전히 실제 160건·112일**이다. 확장 시나리오는
  "데이터가 더 있었다면 어떤 분석이 가능해지는지"를 미리 보여주는 시뮬레이션이지,
  실제 부족분을 진짜로 메운 것은 아니다 — 정직하게는 실서비스 오픈 후 §5의 경로로
  실측 데이터를 쌓는 것이 유일한 근본 해법이다.

전체 실행 순서:
```bash
python3 scripts/simulate_extended_catalog.py   # 확장 카탈로그 생성 (401건)
python3 scripts/build_extended_scenario.py     # 관심도/리뷰 시뮬레이션 재실행 (365일)
python3 scripts/analyze_extended_scenario.py   # 시각화 4종 + 가설 검증
```

---

## 7. 폴더 구조

```
eventhub-trend-analysis/
├── REPORT.md                          ← 최종 분석 리포트 (필수 결과물)
├── README.md                          ← 이 문서
├── requirements.txt
├── analysis.ipynb                     ← 분석 노트북 (실행 결과 포함, 필수 결과물)
├── dashboard.html                     ← 인터랙티브 대시보드 (보너스: 서비스화, 완전 오프라인)
├── templates/
│   └── dashboard_template.html        ← 대시보드 소스 템플릿 (placeholder 포함)
├── sql/
│   └── production_schema_additions.sql ← 실서비스 전환용 추가 스키마 (제안)
├── data/
│   ├── eventhub_seed_events_raw.json  ← 원본 (EventHub 실제 이벤트 카탈로그, 160건)
│   ├── eventhub_events_clean.csv      ← 정제된 이벤트 테이블
│   ├── eventhub_daily_timeseries.csv  ← 카탈로그 기반 일별 시계열 (활성/신규 이벤트 수 등)
│   ├── eventhub_event_daily_engagement.csv  ← 이벤트×일 단위 시뮬레이션 조회수/좋아요
│   ├── eventhub_reviews_simulated.csv ← 시뮬레이션 리뷰(별점/텍스트/감정)
│   ├── eventhub_platform_daily.csv    ← ★ 최종 분석 데이터셋 (112일 × 41개 지표)
│   ├── eventhub_events_extended.csv        ← [고도화] 확장 카탈로그 (401건, is_real 컬럼)
│   ├── eventhub_event_daily_engagement_extended.csv
│   ├── eventhub_reviews_extended.csv
│   └── eventhub_platform_daily_extended.csv ← [고도화] 확장 최종 데이터셋 (365일)
├── images/                            ← 시각화 8종 (PNG)
│   └── extended/                      ← [고도화] 1년 확장 시나리오 시각화 4종
├── docs/
│   ├── DASHBOARD_SCREENSHOTS.md       ← 보너스: 대시보드 필터 시나리오 + 스크린샷
│   └── screenshots/*.png              ← 헤드리스 브라우저로 촬영한 실제 작동 화면 3종
└── scripts/                           ← 데이터 파이프라인 스크립트 (실행 순서대로)
    ├── build_timeseries.py            (1) 카탈로그 → 일별 시계열
    ├── simulate_engagement_and_reviews.py  (2) 관심도/리뷰 시뮬레이션
    ├── build_platform_daily.py        (3) 최종 데이터셋 조립
    ├── analyze_and_visualize.py       (4) 시각화 8종 + 분해 + 예측
    ├── make_notebook.py               (5) analysis.ipynb 생성
    ├── build_dashboard.py             (6) dashboard.html 조립 (템플릿 + 데이터)
    ├── fetch_real_data_from_supabase.py  [실서비스 전환용] 실측 데이터 어댑터
    ├── _vendor_chart.umd.js           Chart.js 번들 (build_dashboard.py가 내장용으로 사용)
    ├── simulate_extended_catalog.py   [고도화] 1년 확장 카탈로그 생성 (§6)
    ├── build_extended_scenario.py     [고도화] 확장 카탈로그 관심도/리뷰 시뮬레이션 재실행
    └── analyze_extended_scenario.py   [고도화] 확장 시나리오 시각화 + 가설 검증
```

---

## 8. 실행 방법

### 8-1. 환경 설정
```bash
python3 -m venv .venv && source .venv/bin/activate   # 선택 사항
pip install -r requirements.txt
sudo apt-get install -y fonts-nanum   # 한글 폰트 (matplotlib 한글 깨짐 방지)
```

### 8-2. 전체 파이프라인 재현 (시뮬레이션 데이터 기준)
```bash
python3 scripts/build_timeseries.py
python3 scripts/simulate_engagement_and_reviews.py
python3 scripts/build_platform_daily.py
python3 scripts/analyze_and_visualize.py
python3 scripts/make_notebook.py
jupyter nbconvert --to notebook --execute --inplace analysis.ipynb
python3 scripts/build_dashboard.py

# [고도화] 1년 확장 시나리오 (§6) — 위 파이프라인 실행 후 추가로:
python3 scripts/simulate_extended_catalog.py
python3 scripts/build_extended_scenario.py
python3 scripts/analyze_extended_scenario.py
```

### 8-3. 결과 확인
- `REPORT.md`를 열어 리포트를 읽는다 (이미지가 `images/`를 상대경로로 참조).
- `analysis.ipynb`를 Jupyter로 열면 코드+실행 결과(차트 포함)를 바로 볼 수 있다.
- `dashboard.html`을 브라우저로 더블클릭해서 열면 완전 오프라인으로 바로 작동한다.
  "전체 112일" 탭이 기본값이며, "최근 4주" 탭을 누르면 REPORT.md §5-4·§6에 인용된
  카테고리 증감률 수치와 정확히 일치하는 값을 볼 수 있다.
- `docs/DASHBOARD_SCREENSHOTS.md`에서 3가지 필터 시나리오 스크린샷을 바로 확인 가능.

### 8-4. 재현성 검증 (실제로 해봤습니다)

모든 스크립트는 `Path(__file__).resolve().parent.parent` 기준 상대경로로 파일을
찾기 때문에, 이 폴더를 **어디에 복사하거나 clone해도** 그대로 동작한다. 실제로
`/tmp/다른-경로/`에 전체를 복사한 뒤 8-2의 9단계 스크립트 + `jupyter nbconvert
--execute`까지 처음부터 다시 실행해 결과(데이터 9개, 이미지 12개, 노트북 38셀 0에러,
대시보드)가 문제없이 재생성되는 것을 확인했다.

---

## 9. 과제 요구사항 체크리스트

| 요구사항 | 충족 여부 |
|---|---|
| 시계열 데이터 100개 이상 | ✅ 112일 (2026-05-01~08-20) |
| 데이터 출처/기간 명시 | ✅ REPORT.md §3 |
| 분석 질문 3개 이상 | ✅ 4개 |
| 데이터 기본 정보/결측치/이상치 처리 | ✅ REPORT.md §4 |
| 시계열 분석 기법 2개 이상 | ✅ 이동평균·요일별 집계·구간비교·경과일 분석 (4개) |
| 시각화 2개 이상(권장 3개 이상) | ✅ 8종 |
| 인사이트 3개 이상(관찰 근거 포함) | ✅ 5개 |
| REPORT.md (주제/질문/데이터/시각화/인사이트/결론) | ✅ |
| Python 코드 (노트북 또는 스크립트) | ✅ `analysis.ipynb` + `scripts/*.py` 8개 |
| GitHub 저장소 | 🟡 로컬 git 커밋 완료, push는 제출자 계정 필요 (§10) |
| 재현성(requirements/실행방법) | ✅ §8 |
| AI 사용 투명성 로그 | ✅ REPORT.md §8 |
| [보너스] 서비스화(대시보드) | ✅ `dashboard.html` + 스크린샷 3종 |
| [보너스] 시계열 심화(분해/예측) | ✅ REPORT.md §5-7, §5-8 |
| (추가 고도화) 실서비스 전환 경로 | ✅ SQL 마이그레이션 + 어댑터 + self-test |
| (추가 고도화) 데이터 폭 확장(1년 시나리오) | ✅ §6, REPORT.md 부록 E — 가설 검증 포함 |

---

## 10. GitHub 저장소로 올리기

이 폴더는 이미 `git init` + 커밋이 되어 있습니다. 본인 GitHub 계정에 새 저장소를 만든 뒤
연결해서 push 하세요.

```bash
git remote add origin https://github.com/<your-id>/eventhub-trend-analysis.git
git branch -M main
git push -u origin main
```

> 기존 `krasia45/eventhub`(서비스 본체) 저장소에는 이 분석 산출물을 직접 올리지
> 않았습니다 — 프로덕션 코드와 과제 산출물을 분리하는 것이 더 깔끔하다고 판단했습니다.
> 원한다면 `eventhub` 저장소 안에 `analysis/` 서브폴더로 옮겨 함께 관리할 수도 있습니다.

---

## 11. 정직한 한계 (다시 한 번 요약)

- 조회수·좋아요·리뷰는 **시뮬레이션**입니다. §3의 가정은 합리적으로 설계했지만 실측이
  아닙니다 — 절대 수치가 아니라 **패턴**을 참고 자료로 봐주세요.
- `fetch_real_data_from_supabase.py`는 로직을 self-test로 검증했지만, 실제 Supabase
  인스턴스에 연결해 end-to-end로 실행해본 적은 없습니다 (자격증명이 없기 때문).
- REPORT.md §6 인사이트 4("6일간 이벤트 공급 공백")만은 시뮬레이션이 아니라 **원본
  카탈로그 자체에서 나온 실제 사실**입니다 — 서비스 오픈 전 지금 바로 검토할 가치가
  있는 유일한 "100% 실측 기반" 발견입니다.
