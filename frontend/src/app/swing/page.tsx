"use client";

import { useEffect, useState } from "react";
import { fetchAPI, SwingData, SwingStock } from "@/lib/api";

const MEDALS = ["🥇", "🥈", "🥉"];

function ScoreBar({ score }: { score: number }) {
    const color =
        score >= 60 ? "var(--green)" : score >= 40 ? "var(--yellow)" : "var(--red)";
    return (
        <div className="score-bar">
            <div
                className="score-bar-fill"
                style={{ width: `${Math.min(100, score)}%`, background: color }}
            />
        </div>
    );
}

function Tags({ tags }: { tags: string }) {
    if (!tags) return null;
    const list = tags.split(",").map((t) => t.trim()).filter(Boolean);
    return (
        <div style={{ marginTop: 6 }}>
            {list.map((t) => (
                <span
                    key={t}
                    className={`tag ${t.includes("수급") || t.includes("쌍끌이") ? "tag-green" : t.includes("과열") ? "tag-red" : "tag-accent"}`}
                >
                    #{t}
                </span>
            ))}
        </div>
    );
}

function StockCard({ stock, rank }: { stock: SwingStock; rank?: number }) {
    const [open, setOpen] = useState(false);
    const isMedal = rank !== undefined && rank < 3;

    return (
        <div
            className={`card ${isMedal ? `medal-card medal-${rank + 1}` : ""}`}
            onClick={() => setOpen(!open)}
            style={{ cursor: "pointer" }}
        >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                    <h3>
                        {isMedal && <span style={{ marginRight: 6 }}>{MEDALS[rank]}</span>}
                        {stock.종목명}
                    </h3>
                    <p style={{ fontSize: "0.75em", color: "var(--text-muted)", margin: "2px 0" }}>
                        {stock.Sector}
                    </p>
                </div>
                <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "1.1em", fontWeight: 700 }}>
                        {stock.현재가?.toLocaleString()}원
                    </div>
                    <div className={`delta ${stock.등락률 > 0 ? "up" : stock.등락률 < 0 ? "down" : ""}`}>
                        {stock.등락률 > 0 ? "+" : ""}{stock.등락률?.toFixed(2)}%
                    </div>
                </div>
            </div>

            {/* Score */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
                <span style={{ fontSize: "0.78em", fontWeight: 700, color: "var(--accent-light)" }}>
                    {stock.스윙점수?.toFixed(1)}점
                </span>
                <div style={{ display: "flex", gap: 12, fontSize: "0.72em" }}>
                    <span style={{ color: "var(--green)" }}>목표 +{stock.목표수익률?.toFixed(1)}%</span>
                    <span style={{ color: "var(--red)" }}>손절 {stock.손절수익률?.toFixed(1)}%</span>
                </div>
            </div>
            <ScoreBar score={stock.스윙점수 || 0} />

            {/* Tags */}
            <Tags tags={stock.Tags || ""} />

            {/* Expandable Detail */}
            <div className={`expandable-content ${open ? "open" : ""}`}>
                <div style={{ marginTop: 12, padding: "12px 0", borderTop: "1px solid var(--border)" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: "0.78em", marginBottom: 8 }}>
                        <div><span style={{ color: "var(--text-muted)" }}>목표가</span> <strong>{stock.목표가?.toLocaleString()}원</strong></div>
                        <div><span style={{ color: "var(--text-muted)" }}>손절가</span> <strong>{stock.손절가?.toLocaleString()}원</strong></div>
                        <div><span style={{ color: "var(--text-muted)" }}>RSI</span> <strong>{stock.RSI?.toFixed(1)}</strong></div>
                    </div>
                    {stock.AI분석코멘트 && (
                        <div style={{
                            background: "rgba(102, 126, 234, 0.06)",
                            borderRadius: 8,
                            padding: 10,
                            fontSize: "0.78em",
                            lineHeight: 1.6,
                            color: "var(--text-secondary)",
                        }}>
                            💡 {stock.AI분석코멘트}
                        </div>
                    )}
                </div>
            </div>

            <div style={{ textAlign: "center", marginTop: 4 }}>
                <span style={{ fontSize: "0.68em", color: "var(--text-muted)" }}>
                    {open ? "접기 ▲" : "상세 보기 ▼"}
                </span>
            </div>
        </div>
    );
}

export default function SwingPage() {
    const [data, setData] = useState<SwingData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function load() {
            try {
                const res = await fetchAPI<SwingData>("/api/swing");
                setData(res);
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    if (loading) {
        return (
            <div className="loading-screen">
                <div className="loading-spinner" />
                <p style={{ color: "var(--text-muted)", fontSize: "0.85em" }}>
                    종목 분석 중... (최대 2분 소요)
                </p>
            </div>
        );
    }

    const top3 = data?.top3 || [];
    const rest = data?.data?.slice(3) || [];

    return (
        <>
            <div className="section-title">🚀 스윙 트레이딩</div>

            {data?.error && (
                <div className="card" style={{ borderColor: "var(--red)" }}>
                    <p style={{ color: "var(--red)", fontSize: "0.85em" }}>⚠️ {data.error}</p>
                </div>
            )}

            {/* TOP 3 */}
            {top3.length > 0 && (
                <>
                    <div className="section-title">🏆 TOP 3 추천 종목</div>
                    {top3.map((stock, i) => (
                        <StockCard key={stock.종목명 || i} stock={stock} rank={i} />
                    ))}
                </>
            )}

            {/* Rest */}
            {rest.length > 0 && (
                <>
                    <div className="section-title">📋 전체 스크리닝 결과</div>
                    {rest.map((stock, i) => (
                        <StockCard key={stock.종목명 || i} stock={stock} />
                    ))}
                </>
            )}

            {!top3.length && !rest.length && (
                <div className="card" style={{ textAlign: "center", padding: 40 }}>
                    <p style={{ color: "var(--text-muted)" }}>
                        분석 결과가 없습니다.<br />장 마감 후 다시 시도해 주세요.
                    </p>
                </div>
            )}
        </>
    );
}
