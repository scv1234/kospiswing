-- ═══════════════════════════════════════
-- Supabase 테이블 생성 SQL
-- Supabase Dashboard → SQL Editor에서 실행하세요
-- ═══════════════════════════════════════

-- 리포트 테이블
CREATE TABLE IF NOT EXISTS reports (
    id BIGSERIAL PRIMARY KEY,
    target_date TEXT NOT NULL,           -- '20260215' 형식
    report_type TEXT NOT NULL DEFAULT 'topdown',  -- 향후 확장용
    content TEXT NOT NULL,               -- 리포트 Markdown 본문
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- target_date + report_type 조합 유니크 (upsert용)
    UNIQUE(target_date, report_type)
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(target_date);
CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(report_type);
CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at DESC);

-- RLS (Row Level Security) 설정
-- anon key로 읽기/쓰기 가능하게 (퍼블릭 대시보드이므로)
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable read access for all users" ON reports
    FOR SELECT USING (true);

CREATE POLICY "Enable insert access for all users" ON reports
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable update access for all users" ON reports
    FOR UPDATE USING (true);
