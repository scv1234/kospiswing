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


-- ═══════════════════════════════════════
-- 스윙 분석 결과 테이블 (GitHub Actions → 프론트엔드)
-- ═══════════════════════════════════════
CREATE TABLE IF NOT EXISTS analysis_results (
    id BIGSERIAL PRIMARY KEY,
    target_date TEXT NOT NULL,                  -- '20260215' 형식
    result_type TEXT NOT NULL DEFAULT 'swing',  -- 'swing' | 'topdown' 등
    results_json TEXT NOT NULL,                 -- 전체 스크리닝 결과 (JSON 문자열)
    top_picks_json TEXT,                        -- TOP 3 종목 (JSON 문자열)
    stock_count INTEGER DEFAULT 0,             -- 분석된 종목 수
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(target_date, result_type)
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_analysis_date ON analysis_results(target_date);
CREATE INDEX IF NOT EXISTS idx_analysis_type ON analysis_results(result_type);
CREATE INDEX IF NOT EXISTS idx_analysis_created ON analysis_results(created_at DESC);

-- RLS
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable read for all" ON analysis_results
    FOR SELECT USING (true);

CREATE POLICY "Enable insert for all" ON analysis_results
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable update for all" ON analysis_results
    FOR UPDATE USING (true);
