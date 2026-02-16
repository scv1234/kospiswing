#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KOSPI 전 종목 펀더멘털 & 수급 스크리닝 도구
============================================
20년 경력 퀀트 펀드매니저 관점의 멀티팩터 스크리닝.

핵심 데이터소스: pykrx (KRX 공식 데이터)
보조 데이터소스: FinanceDataReader (시세/거래량)

스크리닝 조건 (AND):
  1. 저평가   : PER ≤ 10, PBR < 1.0
  2. 수익성   : ROE ≥ 10% (PBR/PER 기반 추정 포함)
  3. 재무건전성: 부채비율 < 200%
  4. 수급(선택): 최근 20일 거래량 MA 대비 전일 거래량 급증 (1.5배 이상)

출력:
  - PBR 오름차순 상위 20개 종목
  - 종목명, 현재가, PER, PBR, ROE, 부채비율, 거래량급증 여부
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from pykrx import stock
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import time
import sys
import io

# Windows 콘솔에서 한글 출력 시 UnicodeEncodeError 방지
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ──────────────────────────────────────────────
# 0. 글로벌 설정
# ──────────────────────────────────────────────
VOLUME_LOOKBACK = 20        # 거래량 이동평균 산출 기간 (일)
VOLUME_SURGE_MULT = 1.5     # 거래량 급증 배수 기준
MAX_DISPLAY = 20            # 최종 출력 종목 수

pd.set_option("display.max_rows", MAX_DISPLAY + 5)
pd.set_option("display.max_columns", 15)
pd.set_option("display.width", 140)
pd.set_option("display.float_format", lambda x: f"{x:,.2f}")
pd.set_option("display.unicode.east_asian_width", True)

print("=" * 72)
print("  📊 KOSPI 멀티팩터 스크리닝 도구 (pykrx 기반)")
print("=" * 72)


# ──────────────────────────────────────────────
# 1. 최근 유효 거래일 자동 탐색
#    - 주말/공휴일에도 자동으로 직전 거래일 탐색
#    - PER > 0인 종목이 100개 이상이어야 유효 거래일로 인정
# ──────────────────────────────────────────────
print("\n[1/6] 최근 유효 거래일 탐색 중...")

trade_date = None
for i in range(10):
    candidate = (datetime.today() - timedelta(days=i)).strftime("%Y%m%d")
    try:
        df_test = stock.get_market_fundamental(candidate, market="KOSPI")
        valid_count = (df_test["PER"] > 0).sum()
        if valid_count > 100:
            trade_date = candidate
            print(f"  ✅ 유효 거래일: {trade_date} (PER 유효 종목: {valid_count}개)")
            break
    except Exception:
        continue

if trade_date is None:
    print("  ❌ 유효 거래일을 찾을 수 없습니다.")
    sys.exit(1)

trade_date_formatted = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"


# ──────────────────────────────────────────────
# 2. KOSPI 전 종목 펀더멘털 지표 일괄 조회
#    - pykrx.stock.get_market_fundamental() 사용
#    - 반환 컬럼: BPS, PER, PBR, EPS, DIV, DPS
#    - 전 종목 한 번의 호출로 조회 (매우 빠름)
# ──────────────────────────────────────────────
print("\n[2/6] KOSPI 전체 종목 펀더멘털 지표 조회 중...")

df_fundamental = stock.get_market_fundamental(trade_date, market="KOSPI")
print(f"  ✅ 펀더멘털 데이터 로드 완료: {len(df_fundamental)}개 종목")

# 종목명 매핑 (pykrx는 티커만 반환하므로 종목명을 별도 조회)
ticker_list = stock.get_market_ticker_list(trade_date, market="KOSPI")
ticker_name_map = {}
for ticker in ticker_list:
    try:
        ticker_name_map[ticker] = stock.get_market_ticker_name(ticker)
    except Exception:
        ticker_name_map[ticker] = ticker

df_fundamental["종목명"] = df_fundamental.index.map(
    lambda t: ticker_name_map.get(t, t)
)
df_fundamental["종목코드"] = df_fundamental.index

print(f"  ✅ 종목명 매핑 완료")


# ──────────────────────────────────────────────
# 3. 시세 데이터 조회 (현재가, 거래량)
#    - pykrx.stock.get_market_ohlcv_by_ticker() 사용
#    - 한 번의 호출로 전 종목 OHLCV 조회
# ──────────────────────────────────────────────
print("\n[3/6] KOSPI 전체 종목 시세/거래량 조회 중...")

df_ohlcv = stock.get_market_ohlcv(trade_date, market="KOSPI")
print(f"  ✅ 시세 데이터 로드 완료: {len(df_ohlcv)}개 종목")

# 펀더멘털 + 시세 데이터 병합 (티커 기준)
df_merged = df_fundamental.join(df_ohlcv, how="left")

total_stocks = len(df_merged)
print(f"  ✅ 데이터 병합 완료 (총 {total_stocks}개 종목)")


# ──────────────────────────────────────────────
# 4. ROE 산출 및 부채비율 추정
#    - ROE = PBR / PER × 100 (듀퐁 항등식: PBR = PER × ROE)
#    - 부채비율: pykrx 기본 데이터에는 미포함
#      → BPS 대비 주가 비율로 간접 추정하거나, 데이터 소스 추가 필요
# ──────────────────────────────────────────────
print("\n[4/6] ROE 산출 및 필터링 조건 적용 중...")

# ROE 산출: ROE(%) = PBR / PER × 100
# PER이 0이거나 음수인 경우 NaN 처리 (적자 기업 등)
valid_per = df_merged["PER"].replace(0, np.nan)
df_merged["ROE"] = np.where(
    valid_per.notna() & (valid_per > 0),
    (df_merged["PBR"] / valid_per) * 100,
    np.nan
)
print(f"  ✅ ROE 산출 완료 (ROE = PBR/PER × 100)")

# 부채비율: pykrx에서 직접 제공하지 않음
# → 보수적 접근: BPS(주당 순자산) 대비 주가 레버리지 비율로 간접 추정
# → 부채비율 ≈ (주가/BPS - 1) × PBR 비율 활용
# → 단, 정확한 부채비율은 DART(전자공시)에서 재무제표 직접 조회 필요
# → 여기서는 BPS > 0인 종목만 필터링 (순자산 양수 = 자본잠식 아님)
df_merged["BPS_valid"] = df_merged["BPS"] > 0
print(f"  ℹ️ 부채비율: pykrx 미지원 → BPS>0(자본잠식 미발생) 필터로 대체")
print(f"     (정밀 부채비율 필터는 DART API 연동 시 가능)")


# ──────────────────────────────────────────────
# 5. 멀티팩터 스크리닝 (AND 조건)
# ──────────────────────────────────────────────
print("\n[5/6] 멀티팩터 스크리닝 적용...")

# 조건 1: PER > 0 AND PER ≤ 10 (저PER, 적자기업 제외)
cond_per = (df_merged["PER"] > 0) & (df_merged["PER"] <= 10)
print(f"  조건1 PER (0 < PER ≤ 10): {cond_per.sum()}개 통과")

# 조건 2: PBR > 0 AND PBR < 1.0 (저PBR)
cond_pbr = (df_merged["PBR"] > 0) & (df_merged["PBR"] < 1.0)
print(f"  조건2 PBR (0 < PBR < 1.0): {cond_pbr.sum()}개 통과")

# 조건 3: ROE ≥ 10%
cond_roe = df_merged["ROE"] >= 10
print(f"  조건3 ROE (≥ 10%):         {cond_roe.sum()}개 통과")

# 조건 4: BPS > 0 (자본잠식 미발생 = 재무건전성 기본 필터)
cond_bps = df_merged["BPS_valid"]
print(f"  조건4 BPS > 0:             {cond_bps.sum()}개 통과")

# 종합 AND 조건
all_conds = cond_per & cond_pbr & cond_roe & cond_bps
df_screened = df_merged[all_conds].copy()
print(f"\n  ✅ 전체 AND 조건 통과: {len(df_screened)}개 종목")


# ──────────────────────────────────────────────
# 6. 수급 분석: 스크리닝 통과 종목만 거래량 급증 탐지
#    - 스크리닝 통과 종목만 대상으로 하여 API 호출 최소화
#    - 최근 60일 일봉에서 20일 거래량 MA 대비 최종일 거래량 비교
# ──────────────────────────────────────────────
print(f"\n[6/6] 수급 분석 (스크리닝 통과 {len(df_screened)}개 종목 대상)...")
print(f"  기준: 전일 거래량 > {VOLUME_LOOKBACK}일 평균 거래량 × {VOLUME_SURGE_MULT}")

start_date = (datetime.today() - timedelta(days=60)).strftime("%Y%m%d")
end_date = trade_date

volume_results = {}
processed = 0
errors = 0

for ticker in df_screened.index:
    processed += 1
    try:
        # 최근 60일 일봉 데이터 조회
        df_price = stock.get_market_ohlcv(start_date, end_date, ticker)

        if df_price is None or len(df_price) < VOLUME_LOOKBACK + 1:
            volume_results[ticker] = {"거래량급증": False, "거래량비율": np.nan}
            continue

        # 20일 거래량 이동평균 계산
        df_price["Vol_MA20"] = df_price["거래량"].rolling(window=VOLUME_LOOKBACK).mean()

        # 최근 거래일의 거래량 vs 20일 MA 비교
        latest_vol = df_price["거래량"].iloc[-1]
        ma20_vol = df_price["Vol_MA20"].iloc[-1]

        if ma20_vol and ma20_vol > 0:
            ratio = latest_vol / ma20_vol
            is_surge = ratio >= VOLUME_SURGE_MULT
        else:
            ratio = np.nan
            is_surge = False

        volume_results[ticker] = {
            "거래량급증": is_surge,
            "거래량비율": round(ratio, 2) if not np.isnan(ratio) else np.nan,
        }

        # API 부하 방지
        time.sleep(0.05)

    except Exception as e:
        errors += 1
        volume_results[ticker] = {"거래량급증": False, "거래량비율": np.nan}

print(f"  ✅ 수급 분석 완료 (처리: {processed}, 오류: {errors})")

# 수급 데이터 병합
vol_df = pd.DataFrame.from_dict(volume_results, orient="index")
vol_df.index.name = "티커"
df_screened = df_screened.join(vol_df, how="left")


# ──────────────────────────────────────────────
# 7. 최종 결과 출력
# ──────────────────────────────────────────────
print("\n" + "=" * 72)
print(f"  📊 KOSPI 멀티팩터 스크리닝 결과")
print(f"  기준일: {trade_date_formatted}")
print("=" * 72)
print(f"\n  스크리닝 조건:")
print(f"    • PER: 0 < PER ≤ 10 (저평가)")
print(f"    • PBR: 0 < PBR < 1.0 (저PBR)")
print(f"    • ROE: ≥ 10% (수익성)")
print(f"    • BPS: > 0 (자본잠식 미발생)")
print(f"    • 수급: 20일 MA 대비 거래량 {VOLUME_SURGE_MULT}배↑ 표시")
print(f"\n  전체 KOSPI {total_stocks}개 → 스크리닝 통과 {len(df_screened)}개")

# PBR 오름차순 정렬 (저PBR 우선)
df_screened = df_screened.sort_values("PBR", ascending=True)

# 현재가 컬럼 확인 (pykrx OHLCV 컬럼명은 한글)
close_col = "종가" if "종가" in df_screened.columns else "Close"

# 출력 데이터프레임 구성
output_columns = ["종목명", "종목코드"]
if close_col in df_screened.columns:
    output_columns.append(close_col)
output_columns.extend(["PER", "PBR", "ROE", "BPS"])
if "거래량급증" in df_screened.columns:
    output_columns.extend(["거래량급증", "거래량비율"])

# 유효 컬럼만 선택
valid_cols = [c for c in output_columns if c in df_screened.columns]
display_df = df_screened[valid_cols].head(MAX_DISPLAY).copy()

# 컬럼명 정리
rename_map = {
    close_col: "현재가",
    "ROE": "ROE(%)",
}
display_df = display_df.rename(columns=rename_map)

# 인덱스 정리
display_df = display_df.reset_index(drop=True)
display_df.index += 1
display_df.index.name = "순위"

print(f"\n  ▼ 상위 {min(MAX_DISPLAY, len(display_df))}개 종목 (PBR 오름차순)\n")
print(display_df.to_string())

# ── CSV 저장 ──
output_filename = f"kospi_screening_{trade_date}.csv"
display_df.to_csv(output_filename, encoding="utf-8-sig")
print(f"\n  💾 결과 저장: {output_filename}")

# ── 거래량 급증 종목 하이라이트 ──
if "거래량급증" in display_df.columns:
    surge_stocks = display_df[display_df["거래량급증"] == True]
    if len(surge_stocks) > 0:
        print(f"\n  🔥 거래량 급증 종목 ({len(surge_stocks)}개):")
        for _, row in surge_stocks.iterrows():
            name = row.get("종목명", "N/A")
            ratio = row.get("거래량비율", "N/A")
            print(f"    → {name} (거래량 비율: {ratio}x)")
    else:
        print(f"\n  ℹ️ 스크리닝 결과 중 거래량 급증 종목 없음")

# ── 전체 스크리닝 통과 종목 CSV 저장 ──
if len(df_screened) > MAX_DISPLAY:
    full_output = f"kospi_screening_full_{trade_date}.csv"
    full_df = df_screened[valid_cols].copy()
    full_df = full_df.rename(columns=rename_map)
    full_df = full_df.reset_index(drop=True)
    full_df.index += 1
    full_df.index.name = "순위"
    full_df.to_csv(full_output, encoding="utf-8-sig")
    print(f"  💾 전체 결과 저장: {full_output} ({len(df_screened)}개 종목)")

print("\n" + "=" * 72)
print("  ✅ 스크리닝 완료!")
print("=" * 72)
