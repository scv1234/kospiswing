"""
Stock Analysis API — FastAPI Backend
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os, sys

# .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv()  # fallback: 현재 디렉토리
except:
    pass

from utils.data_fetcher import (
    get_latest_business_day, get_kospi_chart_data, get_exchange_rate_data,
    get_market_net_purchases, get_leading_sectors, get_global_indices,
    get_sector_returns, get_ticker_mapping
)
from utils.supabase_client import save_report, load_report, load_report_latest

# ── 캐시 (서버 메모리, TTL 없는 단순 캐시) ──
_cache = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    _cache.clear()

app = FastAPI(
    title="Stock Analysis API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — 프론트엔드 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 배포 시 Vercel 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════
# Helper: DataFrame → JSON 변환
# ═══════════════════════════════════════
def df_to_records(df):
    """DataFrame을 JSON-serializable list로 변환"""
    if df is None or df.empty:
        return []
    df = df.copy()
    # index를 컬럼으로
    if df.index.name or not isinstance(df.index, range):
        df = df.reset_index()
    # datetime index를 문자열로
    for col in df.columns:
        if hasattr(df[col], 'dt'):
            df[col] = df[col].astype(str)
    # NaN → None
    df = df.where(df.notna(), None)
    return df.to_dict(orient='records')


# ═══════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════

@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/business-day")
def api_business_day():
    """최근 거래일"""
    date = get_latest_business_day()
    return {"date": date}


@app.get("/api/macro")
def api_macro(days: int = Query(5, ge=1, le=365)):
    """거시경제 지표 (KOSPI, 환율, 글로벌 지수)"""
    kospi_df = get_kospi_chart_data(days=days)
    ex_df = get_exchange_rate_data(days=days)
    global_idx = get_global_indices(days=max(days, 10))
    
    # KOSPI 요약
    kospi = {}
    if not kospi_df.empty and len(kospi_df) >= 2:
        kospi = {
            "current": float(kospi_df['종가'].iloc[-1]),
            "prev": float(kospi_df['종가'].iloc[-2]),
            "change": float(kospi_df['종가'].iloc[-1] - kospi_df['종가'].iloc[-2]),
            "changePct": float((kospi_df['종가'].iloc[-1] - kospi_df['종가'].iloc[-2]) / kospi_df['종가'].iloc[-2] * 100),
            "chart": df_to_records(kospi_df)
        }
    
    # 환율 요약
    exchange = {}
    if not ex_df.empty and len(ex_df) >= 2:
        exchange = {
            "current": float(ex_df['Close'].iloc[-1]),
            "prev": float(ex_df['Close'].iloc[-2]),
            "change": float(ex_df['Close'].iloc[-1] - ex_df['Close'].iloc[-2]),
            "chart": df_to_records(ex_df)
        }
    
    # 글로벌 지수 요약
    global_summary = {}
    for name, df in global_idx.items():
        if len(df) >= 2:
            global_summary[name] = {
                "current": float(df['Close'].iloc[-1]),
                "prev": float(df['Close'].iloc[-2]),
                "changePct": float((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100)
            }
    
    return {
        "kospi": kospi,
        "exchange": exchange,
        "global": global_summary
    }


@app.get("/api/supply")
def api_supply(
    date: str = Query(None),
    investor: str = Query("외국인"),
    top_n: int = Query(10)
):
    """투자자별 순매수 데이터"""
    if not date:
        date = get_latest_business_day()
    
    df = get_market_net_purchases(date, investor=investor, top_n=top_n)
    return {
        "date": date,
        "investor": investor,
        "data": df_to_records(df)
    }


@app.get("/api/sectors")
def api_sectors(date: str = Query(None)):
    """섹터별 등락률"""
    if not date:
        date = get_latest_business_day()
    
    sector_ret = get_sector_returns(date)
    
    data = []
    if not sector_ret.empty:
        data = [{"sector": k, "return": round(float(v), 2)} for k, v in sector_ret.items()]
    
    return {
        "date": date,
        "data": data
    }


@app.get("/api/swing")
def api_swing():
    """스윙 트레이딩 분석"""
    try:
        from utils.analysis import run_swing_analysis
        df_result, top_picks = run_swing_analysis()
        
        if df_result is None or df_result.empty:
            return {"data": [], "top3": []}
        
        records = df_to_records(df_result)
        top3 = records[:3] if len(records) >= 3 else records
        
        return {
            "data": records,
            "top3": top3
        }
    except Exception as e:
        return {"data": [], "top3": [], "error": str(e)}


@app.get("/api/report/latest")
def api_report_latest():
    """최신 리포트 조회"""
    content, target_date = load_report_latest()
    if content:
        return {"content": content, "date": target_date, "source": "supabase"}
    return {"content": None, "date": None, "source": None}


@app.get("/api/report/{date}")
def api_report_by_date(date: str):
    """특정 날짜 리포트 조회"""
    content = load_report(date)
    if content:
        return {"content": content, "date": date}
    return {"content": None, "date": date}


@app.post("/api/report/generate")
def api_report_generate():
    """리포트 생성"""
    try:
        from utils.report_generator import generate_topdown_report
        date = get_latest_business_day()
        report_text, filename, storage = generate_topdown_report(date)
        
        if report_text and not report_text.startswith("리포트 생성 중 오류"):
            return {"success": True, "date": date, "storage": storage, "content": report_text}
        return {"success": False, "error": report_text}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════
# Trading Journal (매매기록)
# ═══════════════════════════════════════
from pydantic import BaseModel
from typing import Optional


class TradeRecord(BaseModel):
    date: str
    ticker: str
    trade_type: str  # "매수" or "매도"
    price: int
    qty: int
    note: Optional[str] = ""


@app.get("/api/trades")
def api_trades_list():
    """매매기록 조회"""
    from utils.supabase_client import get_supabase_client
    client = get_supabase_client()
    if not client:
        return {"data": []}
    try:
        result = client.table("trades").select("*").order("date", desc=True).limit(100).execute()
        return {"data": result.data or []}
    except Exception as e:
        return {"data": [], "error": str(e)}


@app.post("/api/trades")
def api_trades_create(trade: TradeRecord):
    """매매기록 추가"""
    from utils.supabase_client import get_supabase_client
    client = get_supabase_client()
    if not client:
        return {"success": False, "error": "DB 연결 실패"}
    try:
        data = {
            "date": trade.date,
            "ticker": trade.ticker,
            "trade_type": trade.trade_type,
            "price": trade.price,
            "qty": trade.qty,
            "note": trade.note or "",
        }
        client.table("trades").insert(data).execute()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/api/trades/{trade_id}")
def api_trades_delete(trade_id: int):
    """매매기록 삭제"""
    from utils.supabase_client import get_supabase_client
    client = get_supabase_client()
    if not client:
        return {"success": False, "error": "DB 연결 실패"}
    try:
        client.table("trades").delete().eq("id", trade_id).execute()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════
# 실행
# ═══════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
