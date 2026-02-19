"""
KRX 실시간 데이터 모듈
- 장중(09:00~15:30): Naver Finance 스크래핑 (1순위) + KRX 직접 API (2순위)
- 장 마감 후(18:00+): pykrx fallback (data_fetcher.py에서 처리)
"""
import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import StringIO
from datetime import datetime, timedelta, timezone
import re

KST = timezone(timedelta(hours=9))


# ═══════════════════════════════════════
# 장중 여부 판별
# ═══════════════════════════════════════
def is_market_open():
    """현재 장중인지 판별 (KST 기준 평일 09:00~15:30)"""
    now = datetime.now(KST)
    if now.weekday() >= 5:
        return False
    hour, minute = now.hour, now.minute
    if hour < 9 or (hour == 15 and minute >= 30) or hour > 15:
        return False
    return True


def _now_kst():
    return datetime.now(KST)


# ═══════════════════════════════════════
# Naver Finance 스크래핑 (장중 실시간 — 1순위)
# ═══════════════════════════════════════
NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

NAVER_INVESTOR_MAP = {
    "외국인": "01",
    "기관합계": "02",
}


def _parse_naver_number(text):
    """네이버 숫자 문자열을 float으로 변환 (쉼표, +, - 처리)"""
    if not text:
        return 0
    text = str(text).strip().replace(",", "").replace("+", "")
    try:
        return float(text)
    except (ValueError, TypeError):
        return 0


def fetch_naver_investor_trading(investor="외국인"):
    """
    네이버증권 투자자별 매매상위 종목 (장중 실시간)
    BeautifulSoup으로 안정적 파싱

    URL: https://finance.naver.com/sise/sise_deal.naver?sosok={01|02}&type={buy|sell}
    테이블 구조: 종목명(링크포함) | 현재가 | 전일비 | 등락률 | 매도거래량 | 매수거래량 | 순매수거래량 | 거래량

    Returns: pykrx 호환 DataFrame
    """
    sosok = NAVER_INVESTOR_MAP.get(investor)
    if not sosok:
        return pd.DataFrame()

    all_records = []

    for trade_type in ["buy", "sell"]:
        url = f"https://finance.naver.com/sise/sise_deal.naver?sosok={sosok}&type={trade_type}"
        try:
            resp = requests.get(url, headers=NAVER_HEADERS, timeout=10)
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "lxml")

            # 데이터 테이블 찾기: class="type_5" 또는 "type2"
            table = soup.select_one("table.type_5, table.type2, table.type_1")
            if not table:
                # 모든 테이블 중에서 가장 행이 많은 테이블
                tables = soup.select("table")
                table = max(tables, key=lambda t: len(t.select("tr")), default=None)

            if not table:
                continue

            rows = table.select("tr")

            for row in rows:
                tds = row.select("td")
                if len(tds) < 4:
                    continue

                # 종목명과 코드 추출
                link = row.select_one("a[href*='code=']")
                if not link:
                    continue

                name = link.get_text(strip=True)
                href = link.get("href", "")
                code_match = re.search(r"code=(\d{6})", href)
                if not code_match:
                    continue
                code = code_match.group(1)

                # 숫자 데이터 추출 (td 요소들)
                nums = []
                for td in tds:
                    text = td.get_text(strip=True).replace(",", "").replace("+", "").replace("%", "")
                    # 종목명 td 건너뛰기
                    if td.select_one("a[href*='code=']"):
                        continue
                    try:
                        nums.append(float(text))
                    except (ValueError, TypeError):
                        nums.append(None)

                # nums 순서: [현재가, 전일비, 등락률, 매도거래량, 매수거래량, 순매수거래량, 거래량]
                # 또는: [순위, 현재가, 전일비, 등락률, ...]
                price = 0
                net_vol = 0
                change_pct = 0

                # 유효한 숫자만 필터
                valid_nums = [n for n in nums if n is not None]

                if len(valid_nums) >= 4:
                    # 첫 번째 큰 숫자가 현재가 (보통 수천~수십만)
                    # 마지막에서 두 번째가 순매수거래량
                    price = valid_nums[0] if valid_nums[0] and valid_nums[0] > 100 else (valid_nums[1] if len(valid_nums) > 1 else 0)
                    net_vol = valid_nums[-2] if len(valid_nums) >= 2 else 0

                if trade_type == "sell":
                    net_vol = -abs(net_vol) if net_vol else 0

                # 순매수거래대금 추정 (거래량 * 현재가)
                net_val = net_vol * price if price else 0

                all_records.append({
                    "종목코드": code,
                    "종목명": name,
                    "순매수거래량": int(net_vol),
                    "순매수거래대금": int(net_val),
                    "현재가": int(price) if price else 0,
                })

        except Exception as e:
            print(f"[Naver] Error ({investor}/{trade_type}): {e}")

    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    df = df.drop_duplicates(subset="종목코드", keep="first")
    df = df.set_index("종목코드")
    df = df.sort_values("순매수거래대금", ascending=False)

    return df


# ═══════════════════════════════════════
# KRX 직접 JSON API (2순위)
# ═══════════════════════════════════════
KRX_API_URL = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"

INVESTOR_CODE_MAP = {
    "금융투자": "1000", "보험": "2000", "투신": "3000",
    "사모": "3100", "은행": "4000", "기타금융": "5000",
    "연기금": "6000", "기관합계": "7050", "기타법인": "7100",
    "개인": "8000", "외국인": "9000", "기타외국인": "9001",
    "전체": "9999",
}

MARKET_CODE_MAP = {"KOSPI": "STK", "KOSDAQ": "KSQ", "ALL": "ALL"}

KRX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020303",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "X-Requested-With": "XMLHttpRequest",
}


def fetch_krx_investor_net_purchases(date_str, market="KOSPI", investor="외국인"):
    """KRX 직접 JSON API — 장중에는 빈 데이터 반환 가능 (18시 이후 확정)"""
    mkt_code = MARKET_CODE_MAP.get(market, "STK")
    inv_code = INVESTOR_CODE_MAP.get(investor, "9000")

    params = {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT02401",
        "locale": "ko_KR",
        "mktId": mkt_code, "invstTpCd": inv_code,
        "strtDd": date_str, "endDd": date_str,
        "share": "1", "money": "1", "csvxls_isNo": "false",
    }

    try:
        resp = requests.post(KRX_API_URL, data=params, headers=KRX_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if "output" not in data or not data["output"]:
            return pd.DataFrame()

        df = pd.DataFrame(data["output"])
        col_map = {
            "ISU_SRT_CD": "종목코드", "ISU_ABBRV": "종목명",
            "NETBID_TRDVAL": "순매수거래대금", "NETBID_TRDVOL": "순매수거래량",
            "TDD_CLSPRC": "종가", "FLUC_RT": "등락률", "CMPPREVDD_PRC": "대비",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        for col in ["순매수거래대금", "순매수거래량", "종가", "등락률", "대비"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")

        if "종목코드" in df.columns:
            df = df.set_index("종목코드")
        return df

    except Exception as e:
        print(f"[KRX API] Error: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════
# 통합 함수
# ═══════════════════════════════════════
def get_realtime_net_purchases(date_str, market="KOSPI", investor="외국인"):
    """
    실시간 투자자별 순매수 데이터
    1순위: Naver Finance (장중 확실)
    2순위: KRX 직접 API (마감 후)
    """
    # 1순위: Naver Finance
    if investor in ("외국인", "기관합계"):
        try:
            df = fetch_naver_investor_trading(investor)
            if df is not None and not df.empty:
                print(f"[Realtime] Naver 성공: {investor} {len(df)}종목")
                return df
        except Exception as e:
            print(f"[Realtime] Naver 실패: {e}")

    # 2순위: KRX API
    try:
        df = fetch_krx_investor_net_purchases(date_str, market, investor)
        if df is not None and not df.empty:
            print(f"[Realtime] KRX 성공: {investor} {len(df)}종목")
            return df
    except Exception as e:
        print(f"[Realtime] KRX 실패: {e}")

    return pd.DataFrame()
