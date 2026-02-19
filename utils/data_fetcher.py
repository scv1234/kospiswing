import pandas as pd
from pykrx import stock
import FinanceDataReader as fdr
from datetime import datetime, timedelta, timezone
import streamlit as st

# ═══════════════════════════════════════
# KST 시간대 유틸 (Streamlit Cloud는 UTC)
# ═══════════════════════════════════════
KST = timezone(timedelta(hours=9))

def _now_kst():
    """항상 한국 시간 반환 (Cloud=UTC → +9시간)"""
    return datetime.now(KST)

# ═══════════════════════════════════════
# pykrx 안전 래퍼 (클라우드 호환)
# ═══════════════════════════════════════
def _safe_pykrx_call(func, *args, **kwargs):
    """pykrx 함수 호출을 try-except로 감싸서 클라우드 실패 방지"""
    try:
        result = func(*args, **kwargs)
        return result
    except Exception:
        return None


@st.cache_data(ttl=3600*24)
def get_ticker_mapping():
    """종목코드 -> 종목명, 업종 매핑 데이터"""
    # 1. FDR KRX-DESC 사용 (Sector/Industry 정보 포함)
    try:
        df = fdr.StockListing("KRX-DESC")
        cols = ['Code', 'Name']
        if 'Sector' in df.columns:
            cols.append('Sector')
        elif 'Industry' in df.columns:
            df.rename(columns={'Industry': 'Sector'}, inplace=True)
            cols.append('Sector')
        
        return df[cols].set_index('Code')
    except:
        pass

    # 2. FDR KRX (Fallback)
    try:
        df = fdr.StockListing("KRX")
        cols = ['Code', 'Name']
        if 'Sector' in df.columns:
            return df[['Code', 'Name', 'Sector']].set_index('Code')
        
        df_base = df[['Code', 'Name']].set_index('Code')
    except:
        df_base = pd.DataFrame()

    # 3. PyKRX를 이용해 업종 정보 채우기 (Fallback)
    sector_map = {}
    try:
        for market in ["KOSPI", "KOSDAQ"]:
            indices = stock.get_index_listing(market)
            for idx in indices:
                idx_name = stock.get_index_ticker_name(idx)
                if "코스피" in idx_name or "코스닥" in idx_name or "KRX" in idx_name:
                    continue
                tickers = stock.get_index_portfolio_deposit_file(idx)
                for code in tickers:
                    sector_map[code] = idx_name
                    
        df_sector = pd.DataFrame.from_dict(sector_map, orient='index', columns=['Sector'])
        if not df_base.empty:
            df_final = df_base.join(df_sector, how='left')
            df_final['Sector'] = df_final['Sector'].fillna('')
            return df_final
        else:
            return df_sector
            
    except Exception:
        return df_base


@st.cache_data(ttl=3600)
def get_latest_business_day():
    """최근 유효 거래일 (KST 기준, 클라우드 호환)
    - 장중(09:00~15:40 평일): 오늘 날짜 우선 시도, 데이터 없으면 전일 fallback
    - 장 마감 후 / 주말: 가장 최근 거래일 반환
    """
    now = _now_kst()
    date = now

    is_weekday = date.weekday() < 5
    is_market_hours = is_weekday and (
        (date.hour > 9 or (date.hour == 9 and date.minute >= 0)) and
        (date.hour < 15 or (date.hour == 15 and date.minute < 40))
    )

    # 장중이면 오늘부터 시도, 장 마감 후이면 오늘부터 시도 (마감 데이터 있으므로)
    # 장 시작 전(~09:00)이면 전일부터 시도
    if is_weekday and date.hour < 9:
        date -= timedelta(days=1)

    # 주말 처리
    if date.weekday() == 5:
        date -= timedelta(days=1)
    elif date.weekday() == 6:
        date -= timedelta(days=2)

    # pykrx로 데이터 유무 확인 (최대 7일)
    for _ in range(7):
        str_date = date.strftime("%Y%m%d")
        try:
            df = stock.get_index_ohlcv(str_date, str_date, "1001")
            if df is not None and not df.empty:
                return str_date
        except:
            pass

        # FDR fallback 체크
        try:
            fdr_date = date.strftime("%Y-%m-%d")
            df = fdr.DataReader("KS11", fdr_date, fdr_date)
            if df is not None and not df.empty:
                return str_date
        except:
            pass

        date -= timedelta(days=1)
        # 주말 건너뛰기
        if date.weekday() == 6:
            date -= timedelta(days=2)
        elif date.weekday() == 5:
            date -= timedelta(days=1)

    # 최종 Fallback
    date = now - timedelta(days=1)
    while date.weekday() >= 5:
        date -= timedelta(days=1)
    return date.strftime("%Y%m%d")

@st.cache_data(ttl=600)
def get_kospi_chart_data(days=60):
    """KOSPI 일봉 데이터 — pykrx 우선, FDR fallback"""
    now = _now_kst()
    end_date = now.strftime("%Y%m%d")
    start_date = (now - timedelta(days=days)).strftime("%Y%m%d")
    
    # 1순위: pykrx
    try:
        df = stock.get_index_ohlcv(start_date, end_date, "1001")
        if df is not None and not df.empty:
            return df
    except Exception:
        pass
    
    # 2순위: FDR
    try:
        start_fdr = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        end_fdr = now.strftime("%Y-%m-%d")
        df = fdr.DataReader("KS11", start_fdr, end_fdr)
        if df is not None and not df.empty:
            df = df.rename(columns={
                'Open': '시가', 'High': '고가', 'Low': '저가',
                'Close': '종가', 'Volume': '거래량'
            })
            # 등락률 컬럼 추가 (pykrx 호환)
            if '등락률' not in df.columns and '종가' in df.columns:
                df['등락률'] = df['종가'].pct_change() * 100
            return df
    except Exception:
        pass
    
    return pd.DataFrame()

@st.cache_data(ttl=600)
def get_exchange_rate_data(symbol="USD/KRW", days=60):
    """환율 데이터"""
    try:
        now = _now_kst()
        end_date = now.strftime("%Y-%m-%d")
        start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        df = fdr.DataReader(symbol, start_date, end_date)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_market_net_purchases(date, market="KOSPI", investor="외국인", top_n=30):
    """일자별 순매수/순매도 데이터"""
    try:
        df = stock.get_market_net_purchases_of_equities(date, date, market, investor)
        if df is None or df.empty:
            return pd.DataFrame()
            
        df = df.sort_values(by="순매수거래대금", ascending=False)
        
        # 등락률 정보 추가
        try:
            df_ohlcv = stock.get_market_ohlcv(date, market=market)
            if df_ohlcv is not None and not df_ohlcv.empty and '등락률' in df_ohlcv.columns:
                df = df.join(df_ohlcv[['등락률']], how='left')
            else:
                df['등락률'] = 0.0
        except:
            df['등락률'] = 0.0
        
        # 종목명, 업종 매핑
        mapping = get_ticker_mapping()
        
        if mapping is not None and not mapping.empty:
            if 'Sector' not in mapping.columns:
                mapping['Sector'] = ""
            df = df.join(mapping[['Sector']], how='left')
        else:
            df['Sector'] = ""
        
        # 컬럼 정제
        cols = ['종목명', 'Sector', '순매수거래대금', '등락률']
        valid_cols = [c for c in cols if c in df.columns]
        result = df[valid_cols].copy()
        
        if '순매수거래대금' in result.columns:
            result['순매수(억)'] = (result['순매수거래대금'] / 1e8).round(1)
        
        if top_n:
            return result.head(top_n)
        return result
        
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_leading_sectors(date, market="KOSPI", top_n=5):
    """Top-Down 분석: 외국인/기관 수급 주도 섹터 추출"""
    try:
        df_foreign = get_market_net_purchases(date, market, "외국인", top_n=None)
        if not df_foreign.empty and 'Sector' in df_foreign.columns:
            sector_foreign = df_foreign.groupby('Sector')['순매수거래대금'].sum().sort_values(ascending=False)
            top_foreign_sectors = set(sector_foreign.head(top_n).index)
        else:
            top_foreign_sectors = set()
            
        df_inst = get_market_net_purchases(date, market, "기관합계", top_n=None)
        if not df_inst.empty and 'Sector' in df_inst.columns:
            sector_inst = df_inst.groupby('Sector')['순매수거래대금'].sum().sort_values(ascending=False)
            top_inst_sectors = set(sector_inst.head(top_n).index)
        else:
            top_inst_sectors = set()
            
        leading_sectors = (top_foreign_sectors | top_inst_sectors) - {''}
        return leading_sectors
        
    except Exception:
        return set()

@st.cache_data(ttl=600)
def get_global_indices(days=5):
    """주요 글로벌 지수 (NASDAQ, S&P500, SOX) 조회"""
    indices = {
        "NASDAQ": "IXIC",
        "S&P500": "US500", 
        "SOX": "SOXX"
    }
    
    result = {}
    now = _now_kst()
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    
    for name, symbol in indices.items():
        try:
            df = fdr.DataReader(symbol, start_date, end_date)
            if df is not None and not df.empty:
                result[name] = df
        except:
            continue
            
    return result

@st.cache_data(ttl=600)
def get_sector_returns(date, market="KOSPI"):
    """섹터별 평균 등락률 계산"""
    try:
        df_price = stock.get_market_ohlcv(date, market=market)
        df_map = get_ticker_mapping()
        
        if df_price is None or df_price.empty or df_map is None or df_map.empty:
            return pd.Series(dtype=float)
        
        if '등락률' not in df_price.columns:
            return pd.Series(dtype=float)
            
        df_merged = df_price.join(df_map[['Sector']], how='inner')
        sector_ret = df_merged.groupby('Sector')['등락률'].mean().sort_values(ascending=False)
        
        if '' in sector_ret.index:
            sector_ret = sector_ret.drop('')
            
        return sector_ret
        
    except Exception:
        return pd.Series(dtype=float)
