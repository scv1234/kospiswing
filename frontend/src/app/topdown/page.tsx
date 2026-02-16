"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { fetchAPI, MacroData, SectorData, ReportData } from "@/lib/api";

function MetricCard({ label, value, delta, unit }: {
    label: string; value: string; delta?: number; unit?: string;
}) {
    const isUp = delta !== undefined && delta > 0;
    const isDown = delta !== undefined && delta < 0;
    return (
        <div className="metric">
            <div className="label">{label}</div>
            <div className="value">{value}{unit}</div>
            {delta !== undefined && (
                <div className={`delta ${isUp ? "up" : isDown ? "down" : ""}`}>
                    {isUp ? "▲" : isDown ? "▼" : "-"} {Math.abs(delta).toFixed(2)}%
                </div>
            )}
        </div>
    );
}

export default function TopDownPage() {
    const [macro, setMacro] = useState<MacroData | null>(null);
    const [sectors, setSectors] = useState<SectorData | null>(null);
    const [report, setReport] = useState<ReportData | null>(null);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);

    useEffect(() => {
        async function load() {
            try {
                const [m, s, r] = await Promise.all([
                    fetchAPI<MacroData>("/api/macro?days=5"),
                    fetchAPI<SectorData>("/api/sectors"),
                    fetchAPI<ReportData>("/api/report/latest"),
                ]);
                setMacro(m);
                setSectors(s);
                setReport(r);
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    async function handleGenerate() {
        setGenerating(true);
        try {
            const res = await fetchAPI<{ success: boolean; content?: string; date?: string; error?: string }>(
                "/api/report/generate"
            );
            if (res.success && res.content) {
                setReport({ content: res.content, date: res.date || null, source: "just generated" });
            } else {
                alert(res.error || "생성 실패");
            }
        } catch (e) {
            alert("리포트 생성 중 오류 발생");
        } finally {
            setGenerating(false);
        }
    }

    if (loading) {
        return (
            <div className="loading-screen">
                <div className="loading-spinner" />
                <p style={{ color: "var(--text-muted)", fontSize: "0.85em" }}>시장 데이터 로딩 중...</p>
            </div>
        );
    }

    const topSectors = sectors?.data?.slice(0, 5) || [];
    const bottomSectors = sectors?.data?.slice(-5).reverse() || [];

    return (
        <>
            <div className="section-title">📊 Top-Down 리포트</div>

            {/* Macro Metrics */}
            <div className="metrics-grid">
                <MetricCard
                    label="KOSPI"
                    value={macro?.kospi?.current?.toLocaleString() || "-"}
                    delta={macro?.kospi?.changePct}
                />
                <MetricCard
                    label="USD/KRW"
                    value={macro?.exchange?.current?.toLocaleString() || "-"}
                    unit="원"
                />
                {macro?.global?.NASDAQ && (
                    <MetricCard
                        label="NASDAQ"
                        value={macro.global.NASDAQ.current.toLocaleString()}
                        delta={macro.global.NASDAQ.changePct}
                    />
                )}
                {macro?.global?.SOX && (
                    <MetricCard
                        label="SOX"
                        value={macro.global.SOX.current.toLocaleString()}
                        delta={macro.global.SOX.changePct}
                    />
                )}
            </div>

            {/* Sector Returns */}
            {topSectors.length > 0 && (
                <>
                    <div className="section-title">🏆 섹터 등락률</div>
                    <div className="card" style={{ padding: 12 }}>
                        <table className="data-table">
                            <thead>
                                <tr><th>섹터</th><th style={{ textAlign: "right" }}>등락률</th></tr>
                            </thead>
                            <tbody>
                                {topSectors.map((s) => (
                                    <tr key={s.sector}>
                                        <td>{s.sector}</td>
                                        <td style={{ textAlign: "right" }}>
                                            <span className={s.return > 0 ? "delta up" : s.return < 0 ? "delta down" : ""}>
                                                {s.return > 0 ? "+" : ""}{s.return.toFixed(2)}%
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </>
            )}

            {/* Report */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "24px 0 12px" }}>
                <div className="section-title" style={{ margin: 0 }}>📄 AI 리포트</div>
                <button
                    className="btn btn-primary"
                    style={{ width: "auto", padding: "8px 16px", fontSize: "0.78em" }}
                    onClick={handleGenerate}
                    disabled={generating}
                >
                    {generating ? "생성 중..." : "🔄 최신화"}
                </button>
            </div>

            {report?.content ? (
                <div className="card report-content">
                    <ReactMarkdown>{report.content}</ReactMarkdown>
                </div>
            ) : (
                <div className="card" style={{ textAlign: "center", padding: 40 }}>
                    <p style={{ color: "var(--text-muted)" }}>
                        리포트가 없습니다.<br />위 &apos;최신화&apos; 버튼을 눌러 생성하세요.
                    </p>
                </div>
            )}
        </>
    );
}
