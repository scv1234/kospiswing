"""
KRX 실시간 데이터 모듈
- 장중(09:00~15:30): KRX 직접 API + Naver Finance fallback
- pykrx가 오후 6시 이후에만 당일 데이터를 제공하는 한계를 극복
"""
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta, timezone
import time

KST = timezone(timedelta(hours=9))

# ═══════════════════════════════════════
# 장중 여부 판별
# ═══════════════════════════════════════
def is_market_open():
    """현재 장중인지 판별 (KST 기준 평일 09:00~15:30)"""
    now = datetime.now(KST)
    if now.weekday() >= 5:  # 주말
        return False
    hour, minute = now.hour, now.minute
    if hour < 9 or (hour == 15 and minute >= 30) or hour > 15:
        return False
    return True


def _now_kst():
    return datetime.now(KST)


# ═══════════════════════════════════════
# KRX 직접 JSON API (pykrx 내부 엔드포인트)
# ═══════════════════════════════════════
KRX_API_URL = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"

# 투자자 유형 코드 매핑
INVESTOR_CODE_MAP = {
    "금융투자": "1000",
    "보험": "2000",
    "투신": "3000",
    "사모": "3100",
    "은행": "4000",
    "기타금융": "5000",
    "연기금": "6000",
    "기관합계": "7050",
    "기타법인": "7100",
    "개인": "8000",
    "외국인": "9000",
    "기타외국인": "9001",
    "전체": "9999",
}

# 시장 코드 매핑
MARKET_CODE_MAP = {
    "KOSPI": "STK",
    "KOSDAQ": "KSQ",
    "ALL": "ALL",
}

KRX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020303",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "X-Requested-With": "XMLHttpRequest",
}


def fetch_krx_investor_net_purchases(date_str, market="KOSPI", investor="외국인"):
    """
    KRX 직접 JSON API로 투자자별 순매수 상위종목 조회
    pykrx 내부와 동일한 엔드포인트 사용 (bld=MDCSTAT02401)
    장중에도 데이터 반환 가능

    Returns: DataFrame with columns [종목코드, 종목명, 순매수거래대금, 순매수거래량, ...]
    """
    mkt_code = MARKET_CODE_MAP.get(market, "STK")
    inv_code = INVESTOR_CODE_MAP.get(investor, "9000")

    params = {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT02401",
        "locale": "ko_KR",
        "mktId": mkt_code,
        "invstTpCd": inv_code,
        "strtDd": date_str,
        "endDd": date_str,
        "share": "1",
        "money": "1",
        "csvxls_isNo": "false",
    }

    try:
        resp = requests.post(KRX_API_URL, data=params, headers=KRX_HEADERS, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        if "output" not in data or not data["output"]:
            return pd.DataFrame()

        df = pd.DataFrame(data["output"])

        # 컬럼명 정리 (KRX JSON 응답 컬럼)
        col_map = {
            "ISU_SRT_CD": "종목코드",
            "ISU_ABBRV": "종목명",
            "NETBID_TRDVAL": "순매수거래대금",
            "NETBID_TRDVOL": "순매수거래량",
            "TDD_CLSPRC": "종가",
            "FLUC_RT": "등락률",
            "CMPPREVDD_PRC": "대비",
        }

        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        # 숫자 컬럼 변환 (쉼표 제거)
        numeric_cols = ["순매수거래대금", "순매수거래량", "종가", "등락률", "대비"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")

        # 종목코드를 인덱스로
        if "종목코드" in df.columns:
            df = df.set_index("종목코드")

        return df

    except Exception as e:
        print(f"[KRX Direct API] Error: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════
# KRX OTP 방식 (CSV 다운로드) - 백업용
# ═══════════════════════════════════════
def fetch_krx_investor_net_purchases_csv(date_str, market="KOSPI", investor="외국인"):
    """
    KRX OTP 방식으로 투자자별 순매수 상위종목 CSV 다운로드
    JSON API가 실패할 경우 fallback
    """
    mkt_code = MARKET_CODE_MAP.get(market, "STK")
    inv_code = INVESTOR_CODE_MAP.get(investor, "9000")

    try:
        # Step 1: OTP 발급
        gen_url = "https://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd"
        gen_data = {
            "locale": "ko_KR",
            "mktId": mkt_code,
            "invstTpCd": inv_code,
            "strtDd": date_str,
            "endDd": date_str,
            "share": "1",
            "money": "1",
            "csvxls_isNo": "false",
            "name": "fileDown",
            "url": "dbms/MDC/STAT/standard/MDCSTAT02401",
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020303",
        }

        otp_resp = requests.post(gen_url, data=gen_data, headers=headers, timeout=10)
        otp = otp_resp.text

        # Step 2: CSV 다운로드
        down_url = "https://data.krx.co.kr/comm/fileDn/download_csv/download.cmd"
        csv_resp = requests.post(down_url, data={"code": otp}, headers=headers, timeout=15)

        # EUC-KR로 디코딩
        df = pd.read_csv(BytesIO(csv_resp.content), encoding="EUC-KR")

        if df.empty:
            return pd.DataFrame()

        # 컬럼명 정리
        col_map = {
            "종목코드": "종목코드",
            "종목명": "종목명",
            "순매수거래대금": "순매수거래대금",
            "순매수거래량": "순매수거래량",
        }

        if "종목코드" in df.columns:
            df = df.set_index("종목코드")

        return df

    except Exception as e:
        print(f"[KRX CSV API] Error: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════
# Naver Finance 스크래핑 (장중 실시간 확실)
# ═══════════════════════════════════════
NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def fetch_naver_investor_by_stock(code, pages=1):
    """
    네이버증권 종목별 외국인/기관 순매매 데이터
    URL: https://finance.naver.com/item/frgn.naver?code={code}
    장중 실시간 데이터 제공
    """
    url = f"https://finance.naver.com/item/frgn.naver?code={code}&page=1"
    try:
        dfs = pd.read_html(url, encoding="euc-kr")
        if dfs:
            df = dfs[0].dropna(how="all")
            return df
    except Exception as e:
        print(f"[Naver] Error for {code}: {e}")
    return pd.DataFrame()


def fetch_naver_sise_investor_top(investor_type="foreign"):
    """
    네이버증권 투자자별 매매상위 종목 (장중 실시간)
    investor_type: "foreign" (외국인), "institution" (기관), "individual" (개인)

    URL patterns:
    - 외국인 매매상위: https://finance.naver.com/sise/sise_deal.naver?sosok=01&type=buy (순매수), sell (순매도)
    - 기관 매매상위: https://finance.naver.com/sise/sise_deal.naver?sosok=02&type=buy
    - 전체 투자자별: https://finance.naver.com/sise/investorDealTrendDay.naver
    """
    # sosok: 01=외국인, 02=기관, 00=개인은 별도 처리
    sosok_map = {
        "foreign": "01",
        "외국인": "01",
        "institution": "02",
        "기관합계": "02",
    }

    sosok = sosok_map.get(investor_type, "01")

    results = []

    for trade_type in ["buy", "sell"]:
        url = f"https://finance.naver.com/sise/sise_deal.naver?sosok={sosok}&type={trade_type}"
        try:
            dfs = pd.read_html(url, encoding="euc-kr", header=0)
            for df in dfs:
                df = df.dropna(how="all")
                if len(df) > 1:
                    df["매매구분"] = "순매수" if trade_type == "buy" else "순매도"
                    results.append(df)
        except Exception as e:
            print(f"[Naver sise_deal] Error ({trade_type}): {e}")

    if results:
        return pd.concat(results, ignore_index=True)
    return pd.DataFrame()


# ═══════════════════════════════════════
# 통합 실시간 데이터 함수
# ═══════════════════════════════════════
def get_realtime_net_purchases(date_str, market="KOSPI", investor="외국인"):
    """
    실시간 투자자별 순매수 데이터 (장중/마감 자동 분기)

    시도 순서:
    1. KRX 직접 JSON API (가장 정확)
    2. KRX CSV OTP 방식 (JSON 실패 시)
    3. Naver Finance 스크래핑 (최후 fallback)

    Returns: DataFrame (pykrx 호환 형식)
    """
    # 1순위: KRX JSON API
    df = fetch_krx_investor_net_purchases(date_str, market, investor)
    if df is not None and not df.empty:
        return df

    # 2순위: KRX CSV
    df = fetch_krx_investor_net_purchases_csv(date_str, market, investor)
    if df is not None and not df.empty:
        return df

    # 3순위: Naver Finance (외국인/기관만 지원)
    if investor in ("외국인", "기관합계"):
        df = fetch_naver_sise_investor_top(investor)
        if df is not None and not df.empty:
            return df

    return pd.DataFrame()
