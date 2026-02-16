import pandas as pd
from pykrx import stock
import FinanceDataReader as fdr
from datetime import datetime, timedelta, timezone
from functools import lru_cache

# ═══════════════════════════════════════
# KST 시간대 유틸
# ═══════════════════════════════════════
KST = timezone(timedelta(hours=9))

def _now_kst():
    return datetime.now(KST)


def get_ticker_mapping():
    """종목코드 -> 종목명, 업종 매핑"""
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

    try:
        df = fdr.StockListing("KRX")
        if 'Sector' in df.columns:
            return df[['Code', 'Name', 'Sector']].set_index('Code')
        return df[['Code', 'Name']].set_index('Code')
    except:
        return pd.DataFrame()


def get_latest_business_day():
    """최근 유효 거래일 (KST 기준)"""
    date = _now_kst()
    
    if date.hour < 15 or (date.hour == 15 and date.minute < 40):
        date -= timedelta(days=1)

    if date.weekday() == 5:
        date -= timedelta(days=1)
    elif date.weekday() == 6:
        date -= timedelta(days=2)
    
    for _ in range(7):
        str_date = date.strftime("%Y%m%d")
        try:
            df = stock.get_index_ohlcv(str_date, str_date, "1001")
            if df is not None and not df.empty:
                return str_date
        except:
            pass
        try:
            fdr_date = date.strftime("%Y-%m-%d")
            df = fdr.DataReader("KS11", fdr_date, fdr_date)
            if df is not None and not df.empty:
                return str_date
        except:
            pass
        date -= timedelta(days=1)
        while date.weekday() >= 5:
            date -= timedelta(days=1)
        
    date = _now_kst() - timedelta(days=1)
    while date.weekday() >= 5:
        date -= timedelta(days=1)
    return date.strftime("%Y%m%d")


def get_kospi_chart_data(days=60):
    """KOSPI 일봉 데이터"""
    now = _now_kst()
    end_date = now.strftime("%Y%m%d")
    start_date = (now - timedelta(days=days)).strftime("%Y%m%d")
    
    try:
        df = stock.get_index_ohlcv(start_date, end_date, "1001")
        if df is not None and not df.empty:
            return df
    except:
        pass
    
    try:
        start_fdr = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        end_fdr = now.strftime("%Y-%m-%d")
        df = fdr.DataReader("KS11", start_fdr, end_fdr)
        if df is not None and not df.empty:
            df = df.rename(columns={
                'Open': '시가', 'High': '고가', 'Low': '저가',
                'Close': '종가', 'Volume': '거래량'
            })
            if '등락률' not in df.columns and '종가' in df.columns:
                df['등락률'] = df['종가'].pct_change() * 100
            return df
    except:
        pass
    
    return pd.DataFrame()


def get_exchange_rate_data(symbol="USD/KRW", days=60):
    """환율 데이터"""
    try:
        now = _now_kst()
        end_date = now.strftime("%Y-%m-%d")
        start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        df = fdr.DataReader(symbol, start_date, end_date)
        return df if df is not None else pd.DataFrame()
    except:
        return pd.DataFrame()


def get_market_net_purchases(date, market="KOSPI", investor="외국인", top_n=30):
    """순매수/순매도 데이터"""
    try:
        df = stock.get_market_net_purchases_of_equities(date, date, market, investor)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.sort_values(by="순매수거래대금", ascending=False)
        
        try:
            df_ohlcv = stock.get_market_ohlcv(date, market=market)
            if df_ohlcv is not None and not df_ohlcv.empty and '등락률' in df_ohlcv.columns:
                df = df.join(df_ohlcv[['등락률']], how='left')
            else:
                df['등락률'] = 0.0
        except:
            df['등락률'] = 0.0
        
        mapping = get_ticker_mapping()
        if mapping is not None and not mapping.empty:
            if 'Sector' not in mapping.columns:
                mapping['Sector'] = ""
            df = df.join(mapping[['Sector']], how='left')
        else:
            df['Sector'] = ""
        
        cols = ['종목명', 'Sector', '순매수거래대금', '등락률']
        valid_cols = [c for c in cols if c in df.columns]
        result = df[valid_cols].copy()
        
        if '순매수거래대금' in result.columns:
            result['순매수(억)'] = (result['순매수거래대금'] / 1e8).round(1)
        
        if top_n:
            return result.head(top_n)
        return result
    except:
        return pd.DataFrame()


def get_leading_sectors(date, market="KOSPI", top_n=5):
    """수급 주도 섹터"""
    try:
        df_foreign = get_market_net_purchases(date, market, "외국인", top_n=None)
        top_foreign = set()
        if not df_foreign.empty and 'Sector' in df_foreign.columns:
            s = df_foreign.groupby('Sector')['순매수거래대금'].sum().sort_values(ascending=False)
            top_foreign = set(s.head(top_n).index)
            
        df_inst = get_market_net_purchases(date, market, "기관합계", top_n=None)
        top_inst = set()
        if not df_inst.empty and 'Sector' in df_inst.columns:
            s = df_inst.groupby('Sector')['순매수거래대금'].sum().sort_values(ascending=False)
            top_inst = set(s.head(top_n).index)
            
        return (top_foreign | top_inst) - {''}
    except:
        return set()


def get_global_indices(days=5):
    """글로벌 지수"""
    indices = {"NASDAQ": "IXIC", "S&P500": "US500", "SOX": "SOXX"}
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


def get_sector_returns(date, market="KOSPI"):
    """섹터별 평균 등락률"""
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
    except:
        return pd.Series(dtype=float)
