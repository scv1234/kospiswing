import Link from "next/link";

export default function Home() {
  return (
    <>
      <header className="header">
        <div>
          <h1>📈 주식분석</h1>
          <div className="subtitle">KOSPI Top-Down & Swing Trading</div>
        </div>
      </header>

      <div className="section-title">📍 메뉴</div>

      <Link href="/topdown" className="card-link">
        <div className="card">
          <h3>📊 Top-Down 리포트</h3>
          <p>
            KOSPI · 환율 · 글로벌 지수 · 섹터 수급 · AI 분석 리포트
          </p>
          <span className="arrow">→</span>
        </div>
      </Link>

      <Link href="/swing" className="card-link">
        <div className="card">
          <h3>🚀 스윙 트레이딩</h3>
          <p>
            6팩터 점수 · TOP 3 추천 · 기술적 분석 · 매매 전략
          </p>
          <span className="arrow">→</span>
        </div>
      </Link>

      <div style={{ marginTop: 32, textAlign: "center" }}>
        <p style={{ fontSize: "0.75em", color: "var(--text-muted)" }}>
          Made with ❤️ by Antigravity
          <br />
          Powered by pykrx & Next.js
        </p>
      </div>
    </>
  );
}
