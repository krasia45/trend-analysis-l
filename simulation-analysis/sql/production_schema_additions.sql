-- ════════════════════════════════════════════════════════════
-- EventHub 관심도 분석 — 실서비스 전환을 위한 추가 스키마 (제안)
--
-- 이 파일은 krasia45/eventhub 의 schema.sql 을 대체하지 않고, 그 위에
-- '추가로' 적용하는 additive migration 입니다. 전부 idempotent
-- (`if not exists`) 하게 작성되어 몇 번을 실행해도 안전합니다.
--
-- 왜 필요한가?
--   현재 실제 스키마의 event_stats(views, likes, site_visits)는
--   "지금까지 누적된 총합"만 저장하는 카운터 테이블이라, 하루하루의
--   변화를 알 수 없습니다 (일별 시계열을 만들 수 없음). 이 분석
--   리포트가 다루는 '일별 조회수 추이/요일 패턴/노벨티 감쇠'를 실제
--   데이터로 재현하려면 하루 1회 스냅샷이 필요합니다.
--
--   또한 event_visits(다녀온 사람들의 한줄평)는 자유 텍스트
--   comment만 있고 별점(rating)이 없어, '카테고리별 만족도' 분석을
--   할 수 없습니다. rating 컬럼을 추가합니다.
-- ════════════════════════════════════════════════════════════

-- 1) 일별 스냅샷 테이블 — event_stats의 누적값을 하루 1회 복사해 쌓는다.
--    (일별 "신규 조회수"는 분석 스크립트에서 오늘값-어제값으로 계산한다.
--     스냅샷 자체는 단순 누적 복사이므로 SQL이 복잡해지지 않는다.)
create table if not exists event_stats_daily (
  event_id   text not null references events(id) on delete cascade,
  stat_date  date not null,
  views      integer not null default 0,   -- 그 날짜 기준 누적 조회수
  likes      integer not null default 0,
  site_visits integer not null default 0,
  snapshotted_at timestamptz default now(),
  primary key (event_id, stat_date)
);
create index if not exists idx_event_stats_daily_date on event_stats_daily(stat_date);

alter table event_stats_daily enable row level security;
-- PostgreSQL은 CREATE POLICY IF NOT EXISTS 문법을 지원하지 않으므로
-- DO 블록으로 존재 여부를 확인한 뒤에만 생성한다 (재실행해도 안전).
do $$
begin
  if not exists (
    select 1 from pg_policies
    where tablename = 'event_stats_daily' and policyname = '일별 통계는 누구나 조회 가능'
  ) then
    create policy "일별 통계는 누구나 조회 가능"
      on event_stats_daily for select using (true);
  end if;
end $$;

-- 2) 스냅샷 함수 — 매일 1회(cron)이 호출. 오늘 날짜 값이 있으면 덮어쓴다
--    (하루에 여러 번 실행돼도 안전 = idempotent upsert).
create or replace function snapshot_event_stats_daily()
returns void as $$
begin
  insert into event_stats_daily (event_id, stat_date, views, likes, site_visits)
  select event_id, current_date, views, likes, site_visits
  from event_stats
  on conflict (event_id, stat_date)
  do update set
    views = excluded.views,
    likes = excluded.likes,
    site_visits = excluded.site_visits,
    snapshotted_at = now();
end;
$$ language plpgsql;

-- 3) 리뷰 별점 — event_visits(방문 후기)에 1~5점 별점을 추가한다.
--    NULL 허용(기존 한줄평만 남긴 후기와 호환) — 없으면 텍스트만 있는 리뷰로 취급.
alter table event_visits
  add column if not exists rating smallint;
-- PostgreSQL은 ADD CONSTRAINT IF NOT EXISTS 문법도 지원하지 않으므로 동일하게 가드한다.
do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'event_visits_rating_range'
  ) then
    alter table event_visits
      add constraint event_visits_rating_range
      check (rating is null or (rating between 1 and 5));
  end if;
end $$;

-- ════════════════════════════════════════════════════════════
-- 적용 후 남은 작업 (코드 쪽, 이 SQL만으로는 자동화되지 않음):
--
-- (a) api/cron_jobs.py 에 job=snapshot_stats 분기 추가:
--       elif job == "snapshot_stats":
--           sb_rpc("snapshot_event_stats_daily", {})
--     vercel.json crons 배열에 매일 자정 실행 항목 추가.
--
-- (b) 05-event-sheet.js의 방문 후기 작성 폼에 별점(1~5) 입력 UI 추가,
--     event_visits insert 시 rating 필드 포함해서 전송.
--
-- 두 가지를 적용하고 최소 2~3주 데이터가 쌓이면,
-- scripts/fetch_real_data_from_supabase.py 가 그대로 동작해
-- 본 분석 파이프라인(analyze_and_visualize.py, analysis.ipynb,
-- dashboard.html)을 실측 데이터로 재실행할 수 있습니다.
-- ════════════════════════════════════════════════════════════
