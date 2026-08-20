# EventHub 관심도 인텔리전스 — 일별 트렌드 분석

> **[AI 데이터 분석] 데이터 기반 트렌드 분석** 미션 결과물
> "EventHub가 실제로 운영되고 있다면, 사람들은 지금 무엇에 관심이 있을까?"를
> 실제 이벤트 카탈로그 + 시뮬레이션 관심도 데이터로 분석합니다.

📄 **분석 리포트**: [`REPORT.md`](./REPORT.md) ← 결과 요약은 여기서 먼저 확인하세요
📓 **분석 코드(노트북)**: [`analysis.ipynb`](./analysis.ipynb)
🖥️ **인터랙티브 대시보드**: [`dashboard.html`](./dashboard.html) (보너스: 서비스화)

---

## 1. 한눈에 보기

```
실제 이벤트 카탈로그 (seed_events.json, 160건)
        │  ── 실제 필드: 카테고리 / 브랜드 / 할인율 / 진행기간
        ▼
일별 시계열 변환 (build_timeseries.py)
        │
        ▼
관심도 · 리뷰 시뮬레이션 (simulate_engagement_and_reviews.py)
        │  ── "서비스가 실제로 운영된다면"을 가정한 조회수/좋아요/별점 생성
        ▼
최종 일별 데이터셋 (build_platform_daily.py) → data/eventhub_platform_daily.csv
        │
        ├──▶ 시각화 + 시계열 분해 + 예측 (analyze_and_visualize.py) → images/*.png
        ├──▶ 분석 노트북 (make_notebook.py → analysis.ipynb)
        └──▶ 인터랙티브 대시보드 (dashboard.html)
```

EventHub는 아직 정식 오픈 전(가동 준비 중)이라 실측 트래픽이 없습니다. 그래서 이 분석은
**실제 이벤트 카탈로그(카테고리·브랜드·할인율·기간)를 입력으로, 서비스가 운영 중이라는
가정 하에 사용자 관심도를 통계적으로 시뮬레이션**합니다. 이 사실은 리포트와 대시보드 양쪽에
투명하게 명시되어 있습니다. (예외: "6일간 이벤트 공급 공백기" 발견은 시뮬레이션이 아니라
원본 카탈로그 자체에서 나온 실제 사실입니다 — REPORT.md §6 인사이트 4 참고)

---

## 2. 폴더 구조

```
eventhub-trend-analysis/
├── REPORT.md                          ← 최종 분석 리포트 (필수 결과물)
├── README.md                          ← 이 문서
├── requirements.txt
├── analysis.ipynb                     ← 분석 노트북 (실행 결과 포함, 필수 결과물)
├── dashboard.html                     ← 인터랙티브 대시보드 (보너스: 서비스화)
├── data/
│   ├── eventhub_seed_events_raw.json  ← 원본 (EventHub 실제 이벤트 카탈로그, 160건)
│   ├── eventhub_events_clean.csv      ← 정제된 이벤트 테이블
│   ├── eventhub_daily_timeseries.csv  ← 카탈로그 기반 일별 시계열 (활성/신규 이벤트 수 등)
│   ├── eventhub_event_daily_engagement.csv  ← 이벤트×일 단위 시뮬레이션 조회수/좋아요
│   ├── eventhub_reviews_simulated.csv ← 시뮬레이션 리뷰(별점/텍스트/감정)
│   ├── eventhub_platform_daily.csv    ← ★ 최종 분석 데이터셋 (112일 × 41개 지표)
│   └── dashboard_data.json            ← 대시보드용 압축 데이터
├── images/                            ← 시각화 8종 (PNG)
└── scripts/                           ← 데이터 파이프라인 스크립트 (5개, 순서대로 실행)
    ├── build_timeseries.py
    ├── simulate_engagement_and_reviews.py
    ├── build_platform_daily.py
    ├── analyze_and_visualize.py
    └── make_notebook.py
```

---

## 3. 실행 방법

### 3-1. 환경 설정
```bash
python3 -m venv .venv && source .venv/bin/activate   # 선택 사항
pip install -r requirements.txt
# 한글 폰트가 없다면 (matplotlib 한글 깨짐 방지)
sudo apt-get install -y fonts-nanum
```

### 3-2. 데이터 파이프라인 재현 (전체 실행 순서)
```bash
python3 scripts/build_timeseries.py                    # 1) 카탈로그 → 일별 시계열
python3 scripts/simulate_engagement_and_reviews.py      # 2) 관심도/리뷰 시뮬레이션 (시드 고정, 재현 가능)
python3 scripts/build_platform_daily.py                 # 3) 최종 데이터셋 조립
python3 scripts/analyze_and_visualize.py                 # 4) 시각화 8종 + 분해 + 예측
python3 scripts/make_notebook.py                        # 5) analysis.ipynb 생성
jupyter nbconvert --to notebook --execute --inplace analysis.ipynb  # 6) 노트북 실행(결과 내장)
```

### 3-3. 결과 확인
- `REPORT.md`를 열어 리포트를 읽는다 (이미지가 `images/`를 상대경로로 참조).
- `analysis.ipynb`를 Jupyter로 열면 코드+실행 결과(차트 포함)를 바로 볼 수 있다.
- `dashboard.html`을 브라우저로 더블클릭해서 열면 별도 서버 없이 바로 작동한다
  (데이터가 파일 안에 내장되어 있음). GitHub Pages 등에 올리면 배포 URL로도 활용 가능.

---

## 4. 재현성 / 의존성

- Python 3.10+
- 주요 라이브러리: `pandas`, `numpy`, `matplotlib`, `statsmodels`, `jupyter`, `nbformat`, `nbclient`
  (버전은 `requirements.txt` 참고)
- 시뮬레이션은 `np.random.default_rng(42)`로 시드를 고정해 **완전히 재현 가능**합니다.
- 데이터 출처: [github.com/krasia45/eventhub](https://github.com/krasia45/eventhub) —
  `seed_events.json` (EventHub 실제 이벤트 카탈로그, 160건, 분석 시점 기준 스냅샷)
- 라이선스 주의: 원본 카탈로그의 브랜드명·이미지는 EventHub 서비스 시연용 콘텐츠이며,
  이 리포지토리는 학습/과제 제출 목적의 파생 분석입니다.

---

## 5. 과제 요구사항 체크리스트

| 요구사항 | 충족 여부 |
|---|---|
| 시계열 데이터 100개 이상 | ✅ 112일 (2026-05-01~08-20) |
| 데이터 출처/기간 명시 | ✅ §3 데이터 설명 (REPORT.md) |
| 분석 질문 3개 이상 | ✅ 4개 |
| 데이터 기본 정보/결측치/이상치 처리 | ✅ §4 (REPORT.md) |
| 시계열 분석 기법 2개 이상 | ✅ 이동평균 · 요일별 집계 · 구간비교 · 경과일 분석 (4개) |
| 시각화 2개 이상(권장 3개 이상) | ✅ 8종 |
| 인사이트 3개 이상(관찰 근거 포함) | ✅ 5개 |
| REPORT.md (주제/질문/데이터/시각화/인사이트/결론) | ✅ |
| Python 코드 (노트북 또는 스크립트) | ✅ `analysis.ipynb` + `scripts/*.py` |
| GitHub 저장소 | ✅ 이 폴더를 그대로 새 저장소로 push (아래 안내) |
| 재현성(requirements/실행방법) | ✅ 본 README §3~4 |
| AI 사용 투명성 로그 | ✅ REPORT.md §8 |
| [보너스] 서비스화(대시보드) | ✅ `dashboard.html` |
| [보너스] 시계열 심화(분해/예측) | ✅ REPORT.md §5-7, §5-8 |

---

## 6. GitHub 저장소로 올리기

이 폴더는 이미 `git init`이 되어 있습니다 (커밋 이력 포함). 본인 GitHub 계정에 새 저장소를
만든 뒤 아래처럼 연결해서 push 하세요.

```bash
# GitHub에서 새 저장소 생성 후 (예: eventhub-trend-analysis)
git remote add origin https://github.com/<your-id>/eventhub-trend-analysis.git
git branch -M main
git push -u origin main
```

> 기존 `krasia45/eventhub`(서비스 본체) 저장소에는 이 분석 산출물을 직접 올리지 않았습니다.
> 별도 저장소로 분리해 제출용으로 깔끔하게 관리하는 것을 권장합니다. 원한다면
> `eventhub` 저장소 안에 `analysis/` 서브폴더로 옮겨 함께 관리할 수도 있습니다.
