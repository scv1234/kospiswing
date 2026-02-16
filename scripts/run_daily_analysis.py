"""
GitHub Actions용 독립 실행 스크립트
Streamlit 의존성 없이 스윙 분석 + 탑다운 리포트를 실행하고 Supabase에 저장합니다.

사용법:
  python scripts/run_daily_analysis.py

환경변수 필요:
  SUPABASE_URL, SUPABASE_KEY
"""
import sys
import os
import json
import time
import concurrent.futures
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# 프로젝트 루트를 path에 추가
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

# .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT_DIR, '.env'))
except ImportError:
    pass

from pykrx import stock

# backend/utils 사용 (Streamlit 의존성 없음)
sys.path.insert(0, os.path.join(ROOT_DIR, 'backend'))
from utils.data_fetcher import (
    get_latest_business_day, get_kospi_chart_data, get_exchange_rate_data,
    get_market_net_purchases, get_leading_sectors, get_global_indices,
    get_sector_returns, get_ticker_mapping
)


# ═══════════════════════════════════════
# Supabase 클라이언트 (Streamlit 없이)
# ═══════════════════════════════════════
def get_db_client():
    """Supabase 클라이언트 생성 (환경변수만 사용)"""
    try:
        from supabase import create_client
    except ImportError:
        print("[ERROR] supabase 패키지 없음. pip install supabase")
        return None

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("[ERROR] SUPABASE_URL 또는 SUPABASE_KEY 환경변수가 설정되지 않았습니다.")
        return None

    return create_client(url, key)


def save_swing_results(client, target_date: str, df_result: pd.DataFrame, top_picks: list):
    """스윙 분석 결과를 Supabase에 저장"""
    try:
        # DataFrame → JSON 직렬화 가능하게 변환
        records = df_result.copy()
        # 태그 리스트를 문자열로
        if '태그' in records.columns:
            records['태그'] = records['태그'].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else str(x))

        data = {
            "target_date": target_date,
            "result_type": "swing",
            "results_json": records.to_json(orient='records', force_ascii=False),
            "top_picks_json": json.dumps(top_picks, ensure_ascii=False, default=str),
            "stock_count": len(df_result),
        }

        client.table("analysis_results").upsert(
            data, on_conflict="target_date,result_type"
        ).execute()

        print(f"[OK] 스윙 분석 결과 저장 완료 ({len(df_result)}개 종목)")
        return True
    except Exception as e:
        print(f"[ERROR] 스윙 결과 저장 실패: {e}")
        return False


def save_topdown_report(client, target_date: str, report_content: str):
    """탑다운 리포트를 Supabase에 저장"""
    try:
        data = {
            "target_date": target_date,
            "report_type": "topdown",
            "content": report_content,
        }
        client.table("reports").upsert(
            data, on_conflict="target_date,report_type"
        ).execute()
        print(f"[OK] 탑다운 리포트 저장 완료")
        return True
    except Exception as e:
        print(f"[ERROR] 리포트 저장 실패: {e}")
        return False


# ═══════════════════════════════════════
# 스윙 분석 (Streamlit 의존성 제거 버전)
# ═══════════════════════════════════════
def run_swing_analysis_standalone():
    """Streamlit 없이 동작하는 스윙 분석"""
    target_date = get_latest_business_day()
    print(f"[INFO] 분석 기준일: {target_date}")

    start_90d = (datetime.strptime(target_date, "%Y%m%d") - timedelta(days=120)).strftime("%Y%m%d")

    # 수급 데이터
    try:
        df_foreign = stock.get_market_net_purchases_of_equities(target_date, target_date, "KOSPI", "외국인")
        df_inst = stock.get_market_net_purchases_of_equities(target_date, target_date, "KOSPI", "기관합계")
        df_indi = stock.get_market_net_purchases_of_equities(target_date, target_date, "KOSPI", "개인")

        if df_foreign.empty or df_inst.empty:
            print(f"[ERROR] 수급 데이터 비어있음 (Date: {target_date})")
            return pd.DataFrame(), [], target_date

        foreign_buy = set(df_foreign[df_foreign["순매수거래량"] > 0].index)
        inst_buy = set(df_inst[df_inst["순매수거래량"] > 0].index)
        indi_sell = set(df_indi[df_indi["순매수거래량"] < 0].index)

        top_foreign = set(df_foreign.sort_values('순매수거래대금', ascending=False).head(50).index)
        top_inst = set(df_inst.sort_values('순매수거래대금', ascending=False).head(50).index)
        target_tickers = list(top_foreign | top_inst)

        print(f"[INFO] 1차 선별: {len(target_tickers)}개 종목")

    except Exception as e:
        print(f"[ERROR] 수급 데이터 조회 실패: {e}")
        return pd.DataFrame(), [], target_date

    # 펀더멘털 & 섹터
    try:
        df_fund = stock.get_market_fundamental(target_date, market="KOSPI")
    except:
        df_fund = pd.DataFrame()

    try:
        leading_sectors = get_leading_sectors(target_date, "KOSPI")
        ticker_map = get_ticker_mapping()
    except:
        leading_sectors = set()
        ticker_map = pd.DataFrame()

    results = []

    def analyze_ticker(ticker):
        try:
            name = stock.get_market_ticker_name(ticker)
            sector = ""
            if not ticker_map.empty and ticker in ticker_map.index:
                sector = ticker_map.loc[ticker, 'Sector']

            df_price = stock.get_market_ohlcv(start_90d, target_date, ticker)
            if df_price is None or len(df_price) < 30:
                return None

            close = df_price["종가"].iloc[-1]
            vol_today = df_price["거래량"].iloc[-1]
            vol_ma20 = df_price["거래량"].rolling(20).mean().iloc[-1]
            vol_ratio = vol_today / vol_ma20 if vol_ma20 > 0 else 0

            ma5 = df_price["종가"].rolling(5).mean().iloc[-1]
            ma20 = df_price["종가"].rolling(20).mean().iloc[-1]
            ma60 = df_price["종가"].rolling(60).mean().iloc[-1]
            golden_cross = (ma5 > ma20 > ma60)

            delta = df_price["종가"].diff()
            up, down = delta.copy(), delta.copy()
            up[up < 0] = 0
            down[down > 0] = 0
            _gain = up.ewm(com=13, min_periods=14).mean()
            _loss = down.abs().ewm(com=13, min_periods=14).mean()
            rs = _gain / _loss
            rsi = 100 - (100 / (1 + rs))
            rsi_val = rsi.iloc[-1]

            tags = []

            # [A] Top-Down 섹터 (0~8점)
            sector_score = 0.0
            sector_comments = []
            if sector and sector in leading_sectors:
                sector_score = 8.0
                tags.append("주도섹터")
                sector_comments.append(f"현재 시장 주도 업종인 '{sector}' 섹터에 포함.")

            # [B] 수급 (0~30점)
            supply_score = 0.0
            supply_comments = []
            f_amount = df_foreign.loc[ticker, '순매수거래대금'] if ticker in df_foreign.index else 0
            i_amount = df_inst.loc[ticker, '순매수거래대금'] if ticker in df_inst.index else 0

            is_foreign_buy = ticker in foreign_buy
            is_inst_buy = ticker in inst_buy

            if is_foreign_buy and is_inst_buy:
                combined = abs(f_amount) + abs(i_amount)
                supply_score = 20.0 + min(10.0, np.log1p(combined / 1e8) * 1.5)
                tags.append("쌍끌이")
                supply_comments.append(f"외국인({f_amount/1e8:+,.0f}억) + 기관({i_amount/1e8:+,.0f}억) 동시 매집.")
            elif is_foreign_buy:
                supply_score = 12.0 + min(6.0, np.log1p(abs(f_amount) / 1e8) * 1.2)
                tags.append("외인수급")
                supply_comments.append(f"외국인 {f_amount/1e8:+,.0f}억원 순매수.")
            elif is_inst_buy:
                supply_score = 12.0 + min(6.0, np.log1p(abs(i_amount) / 1e8) * 1.2)
                tags.append("기관수급")
                supply_comments.append(f"기관 {i_amount/1e8:+,.0f}억원 순매수.")

            if ticker in indi_sell:
                supply_score += 5.0
                tags.append("개인매도")

            # [C] 기술적 (0~30점)
            tech_score = 0.0
            tech_comments = []
            open_p = df_price["시가"].iloc[-1]
            body_len = abs(close - open_p)
            upper_tail = df_price["고가"].iloc[-1] - max(close, open_p)
            daily_chg = (close - df_price['종가'].iloc[-2]) / df_price['종가'].iloc[-2] * 100

            if daily_chg > 5 and body_len > upper_tail * 2:
                tech_score += 3.0
                tech_comments.append("장대양봉 출현.")
            elif daily_chg > 2 and close > open_p:
                tech_score += 1.5

            if golden_cross:
                spread = (close - ma60) / ma60 * 100 if ma60 > 0 else 0
                tech_score += 7.0 + min(3.0, max(0, spread * 0.3))
                tags.append("정배열")
                tech_comments.append(f"정배열 확산 중 (60일선 대비 +{spread:.1f}%).")
            elif close > ma20 and ma5 > ma20:
                tech_score += 4.0
            elif close > ma20:
                tech_score += 2.0

            if vol_ratio >= 1.2:
                tech_score += min(12.0, 3.0 + (vol_ratio - 1.2) * 11.25)
                if vol_ratio >= 1.5:
                    tags.append(f"거래량급증({vol_ratio:.1f}배)")
                    tech_comments.append(f"거래량 {vol_ratio:.1f}배 폭증.")

            rsi_optimal_center = 45.0
            rsi_score = max(0, 8.0 - abs(rsi_val - rsi_optimal_center) * 0.2)
            tech_score += rsi_score
            if 30 <= rsi_val <= 45:
                tags.append(f"RSI눌림목({rsi_val:.0f})")

            # [D] 모멘텀 (0~12점)
            momentum_score = 0.0
            if len(df_price) >= 5:
                ret_5d = (close - df_price['종가'].iloc[-5]) / df_price['종가'].iloc[-5] * 100
                momentum_score += min(6.0, max(0, ret_5d * 0.8))
            if len(df_price) >= 20:
                ret_20d = (close - df_price['종가'].iloc[-20]) / df_price['종가'].iloc[-20] * 100
                momentum_score += min(6.0, max(0, ret_20d * 0.4))

            # [E] 펀더멘털 (0~10점)
            fund_score = 0.0
            pbr = df_fund.loc[ticker, "PBR"] if ticker in df_fund.index else 0
            div_yield = df_fund.loc[ticker, "DIV"] if ticker in df_fund.index else 0
            if 0 < pbr < 1.5:
                fund_score = max(0, 10.0 - pbr * 6.67)
                if pbr < 1.0:
                    tags.append(f"PBR{pbr:.1f}")

            # [F] 가격 위치 (0~10점)
            position_score = 0.0
            ma20_gap = (close - ma20) / ma20 * 100 if ma20 > 0 else 0
            if 0 < ma20_gap <= 5:
                position_score += min(5.0, ma20_gap * 1.5)
            elif ma20_gap > 5:
                position_score += max(0, 5.0 - (ma20_gap - 5) * 0.5)

            high_60d = df_price['고가'].rolling(60).max().iloc[-1]
            if high_60d > 0:
                from_high = (close / high_60d) * 100
                if from_high >= 95:
                    position_score += 5.0
                    tags.append("고점돌파임박")
                elif from_high >= 85:
                    position_score += 3.0 + (from_high - 85) * 0.2

            # 종합
            raw_score = sector_score + supply_score + tech_score + momentum_score + fund_score + position_score
            score = round(min(100.0, raw_score), 1)

            final_comments = sector_comments + supply_comments + tech_comments
            full_reason = " ".join(final_comments) or "수급과 차트 흐름이 양호한 종목입니다."

            # ATR 기반 목표/손절
            high_low = df_price['고가'] - df_price['저가']
            high_close = np.abs(df_price['고가'] - df_price['종가'].shift())
            low_close = np.abs(df_price['저가'] - df_price['종가'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]

            atr_stop = int(close - (atr * 2.0))
            ma_stop = int(ma20)
            stop_candidates = [p for p in [atr_stop, ma_stop] if p < close]
            stop_loss = max(stop_candidates) if stop_candidates else int(close * 0.95)

            risk = close - stop_loss
            target_price = int(close + (risk * 2.0))
            if (target_price - close) / close < 0.05:
                target_price = int(close * 1.05)

            target_rate = round((target_price - close) / close * 100, 1)
            stop_rate = round((stop_loss - close) / close * 100, 1)

            if score >= 20:
                return {
                    "종목명": name, "현재가": close,
                    "등락률": round(daily_chg, 2),
                    "스윙점수": score, "추천사유": full_reason,
                    "태그": tags,
                    "목표가": target_price, "목표수익률": target_rate,
                    "손절가": stop_loss, "손절수익률": stop_rate,
                    "PBR": pbr, "배당수익률": div_yield,
                    "Code": ticker, "RSI": round(rsi_val, 1),
                    "Sector": sector
                }
            return None
        except Exception as e:
            return None

    # 병렬 실행
    print(f"[INFO] {len(target_tickers)}개 종목 심층 분석 시작...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(analyze_ticker, t): t for t in target_tickers}
        done = 0
        for future in concurrent.futures.as_completed(futures):
            data = future.result()
            if data and "error" not in data:
                results.append(data)
            done += 1
            if done % 10 == 0:
                print(f"  ... {done}/{len(target_tickers)} 완료")

    if not results:
        print("[WARN] 분석 결과 0건")
        return pd.DataFrame(), [], target_date

    df_result = pd.DataFrame(results).sort_values("스윙점수", ascending=False)
    top_picks = df_result.head(3).to_dict('records')

    print(f"[OK] 스윙 분석 완료: {len(df_result)}개 종목, TOP3: {[p['종목명'] for p in top_picks]}")
    return df_result, top_picks, target_date


# ═══════════════════════════════════════
# 탑다운 리포트 생성 (Streamlit 없이)
# ═══════════════════════════════════════
def generate_topdown_report_standalone(target_date):
    """report_generator.py와 동일하지만 Streamlit 없이 동작"""
    # backend/utils의 report_generator는 Streamlit 의존성 없음
    # 하지만 utils/report_generator.py는 있으므로 그걸 직접 호출
    sys.path.insert(0, ROOT_DIR)

    # report_generator 내부에서 streamlit을 import하지 않도록 우회
    # utils/report_generator.py는 data_fetcher만 사용하므로 OK
    from utils.report_generator import generate_topdown_report
    report_text, filename, storage_info = generate_topdown_report(target_date)
    return report_text


# ═══════════════════════════════════════
# 메인 실행
# ═══════════════════════════════════════
def main():
    print("=" * 50)
    print(f"📊 일일 자동 분석 시작 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    client = get_db_client()
    if not client:
        print("[FATAL] Supabase 연결 실패. 종료합니다.")
        sys.exit(1)

    # 1. 스윙 분석
    print("\n[STEP 1] 스윙 트레이딩 분석...")
    start = time.time()
    df_result, top_picks, target_date = run_swing_analysis_standalone()
    elapsed = time.time() - start
    print(f"  소요 시간: {elapsed:.1f}초")

    if not df_result.empty:
        save_swing_results(client, target_date, df_result, top_picks)

    # 2. 탑다운 리포트
    print("\n[STEP 2] 탑다운 리포트 생성...")
    start = time.time()
    try:
        report_text = generate_topdown_report_standalone(target_date)
        if report_text and not report_text.startswith("리포트 생성 중 오류"):
            save_topdown_report(client, target_date, report_text)
        else:
            print(f"[WARN] 리포트 생성 실패: {report_text[:100] if report_text else 'None'}")
    except Exception as e:
        print(f"[ERROR] 리포트 생성 중 오류: {e}")
    elapsed = time.time() - start
    print(f"  소요 시간: {elapsed:.1f}초")

    print("\n" + "=" * 50)
    print("✅ 일일 분석 완료!")
    print("=" * 50)


if __name__ == "__main__":
    main()
