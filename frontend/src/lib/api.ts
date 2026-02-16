const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchAPI<T>(endpoint: string): Promise<T> {
    const res = await fetch(`${API_BASE}${endpoint}`, {
        cache: "no-store",
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

export interface MacroData {
    kospi: {
        current: number;
        prev: number;
        change: number;
        changePct: number;
        chart: Record<string, unknown>[];
    };
    exchange: {
        current: number;
        prev: number;
        change: number;
        chart: Record<string, unknown>[];
    };
    global: Record<string, { current: number; prev: number; changePct: number }>;
}

export interface SupplyData {
    date: string;
    investor: string;
    data: Record<string, unknown>[];
}

export interface SectorData {
    date: string;
    data: { sector: string; return: number }[];
}

export interface SwingStock {
    종목명: string;
    Sector: string;
    현재가: number;
    등락률: number;
    스윙점수: number;
    목표가: number;
    손절가: number;
    목표수익률: number;
    손절수익률: number;
    RSI: number;
    Tags: string;
    AI분석코멘트: string;
    [key: string]: unknown;
}

export interface SwingData {
    data: SwingStock[];
    top3: SwingStock[];
    error?: string;
}

export interface ReportData {
    content: string | null;
    date: string | null;
    source?: string;
}
