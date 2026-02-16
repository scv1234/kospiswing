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

            # ATR 기반 목표/손절 (코멘트에서 참조하므로 먼저 계산)
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

            # ═══ 종합 AI 분석 코멘트 생성 (상세 버전) ═══
            ret_5d = (close - df_price['종가'].iloc[-5]) / df_price['종가'].iloc[-5] * 100 if len(df_price) >= 5 else 0
            ret_20d = (close - df_price['종가'].iloc[-20]) / df_price['종가'].iloc[-20] * 100 if len(df_price) >= 20 else 0
            is_indi_sell = ticker in indi_sell

            # ── 1. 종합 판정 헤더 ──
            if score >= 60:
                grade = "매우 강력한 매수 시그널"
                grade_desc = "수급, 기술적 분석, 펀더멘털 모두 긍정적이며, 단기 스윙 트레이딩에 최적의 타이밍입니다."
            elif score >= 45:
                grade = "강한 매수 시그널"
                grade_desc = "주요 지표들이 상승을 지지하고 있으며, 리스크 대비 기대수익이 우수합니다."
            elif score >= 30:
                grade = "관심 종목 (조건부 매수)"
                grade_desc = "일부 지표가 긍정적이나, 추가 확인이 필요한 구간입니다. 분할 매수를 권장합니다."
            else:
                grade = "모니터링 단계"
                grade_desc = "아직 확실한 시그널이 형성되지 않았으나, 추세 전환 시 빠르게 진입할 수 있도록 관찰이 필요합니다."

            sections = []
            sections.append(f"**[{grade}]** {grade_desc}")

            # ── 2. 섹터 분석 ──
            if sector_comments:
                sections.append(f"\n**▶ 섹터 분석 ({sector_score:.0f}점)**: {' '.join(sector_comments)} 시장의 자금 흐름이 해당 업종으로 집중되고 있어, 업종 내 다른 종목 대비 초과 수익이 기대됩니다.")
            elif sector:
                sections.append(f"\n**▶ 섹터 분석**: '{sector}' 업종에 속해 있으나, 현재 수급 주도 섹터에는 포함되지 않았습니다. 개별 종목의 모멘텀에 집중할 필요가 있습니다.")

            # ── 3. 수급 분석 ──
            supply_detail = f"\n**▶ 수급 분석 ({supply_score:.1f}점)**: "
            if is_foreign_buy and is_inst_buy:
                supply_detail += f"외국인({f_amount/1e8:+,.0f}억)과 기관({i_amount/1e8:+,.0f}억)이 동시에 순매수하는 '쌍끌이' 패턴이 확인되었습니다. 이는 대형 투자 주체들이 동시에 이 종목에 확신을 갖고 진입하고 있다는 강력한 시그널입니다."
                if is_indi_sell:
                    supply_detail += " 동시에 개인 투자자가 매도하고 있어, 전형적인 '세력 매집 → 개인 이탈' 구조가 형성되었습니다. 역사적으로 이 패턴은 단기 상승 확률이 높습니다."
            elif is_foreign_buy:
                supply_detail += f"외국인이 {f_amount/1e8:+,.0f}억원을 순매수하고 있습니다. 외국인은 글로벌 자금 흐름과 환율을 고려하여 움직이기 때문에, 이들의 매수세는 중장기 상승의 선행 지표로 작용하는 경우가 많습니다."
                if is_indi_sell:
                    supply_detail += " 개인 매도 물량을 외국인이 흡수하며 수급 개선이 진행 중입니다."
            elif is_inst_buy:
                supply_detail += f"기관이 {i_amount/1e8:+,.0f}억원을 순매수하고 있습니다. 기관은 리서치 기반으로 투자하기 때문에, 펀더멘털 개선이나 실적 모멘텀을 선반영하고 있을 가능성이 높습니다."
                if is_indi_sell:
                    supply_detail += " 개인 물량을 기관이 받아내는 긍정적 손바뀜이 진행 중입니다."
            else:
                supply_detail += "당일 뚜렷한 수급 주체가 확인되지 않았습니다. 기술적 지표 위주로 판단하는 것이 적절합니다."
            sections.append(supply_detail)

            # ── 4. 기술적 분석 ──
            tech_detail = f"\n**▶ 기술적 분석 ({tech_score:.1f}점)**:\n"
            tech_items = []

            if golden_cross:
                spread = (close - ma60) / ma60 * 100 if ma60 > 0 else 0
                tech_items.append(f"• **이동평균선 정배열**: 5일선({ma5:,.0f}) > 20일선({ma20:,.0f}) > 60일선({ma60:,.0f})으로 완벽한 정배열 상태입니다. 60일선 대비 +{spread:.1f}% 이격되어 있으며, 이는 중기 상승 추세가 건재함을 의미합니다.")
            elif close > ma20 and ma5 > ma20:
                tech_items.append(f"• **골든크로스 임박**: 5일선({ma5:,.0f})이 20일선({ma20:,.0f}) 위에 위치하며 상향 추세를 형성하고 있습니다. 60일선({ma60:,.0f}) 돌파 시 본격적인 상승 추세로 전환될 수 있습니다.")
            elif close > ma20:
                tech_items.append(f"• **20일선 지지**: 현재가({close:,}원)가 20일 이동평균선({ma20:,.0f}원) 위에 있어 단기 지지가 유효합니다.")
            else:
                tech_items.append(f"• **이동평균선**: 현재가({close:,}원)가 20일선({ma20:,.0f}원) 하단에 위치해 있어, 이평선 회복 여부를 주시해야 합니다.")

            if vol_ratio >= 2.0:
                tech_items.append(f"• **거래량 폭증**: 20일 평균 대비 {vol_ratio:.1f}배로 거래량이 폭발적으로 증가했습니다. 이는 새로운 매수세가 대거 유입되고 있음을 의미하며, 추세 전환 또는 강화의 강력한 신호입니다.")
            elif vol_ratio >= 1.5:
                tech_items.append(f"• **거래량 급증**: 20일 평균 대비 {vol_ratio:.1f}배의 거래량이 발생했습니다. 평소보다 높은 거래 참여도는 가격 방향성에 대한 시장의 확신을 반영합니다.")
            elif vol_ratio >= 1.2:
                tech_items.append(f"• **거래량 소폭 증가**: 20일 평균 대비 {vol_ratio:.1f}배로 다소 활발한 거래가 이루어지고 있습니다.")
            else:
                tech_items.append(f"• **거래량**: 20일 평균 대비 {vol_ratio:.1f}배로 평이한 수준입니다. 거래량 동반 없는 상승은 지속성에 의문이 있을 수 있습니다.")

            if rsi_val <= 30:
                tech_items.append(f"• **RSI {rsi_val:.0f} (과매도)**: 극단적 과매도 영역에 진입하여 기술적 반등 가능성이 높습니다. 다만, 추세적 하락 중 과매도가 지속될 수 있으므로 거래량 반등을 동반하는지 확인이 필요합니다.")
            elif rsi_val <= 45:
                tech_items.append(f"• **RSI {rsi_val:.0f} (눌림목)**: 과매도 구간을 벗어나 반등을 모색하는 '눌림목' 구간입니다. 스윙 트레이딩의 교과서적인 매수 타이밍에 해당하며, 리스크 대비 기대수익이 높은 구간입니다.")
            elif rsi_val <= 60:
                tech_items.append(f"• **RSI {rsi_val:.0f} (중립~강세)**: 과열 없이 건전한 상승 추세를 유지하고 있습니다. 추가 상승 여력이 충분한 구간입니다.")
            elif rsi_val <= 75:
                tech_items.append(f"• **RSI {rsi_val:.0f} (강세)**: 강한 상승 모멘텀이 유지되고 있으나, 70 이상에서는 차익실현 매물이 나올 수 있어 분할 매수/매도 전략이 권장됩니다.")
            else:
                tech_items.append(f"• **RSI {rsi_val:.0f} (과매수 주의)**: RSI가 75를 넘어 과매수 영역에 진입했습니다. 단기적으로 조정 가능성이 있으며, 신규 진입보다는 기존 보유자의 일부 차익실현이 적절할 수 있습니다.")

            if daily_chg > 5 and body_len > upper_tail * 2:
                tech_items.append(f"• **캔들 패턴 (장대양봉)**: 전일 대비 +{daily_chg:.1f}% 상승하며 강한 장대양봉이 형성되었습니다. 매수세가 장중 내내 지속되었음을 의미하며, 향후 추가 상승 모멘텀이 기대됩니다.")
            elif daily_chg > 2 and close > open_p:
                tech_items.append(f"• **캔들 패턴 (양봉)**: 전일 대비 +{daily_chg:.1f}% 상승하며 안정적인 양봉이 형성되었습니다.")
            elif upper_tail > body_len * 2 and daily_chg > 0:
                tech_items.append(f"• **캔들 패턴 (윗꼬리)**: 장중 매물대를 테스트했으나 소화 과정으로 보이며, 돌파 시도가 진행 중입니다.")

            tech_detail += "\n".join(tech_items)
            sections.append(tech_detail)

            # ── 5. 모멘텀 분석 ──
            momentum_detail = f"\n**▶ 모멘텀 분석 ({momentum_score:.1f}점)**: "
            if ret_5d > 5 and ret_20d > 10:
                momentum_detail += f"5일 수익률 +{ret_5d:.1f}%, 20일 수익률 +{ret_20d:.1f}%로 단기·중기 모멘텀이 모두 매우 강합니다. 상승 추세가 가속화되고 있으며, 추세 추종 매매에 유리합니다."
            elif ret_5d > 3:
                momentum_detail += f"5일 수익률 +{ret_5d:.1f}%로 단기 모멘텀이 양호합니다. 20일 수익률은 {ret_20d:+.1f}%입니다."
            elif ret_5d > 0:
                momentum_detail += f"5일 수익률 +{ret_5d:.1f}%, 20일 수익률 {ret_20d:+.1f}%로 완만한 상승세를 보이고 있습니다."
            else:
                momentum_detail += f"5일 수익률 {ret_5d:+.1f}%로 단기 조정 국면입니다. 20일 수익률({ret_20d:+.1f}%)을 감안하면 눌림목 매수 기회일 수 있습니다."
            sections.append(momentum_detail)

            # ── 6. 펀더멘털 ──
            fund_detail = f"\n**▶ 펀더멘털 ({fund_score:.1f}점)**: "
            if pbr > 0:
                if pbr < 0.7:
                    fund_detail += f"PBR {pbr:.2f}배로 자산가치 대비 심하게 저평가되어 있습니다. 청산가치보다 시가총액이 낮은 상태로, 하방 경직성이 매우 높습니다."
                elif pbr < 1.0:
                    fund_detail += f"PBR {pbr:.2f}배로 자산가치 대비 저평가 영역입니다. 가치투자 관점에서도 매력적인 구간입니다."
                elif pbr < 2.0:
                    fund_detail += f"PBR {pbr:.2f}배로 적정 수준입니다."
                else:
                    fund_detail += f"PBR {pbr:.2f}배로 다소 높은 밸류에이션입니다. 성장성이 뒷받침되는지 확인이 필요합니다."
            else:
                fund_detail += "PBR 데이터를 확인할 수 없습니다."
            if div_yield > 0:
                fund_detail += f" 배당수익률 {div_yield:.1f}%로 {'매력적인 배당 수익' if div_yield >= 3 else '소폭의 배당 수익'}이 추가됩니다."
            sections.append(fund_detail)

            # ── 7. 가격 위치 & 매매 전략 ──
            strategy = f"\n**▶ 매매 전략**: "
            strategy += f"목표가 {target_price:,}원(+{target_rate:.1f}%), 손절가 {stop_loss:,}원({stop_rate:.1f}%)으로 "
            rr_ratio = abs(target_rate / stop_rate) if stop_rate != 0 else 0
            strategy += f"손익비 1:{rr_ratio:.1f}입니다. "

            if high_60d > 0:
                if from_high >= 95:
                    strategy += f"현재 60일 고점({high_60d:,.0f}원) 대비 {from_high:.0f}% 수준으로 고점 돌파를 시도하고 있어, 돌파 시 급등 가능성이 있습니다. "
                elif from_high >= 85:
                    strategy += f"60일 고점({high_60d:,.0f}원) 대비 {from_high:.0f}% 수준으로 고점까지 여유가 있어 추가 상승 여력이 충분합니다. "

            if ma20_gap > 0:
                strategy += f"20일선 대비 +{ma20_gap:.1f}% 이격 중이며, "
                if ma20_gap <= 3:
                    strategy += "이평선 근접 매수로 손절 리스크가 낮은 구간입니다."
                elif ma20_gap <= 7:
                    strategy += "적정 이격 구간에서 상승 추세를 유지하고 있습니다."
                else:
                    strategy += "이격이 다소 벌어져 있어 단기 조정 시 추가 매수 전략이 유효합니다."
            else:
                strategy += f"20일선 하단({ma20_gap:+.1f}%)에 위치해 있어, 이평선 회복 확인 후 진입이 안전합니다."
            sections.append(strategy)

            full_reason = "\n".join(sections)

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
