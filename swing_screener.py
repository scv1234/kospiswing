"""
KOSPI 스윙 트레이딩 4단계 분석 시스템
"""
import warnings
warnings.filterwarnings("ignore")

import sys, io
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np
from pykrx import stock
from datetime import datetime, timedelta
import time

pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 200)
pd.set_option("display.float_format", lambda x: f"{x:,.2f}")

# === 설정 ===
TRADE_DATE = "20260213"  # 최근 거래일
START_90D = (datetime.strptime(TRADE_DATE, "%Y%m%d") - timedelta(days=120)).strftime("%Y%m%d")

print("=" * 80)
print("  KOSPI 스윙 트레이딩 4단계 분석")
print(f"  기준 거래일: {TRADE_DATE}")
print("=" * 80)

# ============================================================
# STEP 1: 외국인/기관 순매수 TOP 종목 파악
# ============================================================
print("\n[STEP 1] 외국인/기관 순매수 종목 조회...")

df_foreign = stock.get_market_net_purchases_of_equities(TRADE_DATE, TRADE_DATE, "KOSPI", "외국인")
df_inst = stock.get_market_net_purchases_of_equities(TRADE_DATE, TRADE_DATE, "KOSPI", "기관합계")

# 외국인 순매수 TOP
print("\n--- 외국인 순매수 TOP 10 ---")
print(df_foreign.head(10)[["종목명", "매수거래량", "매도거래량", "순매수거래량", "순매수거래대금"]].to_string())

print("\n--- 기관 순매수 TOP 10 ---")
print(df_inst.head(10)[["종목명", "매수거래량", "매도거래량", "순매수거래량", "순매수거래대금"]].to_string())

# 외국인+기관 모두 순매수한 종목 찾기
foreign_buy_tickers = set(df_foreign[df_foreign["순매수거래량"] > 0].index.tolist())
inst_buy_tickers = set(df_inst[df_inst["순매수거래량"] > 0].index.tolist())
both_buy = foreign_buy_tickers & inst_buy_tickers

print(f"\n외국인+기관 동시 순매수 종목: {len(both_buy)}개")

# ============================================================
# STEP 2: 기술적 분석 스크리닝 (관심 종목 대상)
# ============================================================
print("\n[STEP 2] 기술적 분석 스크리닝...")

# 관심 종목 = 외국인+기관 동시 순매수 + 외국인 TOP 20 + 기관 TOP 20
target_tickers = list(both_buy | set(df_foreign.head(20).index) | set(df_inst.head(20).index))
print(f"분석 대상: {len(target_tickers)}개 종목")

# 펀더멘털 데이터 로드
df_fund = stock.get_market_fundamental(TRADE_DATE, market="KOSPI")
df_ohlcv_today = stock.get_market_ohlcv(TRADE_DATE, market="KOSPI")

results = []

for i, ticker in enumerate(target_tickers):
    try:
        name = stock.get_market_ticker_name(ticker)
        
        # 60거래일 일봉 데이터
        df_price = stock.get_market_ohlcv(START_90D, TRADE_DATE, ticker)
        if df_price is None or len(df_price) < 25:
            continue
        
        # 현재가
        close = df_price["종가"].iloc[-1]
        prev_close = df_price["종가"].iloc[-2]
        change_pct = (close / prev_close - 1) * 100
        
        # --- 거래량 분석 ---
        vol_today = df_price["거래량"].iloc[-1]
        vol_ma20 = df_price["거래량"].rolling(20).mean().iloc[-1]
        vol_ratio = vol_today / vol_ma20 if vol_ma20 > 0 else 0
        
        # --- 이동평균선 ---
        df_price["MA5"] = df_price["종가"].rolling(5).mean()
        df_price["MA20"] = df_price["종가"].rolling(20).mean()
        df_price["MA60"] = df_price["종가"].rolling(60).mean()
        
        ma5 = df_price["MA5"].iloc[-1]
        ma20 = df_price["MA20"].iloc[-1]
        ma60 = df_price["MA60"].iloc[-1] if pd.notna(df_price["MA60"].iloc[-1]) else 0
        
        # 정배열 체크 (5 > 20 > 60)
        golden_cross = (ma5 > ma20 > ma60 > 0) if ma60 > 0 else (ma5 > ma20)
        
        # 20일선 눌림목 반등 (현재가가 20일선 근처에서 반등)
        ma20_proximity = abs(close - ma20) / ma20 * 100 if ma20 > 0 else 999
        pullback_bounce = (close > ma20) and (ma20_proximity < 3)
        
        # --- 캔들 패턴 ---
        open_p = df_price["시가"].iloc[-1]
        high = df_price["고가"].iloc[-1]
        low = df_price["저가"].iloc[-1]
        body = abs(close - open_p)
        candle_range = high - low if high - low > 0 else 1
        
        # 장대양봉 (양봉 + 몸통이 전체의 60% 이상 + 2% 이상 상승)
        bullish_marubozu = (close > open_p) and (body / candle_range > 0.6) and (change_pct >= 2)
        
        # 망치형 (하꼬리가 몸통의 2배 이상, 윗꼬리 짧음)
        lower_shadow = min(open_p, close) - low
        upper_shadow = high - max(open_p, close)
        hammer = (lower_shadow > body * 2) and (upper_shadow < body * 0.5) and (body > 0)
        
        # 전일 고가 돌파
        prev_high = df_price["고가"].iloc[-2]
        breakout = close > prev_high
        
        # --- 펀더멘털 ---
        per = df_fund.loc[ticker, "PER"] if ticker in df_fund.index else 0
        pbr = df_fund.loc[ticker, "PBR"] if ticker in df_fund.index else 0
        bps = df_fund.loc[ticker, "BPS"] if ticker in df_fund.index else 0
        div_yield = df_fund.loc[ticker, "DIV"] if ticker in df_fund.index else 0
        
        # ROE 추정
        roe = (pbr / per * 100) if per > 0 else 0
        
        # 스윙 점수 계산
        score = 0
        signals = []
        
        # 수급 (외국인+기관 동시 순매수 = 높은 점수)
        if ticker in both_buy:
            score += 30
            signals.append("외+기관_동시매수")
        elif ticker in foreign_buy_tickers:
            score += 15
            signals.append("외국인_순매수")
        elif ticker in inst_buy_tickers:
            score += 15
            signals.append("기관_순매수")
        
        # 거래량 급증
        if vol_ratio >= 2.0:
            score += 20
            signals.append(f"거래량{vol_ratio:.1f}x")
        elif vol_ratio >= 1.5:
            score += 10
            signals.append(f"거래량{vol_ratio:.1f}x")
        
        # 이동평균선
        if golden_cross:
            score += 15
            signals.append("정배열")
        if pullback_bounce:
            score += 10
            signals.append("눌림목반등")
        
        # 캔들
        if bullish_marubozu:
            score += 15
            signals.append("장대양봉")
        if hammer:
            score += 10
            signals.append("망치형")
        
        # 전고점 돌파
        if breakout:
            score += 10
            signals.append("전고돌파")
        
        # 밸류에이션 (저PBR 가점)
        if 0 < pbr < 1.2:
            score += 10
            signals.append(f"PBR{pbr:.2f}")
        
        # 배당
        if div_yield > 0:
            score += 5
            signals.append(f"배당{div_yield:.1f}%")
        
        # 20일선/60일선 (지지/저항)
        support_20 = ma20
        support_60 = ma60 if ma60 > 0 else ma20 * 0.95
        
        # 목표가 (직전 고점 or +7%)
        recent_high = df_price["고가"].tail(20).max()
        target_price_1 = max(int(close * 1.07), int(recent_high))
        stop_loss = int(min(ma20, close * 0.95))
        
        results.append({
            "티커": ticker,
            "종목명": name,
            "현재가": close,
            "등락률(%)": round(change_pct, 2),
            "거래량비율": round(vol_ratio, 2),
            "MA5": int(ma5),
            "MA20": int(ma20),
            "MA60": int(ma60) if ma60 > 0 else None,
            "정배열": golden_cross,
            "눌림목": pullback_bounce,
            "장대양봉": bullish_marubozu,
            "망치형": hammer,
            "전고돌파": breakout,
            "PER": round(per, 2),
            "PBR": round(pbr, 2),
            "ROE(%)": round(roe, 2),
            "배당률(%)": round(div_yield, 2),
            "BPS": int(bps),
            "스윙점수": score,
            "시그널": " | ".join(signals),
            "1차목표가": target_price_1,
            "손절가": stop_loss,
        })
        
        time.sleep(0.03)
    except Exception as e:
        continue

print(f"\n분석 완료: {len(results)}개 종목")

# 결과 정렬 (스윙점수 내림차순)
df_result = pd.DataFrame(results).sort_values("스윙점수", ascending=False)

print("\n" + "=" * 80)
print("  [STEP 3] 종합 스윙 스코어 TOP 20")
print("=" * 80)

top20 = df_result.head(20)
for idx, row in top20.iterrows():
    print(f"\n{'─'*60}")
    print(f"  {row['종목명']} ({row['티커']})  |  점수: {row['스윙점수']}")
    print(f"  현재가: {row['현재가']:,}원  |  등락: {row['등락률(%)']}%  |  거래량비: {row['거래량비율']}x")
    print(f"  MA5: {row['MA5']:,}  MA20: {row['MA20']:,}  MA60: {row['MA60'] if row['MA60'] else 'N/A'}")
    print(f"  PER: {row['PER']}  PBR: {row['PBR']}  ROE: {row['ROE(%)']}%  배당: {row['배당률(%)']}%")
    print(f"  시그널: {row['시그널']}")
    print(f"  ▶ 1차 목표가: {row['1차목표가']:,}원  |  손절가: {row['손절가']:,}원")

# CSV 저장
df_result.to_csv("swing_screening_20260213.csv", index=False, encoding="utf-8-sig")
print(f"\n💾 전체 결과 저장: swing_screening_20260213.csv")

# 최종 TOP 3 선정
print("\n\n" + "=" * 80)
print("  [STEP 4] 최종 스윙 종목 TOP 3 선정")
print("=" * 80)

# 조건: 스윙점수 높고, PBR < 1.2, 거래량비율 >= 1.5
final_candidates = df_result[
    (df_result["스윙점수"] >= 40)
].head(10)

print(f"\n최종 후보 {len(final_candidates)}개 종목:")
for idx, row in final_candidates.head(5).iterrows():
    rr_ratio = (row["1차목표가"] - row["현재가"]) / (row["현재가"] - row["손절가"]) if row["현재가"] != row["손절가"] else 0
    print(f"\n{'━'*60}")
    print(f"  ★ {row['종목명']} ({row['티커']})")
    print(f"  스윙점수: {row['스윙점수']} | 시그널: {row['시그널']}")
    print(f"  현재가: {row['현재가']:,}원")
    print(f"  1차 목표가: {row['1차목표가']:,}원 (+{(row['1차목표가']/row['현재가']-1)*100:.1f}%)")
    print(f"  손절가: {row['손절가']:,}원 ({(row['손절가']/row['현재가']-1)*100:.1f}%)")
    print(f"  Risk/Reward: 1:{rr_ratio:.1f}")
    print(f"  PER: {row['PER']} | PBR: {row['PBR']} | ROE: {row['ROE(%)']}% | 배당: {row['배당률(%)']}%")

print("\n" + "=" * 80)
print("  분석 완료!")
print("=" * 80)
