import pandas as pd
from pykrx import stock
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import streamlit as st

# 모바일 최적화를 위해 데이터 크기를 줄이고 캐싱을 적극 활용

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
        
        # 해당 컬럼만 반환
        return df[cols].set_index('Code')
    except:
        pass

    # 2. FDR KRX (Fallback)
    try:
        df = fdr.StockListing("KRX")
        cols = ['Code', 'Name']
        if 'Sector' in df.columns:
            return df[['Code', 'Name', 'Sector']].set_index('Code')
        
        # Sector 없으면 Name만 챙김
        df_base = df[['Code', 'Name']].set_index('Code')
    except:
        df_base = pd.DataFrame()

    # 2. PyKRX를 이용해 업종 정보 채우기 (Fallback)
    sector_map = {}
    
    # KRX 전체 지수 스캔 (약 3~5초 소요 예상)
    try:
        for market in ["KOSPI", "KOSDAQ"]:
            indices = stock.get_index_listing(market)
            # 인덱스 리스트 중 '코스피', '코스닥' 등 시장 대표 지수 제외하고
            # '반도체', '제약' 등 업종 지수만 골라내면 좋겠지만 필터링 어려움.
            # 그냥 다 돌면서 덮어쓰기 (하위 섹터가 덮어써지길 기대)
            for idx in indices:
                idx_name = stock.get_index_ticker_name(idx)
                # 시장 대표 지수명이 포함된 경우 스킵 (ex: 코스피 200) - 업종 구분이 모호해짐
                if "코스피" in idx_name or "코스닥" in idx_name or "KRX" in idx_name:
                    continue
                    
                tickers = stock.get_index_portfolio_deposit_file(idx)
                for code in tickers:
                    # 이미 있는 경우 더 구체적인(긴) 이름이나 나중에 나온 걸로? 
                    # 보통 지수 리스트 순서가 업종 -> 테마 순일 수 있음.
                    # 일단 덮어쓰기
                    sector_map[code] = idx_name
                    
        # 매핑 적용
        df_sector = pd.DataFrame.from_dict(sector_map, orient='index', columns=['Sector'])
        if not df_base.empty:
            df_final = df_base.join(df_sector, how='left')
            df_final['Sector'] = df_final['Sector'].fillna('') # 없는 건 빈 문자열
            return df_final
        else:
            return df_sector
            
    except Exception as e:
        # 에러 나면 그냥 기본 정보만 반환
        return df_base


@st.cache_data(ttl=3600)
def get_latest_business_day():
    """최근 유효 거래일 (평일 & 데이터 존재 여부 확인)"""
    date = datetime.now()
    
    # 1. 시간 체크 (장 마감 전에는 전일 데이터 사용)
    # 15시 30분 장 마감, 15시 45분쯤 집계 완료 가정
    current_time = datetime.now().time()
    if current_time.hour < 15 or (current_time.hour == 15 and current_time.minute < 40):
         # 장 마감 전이면 어제를 기준으로 시작
         date -= timedelta(days=1)

    # 2. 주말 처리 (토/일 -> 금)
    if date.weekday() == 5: # 토요일
        date -= timedelta(days=1)
    elif date.weekday() == 6: # 일요일
        date -= timedelta(days=2)
    
    # 3. 데이터 유무 확인 (최대 5일)
    for _ in range(5): 
        str_date = date.strftime("%Y%m%d")
        try:
            # KOSPI 지수 데이터로 장 열림 여부 확인
            df = stock.get_index_ohlcv(str_date, str_date, "1001") # 1001: KOSPI
            if not df.empty:
                return str_date
        except:
            pass
        date -= timedelta(days=1)
        
    # 3. 실패 시 가장 최근 평일 반환 (Fallback)
    date = datetime.now()
    if date.weekday() == 5: date -= timedelta(days=1)
    elif date.weekday() == 6: date -= timedelta(days=2)
    
    return date.strftime("%Y%m%d")

@st.cache_data(ttl=600)  # 10분 캐시 (장중 업데이트 고려)
def get_kospi_chart_data(days=60):
    """KOSPI 일봉 데이터 (차트용) — pykrx 우선, FDR fallback"""
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    
    # 1순위: pykrx
    try:
        df = stock.get_index_ohlcv(start_date, end_date, "1001")  # KOSPI
        if not df.empty:
            return df
    except Exception:
        pass
    
    # 2순위: FinanceDataReader (클라우드 환경 fallback)
    try:
        start_fdr = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end_fdr = datetime.now().strftime("%Y-%m-%d")
        df = fdr.DataReader("KS11", start_fdr, end_fdr)  # KS11 = KOSPI
        if not df.empty:
            # pykrx 컬럼명으로 맞춤 (1페이지 호환)
            df = df.rename(columns={
                'Open': '시가', 'High': '고가', 'Low': '저가',
                'Close': '종가', 'Volume': '거래량'
            })
            return df
    except Exception:
        pass
    
    return pd.DataFrame()

@st.cache_data(ttl=600)
def get_exchange_rate_data(symbol="USD/KRW", days=60):
    """환율 데이터 (USD/KRW 등)"""
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        df = fdr.DataReader(symbol, start_date, end_date)
        return df
    except Exception:
        return pd.DataFrame()
@st.cache_data(ttl=600)
def get_market_net_purchases(date, market="KOSPI", investor="외국인", top_n=30):
    """일자별 순매수/순매도 데이터 (top_n=None이면 전체 반환)"""
    try:
        # pykrx 순매수 (금액 기준 정렬 추천)
        # 종목별 순매수 (금액 단위: 원)
        df = stock.get_market_net_purchases_of_equities(date, date, market, investor)
        df = df.sort_values(by="순매수거래대금", ascending=False)
        
        # 등락률 정보 추가 (get_market_ohlcv 사용 — market_cap은 등락률 미포함 케이스 있음)
        try:
            df_ohlcv = stock.get_market_ohlcv(date, market=market)
            if not df_ohlcv.empty and '등락률' in df_ohlcv.columns:
                df = df.join(df_ohlcv[['등락률']], how='left')
            else:
                df['등락률'] = 0.0
        except:
            df['등락률'] = 0.0  # 실패해도 순매수는 보여줌
        
        # 종목명, 업종 매핑
        mapping = get_ticker_mapping()
        
        if not mapping.empty:
            if 'Sector' not in mapping.columns:
                mapping['Sector'] = ""
            df = df.join(mapping[['Sector']], how='left')
        else:
            df['Sector'] = ""
        
        # 모바일용 컬럼 축소 및 정제
        cols = ['종목명', 'Sector', '순매수거래대금', '등락률']
        valid_cols = [c for c in cols if c in df.columns]
        
        # 전체 데이터가 필요한 경우 (순매도 분석 등)
        result = df[valid_cols].copy()
        
        # 순매수대금 억 단위 변환
        if '순매수거래대금' in result.columns:
            result['순매수(억)'] = result['순매수거래대금'] / 100000000
            result['순매수(억)'] = result['순매수(억)'].apply(lambda x: round(x, 1)) # float 유지 (정렬 위해)
        
        # top_n 필터링 (순매수 상위)
        if top_n:
            return result.head(top_n)
            
        return result
        
    except Exception as e:
        # 에러 발생 시 빈 데이터프레임 반환
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_leading_sectors(date, market="KOSPI", top_n=5):
    """
    Top-Down 분석: 외국인/기관 수급 주도 섹터 추출
    Returns: set(sector_names)
    """
    try:
        # 외국인 수급 상위
        df_foreign = get_market_net_purchases(date, market, "외국인", top_n=None)
        if not df_foreign.empty and 'Sector' in df_foreign.columns:
            # 섹터별 합산
            sector_foreign = df_foreign.groupby('Sector')['순매수거래대금'].sum().sort_values(ascending=False)
            top_foreign_sectors = set(sector_foreign.head(top_n).index)
        else:
            top_foreign_sectors = set()
            
        # 기관 수급 상위
        df_inst = get_market_net_purchases(date, market, "기관합계", top_n=None)
        if not df_inst.empty and 'Sector' in df_inst.columns:
            sector_inst = df_inst.groupby('Sector')['순매수거래대금'].sum().sort_values(ascending=False)
            top_inst_sectors = set(sector_inst.head(top_n).index)
        else:
            top_inst_sectors = set()
            
        # 빈 값 제거 및 합집합
        leading_sectors = (top_foreign_sectors | top_inst_sectors) - {''}
        return leading_sectors
        
    except Exception as e:
        return set()

@st.cache_data(ttl=600)
def get_global_indices(days=5):
    """
    주요 글로벌 지수 (NASDAQ, S&P500, SOX) 조회
    """
    indices = {
        "NASDAQ": "IXIC",
        "S&P500": "US500", 
        "SOX": "SOXX" # VanEck 반도체 ETF (SOX 지수 직접조회 불가 → ETF 대체)
    }
    
    result = {}
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    for name, symbol in indices.items():
        try:
            df = fdr.DataReader(symbol, start_date, end_date)
            if not df.empty:
                result[name] = df
        except:
            continue
            
    return result

@st.cache_data(ttl=600)
def get_sector_returns(date, market="KOSPI"):
    """
    Top-Down 분석: 섹터별 평균 등락률 계산
    Returns: pd.Series (Index: Sector, Value: 등락률 평균)
    """
    try:
        # 전 종목 시세 (등락률 포함)
        df_price = stock.get_market_ohlcv(date, market=market)
        
        # 종목 매핑 (Sector 정보)
        df_map = get_ticker_mapping()
        
        if df_price.empty or df_map.empty:
            return pd.Series()
            
        # Merge
        df_merged = df_price.join(df_map[['Sector']], how='inner')
        
        # 섹터별 평균 등락률 (거래량 가중 평균이 정확하지만, 단순 평균으로 트렌드 파악)
        sector_ret = df_merged.groupby('Sector')['등락률'].mean().sort_values(ascending=False)
        
        # 빈 섹터명 제거
        if '' in sector_ret.index:
            sector_ret = sector_ret.drop('')
            
        return sector_ret
        
    except Exception as e:
        return pd.Series()
