# EventHub 트렌드 분석 — 시뮬레이션 버전 + 실제 데이터 버전

> **[AI 데이터 분석] 데이터 기반 트렌드 분석** 미션 결과물
> 이 저장소 하나에 **분석 2개**가 들어있습니다. 아래에서 차이를 쉽게 설명드릴게요.

---

## 0. 이 저장소, 한마디로 뭔가요?

같은 과제를 **두 번** 했습니다. 이유는 이렇습니다:

- 처음 할 때는 EventHub가 아직 정식 오픈 전이라 실제 데이터가 없었어요. 그래서
  "진짜 데이터가 있다면 이럴 것이다"를 통계적으로 **시뮬레이션**해서 분석했습니다.
  → [`simulation-analysis/`](./simulation-analysis) 폴더
- 나중에 네이버에서 진짜 검색 데이터를 받을 수 있는 방법을 찾았어요. 그래서 이번엔
  **실제 데이터**(사람들이 네이버에서 "성수동"을 얼마나 검색했는지)로 똑같은 분석을
  다시 했습니다. → [`real-data-analysis/`](./real-data-analysis) 폴더

**두 분석 모두 각각 독립적으로 과제 요구사항을 전부 만족합니다** (아래 §7 체크리스트
참고). 시뮬레이션 버전은 "나중에 진짜 서비스가 커지면 이런 식으로 분석하면 된다"는
설계도 역할을 하고, 실제 데이터 버전은 "지금 당장 확인 가능한 진짜 사실"을 보여줍니다.

---

## 1. 🖥️ 대시보드 먼저 보기 (제일 쉬운 방법)

**아래 주소를 클릭하면 브라우저에서 바로 볼 수 있습니다.** 설치할 것도, 코드를
실행할 필요도 없어요.

### 👉 https://krasia45.github.io/trend-analysis-l/

접속하면 위쪽에 탭이 두 개 보입니다:
- **📊 시뮬레이션 분석** — 가상의 EventHub 운영 데이터
- **🔍 실제 데이터 분석** — 진짜 네이버 검색 트렌드

탭을 눌러가며 왔다갔다 비교해보실 수 있어요.

> ⚠️ **아직 위 주소가 안 열린다면?** GitHub Pages라는 기능을 한 번 켜줘야 합니다.
> §6에 3분이면 끝나는 방법을 적어뒀어요.

---

## 2. 두 분석의 차이 (한눈에 보기)

| | 📊 시뮬레이션 분석 | 🔍 실제 데이터 분석 |
|---|---|---|
| **폴더** | [`simulation-analysis/`](./simulation-analysis) | [`real-data-analysis/`](./real-data-analysis) |
| **데이터** | EventHub 실제 이벤트 카탈로그(160건) + 통계적으로 만든 가상 조회수·좋아요·리뷰 | 네이버 실제 검색어 트렌드 (성수동/팝업스토어/할인, 365일) |
| **진짜 데이터인가?** | ❌ 아니요, 시뮬레이션입니다 | ✅ 네, 실제 API로 받은 진짜 데이터입니다 |
| **왜 필요한가** | EventHub가 커지면 실제 데이터로 그대로 갈아끼울 수 있게 설계해둔 것 | 지금 당장 확인 가능한 성수동 상권의 실제 관심도 |
| **대시보드** | [docs/simulation/](./docs/simulation) | [docs/real-data/](./docs/real-data) |
| **리포트** | [simulation-analysis/REPORT.md](./simulation-analysis/REPORT.md) | [real-data-analysis/REPORT.md](./real-data-analysis/REPORT.md) |

---

## 3. 각 분석이 어떻게 만들어졌는지 궁금하다면

### 📊 시뮬레이션 분석
EventHub의 실제 이벤트 목록(브랜드, 할인율, 진행기간 등 160건)은 진짜예요. 그런데
"사람들이 실제로 이걸 얼마나 봤는지"는 서비스 오픈 전이라 데이터가 없어서, 요일·
카테고리·할인율에 따라 조회수가 어떻게 변할지를 통계적으로 계산해서 만들었습니다.
자세한 계산 방법은 [simulation-analysis/README.md](./simulation-analysis/README.md)에
있습니다.

### 🔍 실제 데이터 분석
[NAVER API HUB](https://www.ncloud.com/product/applicationService/naverApiHub)라는
네이버의 공식 서비스를 통해 "성수동", "팝업스토어", "할인" 세 단어를 사람들이 최근
1년간 얼마나 검색했는지 실제로 받아왔습니다. 이 데이터는 가공하거나 지어낸 것이
전혀 없는 진짜 검색 기록입니다. 자세한 내용은
[real-data-analysis/README.md](./real-data-analysis/README.md)에 있습니다
*(초보자 눈높이로 설명되어 있어요)*.

---

## 4. 폴더 구조

```
trend-analysis-l/
├── README.md                  ← 지금 보고 계신 파일
├── docs/                       ← GitHub Pages가 여기를 웹사이트로 보여줍니다
│   ├── index.html                  대시보드 허브 (탭 전환 페이지)
│   ├── simulation/index.html       시뮬레이션 대시보드
│   └── real-data/index.html        실제 데이터 대시보드
│
├── simulation-analysis/       ← 첫 번째 분석 (가상 데이터)
│   ├── REPORT.md                   분석 리포트
│   ├── analysis.ipynb              분석 코드 (실행 결과 포함)
│   ├── dashboard.html              대시보드 원본 파일
│   ├── data/, images/, scripts/    데이터·그래프·코드
│   └── README.md                   이 분석만의 상세 설명
│
└── real-data-analysis/        ← 두 번째 분석 (실제 데이터)
    ├── REPORT.md                   분석 리포트
    ├── analysis.ipynb              분석 코드 (실행 결과 포함)
    ├── dashboard.html               대시보드 원본 파일
    ├── data/                       naver_search_trend_raw.json (원본) + 정제된 CSV
    ├── images/                     시각화 6종
    └── scripts/                    데이터 정제·시각화 코드
```

---

## 5. 내 컴퓨터에서 직접 실행해보고 싶다면 (초보자용)

대시보드는 그냥 열어보면 되지만, "코드가 진짜 이 결과를 만드는지" 직접 실행해보고
싶으시면 아래를 따라 하세요.

### 5-1. 터미널 열기
- **Mac**: Spotlight(⌘+Space)에서 "터미널" 검색해서 실행
- **Windows**: 시작 메뉴에서 "PowerShell" 검색해서 실행

### 5-2. 저장소 받기
```bash
git clone https://github.com/krasia45/trend-analysis-l.git
cd trend-analysis-l
```

### 5-3. 실제 데이터 분석 실행해보기
```bash
cd real-data-analysis
python3 -m venv .venv
source .venv/bin/activate          # Windows는: .venv\Scripts\activate
pip install -r requirements.txt

python3 scripts/clean_data.py           # 원본 JSON → 정제된 CSV
python3 scripts/analyze_and_visualize.py  # 그래프 6개 생성 (images/ 폴더에 저장됨)
```
`images/` 폴더를 열어보시면 방금 만들어진 그래프들이 보일 거예요. `REPORT.md`를
열면 그 그래프들에 대한 설명과 인사이트를 읽을 수 있습니다.

### 5-4. 노트북으로 보고 싶다면
```bash
jupyter notebook analysis.ipynb
```
브라우저가 열리면서 코드와 결과(그래프 포함)를 한 화면에서 순서대로 볼 수 있습니다.
이미 실행된 결과가 저장되어 있어서, 그냥 열기만 해도 그래프가 바로 보입니다.

### 5-5. 시뮬레이션 분석도 똑같은 방식
```bash
cd ../simulation-analysis
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/build_timeseries.py
python3 scripts/simulate_engagement_and_reviews.py
python3 scripts/build_platform_daily.py
python3 scripts/analyze_and_visualize.py
```
(순서대로 실행해야 합니다 — 뒤 단계가 앞 단계의 결과물을 사용해요)

---

## 6. GitHub Pages 켜는 방법 (대시보드 주소가 아직 안 열릴 때만)

이 저장소를 갓 받으셨거나, §1의 주소가 아직 안 열린다면 딱 한 번 설정을 켜주셔야
합니다. 3분이면 끝나요.

1. GitHub에서 이 저장소(`krasia45/trend-analysis-l`) 페이지로 이동
2. 상단 메뉴에서 **"Settings"** 클릭
3. 왼쪽 메뉴에서 **"Pages"** 클릭
4. **"Build and deployment"** 항목에서:
   - Source: **"Deploy from a branch"** 선택
   - Branch: **"main"**, 폴더는 **"/docs"** 선택
5. **"Save"** 클릭
6. 1~2분 기다리면 페이지 상단에 초록색으로 **"Your site is live at
   https://krasia45.github.io/trend-analysis-l/"** 라고 뜹니다 — 그 주소로 들어가면
   대시보드가 보입니다.

---

## 7. 과제 요구사항 체크리스트

**시뮬레이션 분석과 실제 데이터 분석 둘 다 각각 아래 요구사항을 전부 만족합니다.**

| 요구사항 | 📊 시뮬레이션 | 🔍 실제 데이터 |
|---|---|---|
| 시계열 데이터 100개 이상 | ✅ 112일 | ✅ 365일 |
| 데이터 출처/기간 명시 | ✅ | ✅ |
| 분석 질문 3개 이상 | ✅ 4개 | ✅ 4개 |
| 데이터 정제(결측치/이상치) | ✅ | ✅ |
| 시계열 분석 기법 2개 이상 | ✅ 4개(이동평균/요일별/구간비교/경과일) | ✅ 4개(이동평균/요일별/월별/상관관계) |
| 시각화 2개 이상(권장 3개 이상) | ✅ 8종 | ✅ 6종 |
| 인사이트 3개 이상(근거 포함) | ✅ 3개 | ✅ 4개 |
| REPORT.md | ✅ | ✅ |
| Python 코드(노트북/스크립트) | ✅ | ✅ |
| GitHub 저장소 | ✅ (이 저장소) | ✅ (이 저장소) |
| 재현성(requirements.txt, 실행법) | ✅ | ✅ |
| AI 사용 로그 | ✅ | ✅ |
| **[보너스] 서비스화(대시보드)** | ✅ | ✅ |
| **[보너스] 시계열 심화(분해/예측)** | ✅ | ✅ |
| (추가) 실서비스 전환 경로 설계 | ✅ (§5, 시뮬레이션→실측 전환 SQL/어댑터) | — (이미 실측이라 해당 없음) |
| (추가) 두 분석 통합 대시보드 | ✅ 하나의 대시보드에서 탭으로 전환 가능 | |

세부 항목별 근거는 각 폴더의 REPORT.md에서 확인할 수 있습니다.

---

## 8. 데이터 출처 및 라이선스

- **시뮬레이션 분석 원본**: EventHub 실제 이벤트 카탈로그
  ([github.com/krasia45/eventhub](https://github.com/krasia45/eventhub)의
  `seed_events.json`, 2026-08-20 기준 스냅샷, 160건). 조회수·좋아요·리뷰는 이 원본을
  바탕으로 만든 통계적 시뮬레이션이며 실측이 아니다.
- **실제 데이터 분석 원본**: NAVER API HUB Search Trend API로 2026-08-25에 수집한
  실제 검색어 트렌드. 네이버 오픈 API 이용약관에 따라 제공되는 상대 검색량 지수이며,
  원본 검색 로그나 재판매 목적의 재배포는 허용되지 않는다.
- 이 저장소는 학습/과제 제출 목적의 분석이며, EventHub 서비스 본체
  (`krasia45/eventhub`)의 프로덕션 코드와는 별도로 관리된다.
