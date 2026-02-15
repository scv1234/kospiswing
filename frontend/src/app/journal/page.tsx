"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchAPI } from "@/lib/api";

interface Trade {
    id: number;
    date: string;
    ticker: string;
    trade_type: string;
    price: number;
    qty: number;
    note: string;
}

export default function JournalPage() {
    const [trades, setTrades] = useState<Trade[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);

    // Form state
    const [date, setDate] = useState(new Date().toISOString().split("T")[0]);
    const [ticker, setTicker] = useState("");
    const [tradeType, setTradeType] = useState("매수");
    const [price, setPrice] = useState("");
    const [qty, setQty] = useState("");
    const [note, setNote] = useState("");
    const [submitting, setSubmitting] = useState(false);

    const loadTrades = useCallback(async () => {
        try {
            const res = await fetchAPI<{ data: Trade[] }>("/api/trades");
            setTrades(res.data || []);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadTrades();
    }, [loadTrades]);

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (!ticker || !price || !qty) return;
        setSubmitting(true);
        try {
            const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(`${API_BASE}/api/trades`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    date,
                    ticker,
                    trade_type: tradeType,
                    price: parseInt(price),
                    qty: parseInt(qty),
                    note,
                }),
            });
            const data = await res.json();
            if (data.success) {
                setTicker("");
                setPrice("");
                setQty("");
                setNote("");
                setShowForm(false);
                loadTrades();
            } else {
                alert(data.error || "저장 실패");
            }
        } catch {
            alert("저장 중 오류 발생");
        } finally {
            setSubmitting(false);
        }
    }

    async function handleDelete(id: number) {
        if (!confirm("이 기록을 삭제하시겠습니까?")) return;
        try {
            const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            await fetch(`${API_BASE}/api/trades/${id}`, { method: "DELETE" });
            loadTrades();
        } catch {
            alert("삭제 실패");
        }
    }

    if (loading) {
        return (
            <div className="loading-screen">
                <div className="loading-spinner" />
                <p style={{ color: "var(--text-muted)", fontSize: "0.85em" }}>매매기록 로딩 중...</p>
            </div>
        );
    }

    const buyCount = trades.filter((t) => t.trade_type === "매수").length;
    const sellCount = trades.filter((t) => t.trade_type === "매도").length;

    return (
        <>
            <div className="section-title">📝 매매기록</div>

            {/* Summary */}
            <div className="metrics-grid">
                <div className="metric">
                    <div className="label">총 매수</div>
                    <div className="value" style={{ color: "var(--green)" }}>{buyCount}회</div>
                </div>
                <div className="metric">
                    <div className="label">총 매도</div>
                    <div className="value" style={{ color: "var(--red)" }}>{sellCount}회</div>
                </div>
            </div>

            {/* Add Button */}
            <button
                className="btn btn-primary"
                onClick={() => setShowForm(!showForm)}
                style={{ marginBottom: 16 }}
            >
                {showForm ? "✕ 닫기" : "➕ 새 매매기록 추가"}
            </button>

            {/* Form */}
            {showForm && (
                <div className="card" style={{ marginBottom: 16 }}>
                    <form onSubmit={handleSubmit}>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
                            <div>
                                <label style={labelStyle}>날짜</label>
                                <input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={inputStyle} />
                            </div>
                            <div>
                                <label style={labelStyle}>종목명</label>
                                <input type="text" value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="삼성전자" style={inputStyle} required />
                            </div>
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 10 }}>
                            <div>
                                <label style={labelStyle}>구분</label>
                                <select value={tradeType} onChange={(e) => setTradeType(e.target.value)} style={inputStyle}>
                                    <option value="매수">매수</option>
                                    <option value="매도">매도</option>
                                </select>
                            </div>
                            <div>
                                <label style={labelStyle}>가격</label>
                                <input type="number" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="75000" style={inputStyle} required />
                            </div>
                            <div>
                                <label style={labelStyle}>수량</label>
                                <input type="number" value={qty} onChange={(e) => setQty(e.target.value)} placeholder="10" style={inputStyle} required />
                            </div>
                        </div>
                        <div style={{ marginBottom: 12 }}>
                            <label style={labelStyle}>매매 메모</label>
                            <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="진입/청산 근거를 기록하세요" style={{ ...inputStyle, height: 60, resize: "none" }} />
                        </div>
                        <button type="submit" className="btn btn-primary" disabled={submitting}>
                            {submitting ? "저장 중..." : "💾 기록 저장"}
                        </button>
                    </form>
                </div>
            )}

            {/* Trade List */}
            <div className="section-title">📋 기록장</div>
            {trades.length === 0 ? (
                <div className="card" style={{ textAlign: "center", padding: 40 }}>
                    <p style={{ color: "var(--text-muted)" }}>아직 매매기록이 없습니다.</p>
                </div>
            ) : (
                trades.map((t) => (
                    <div key={t.id} className="card" style={{ padding: 14 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <div>
                                <span
                                    className={`tag ${t.trade_type === "매수" ? "tag-green" : "tag-red"}`}
                                    style={{ marginRight: 8 }}
                                >
                                    {t.trade_type}
                                </span>
                                <strong>{t.ticker}</strong>
                            </div>
                            <span style={{ fontSize: "0.72em", color: "var(--text-muted)" }}>{t.date}</span>
                        </div>
                        <div style={{ marginTop: 6, fontSize: "0.82em", color: "var(--text-secondary)" }}>
                            {t.price?.toLocaleString()}원 × {t.qty}주 = <strong>{(t.price * t.qty).toLocaleString()}원</strong>
                        </div>
                        {t.note && (
                            <div style={{ marginTop: 6, fontSize: "0.78em", color: "var(--text-muted)", fontStyle: "italic" }}>
                                💬 {t.note}
                            </div>
                        )}
                        <button
                            onClick={() => handleDelete(t.id)}
                            style={{
                                marginTop: 8, background: "none", border: "1px solid var(--border)",
                                color: "var(--text-muted)", borderRadius: 6, padding: "4px 10px",
                                fontSize: "0.72em", cursor: "pointer",
                            }}
                        >
                            🗑 삭제
                        </button>
                    </div>
                ))
            )}
        </>
    );
}

const labelStyle: React.CSSProperties = {
    display: "block",
    fontSize: "0.72em",
    fontWeight: 600,
    color: "var(--text-muted)",
    marginBottom: 4,
    textTransform: "uppercase",
    letterSpacing: "0.5px",
};

const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "10px 12px",
    background: "var(--bg-secondary)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    color: "var(--text-primary)",
    fontFamily: "inherit",
    fontSize: "0.85em",
};
