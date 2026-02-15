import pandas as pd
from datetime import datetime
import os
from utils.data_fetcher import (
    get_kospi_chart_data, get_exchange_rate_data,
    get_market_net_purchases, get_leading_sectors,
    get_global_indices, get_sector_returns
)


def _safe_index_str(df, idx, col, default="N/A"):
    """DataFrame에서 안전하게 값 추출"""
    try:
        if idx in df.index:
            val = df.loc[idx, col]
            return val
    except:
        pass
    return default


def _calc_change(df, col='Close'):
    """DataFrame의 마지막 2행으로 변동 계산"""
    if df is None or len(df) < 2:
        return 0, 0, "-"
    val = df[col].iloc[-1]
    prev = df[col].iloc[-2]
    chg = (val - prev) / prev * 100
    sign = "▲" if chg > 0 else "▼" if chg < 0 else "-"
    return val, chg, sign


def generate_topdown_report(target_date):
    """
    1.md 형식을 정확히 복제하여 전문가급 Top-Down 리포트를 생성합니다.
    (v3.0: Executive Summary, 거시경제, 수급, 리스크, 유망 섹터 TOP 3, 비교 매트릭스 포함)
    """
    try:
        # ══════════════════════════════════════════
        # 1. 데이터 수집
        # ══════════════════════════════════════════
        
        # KOSPI
        df_kospi = get_kospi_chart_data(days=10)
        kospi_val, kospi_chg, kospi_sign = _calc_change(df_kospi, '종가')
        
        # 환율
        try:
            df_ex = get_exchange_rate_data(days=10)
            ex_val, ex_chg_pct, ex_sign = _calc_change(df_ex, 'Close')
            ex_delta = df_ex['Close'].iloc[-1] - df_ex['Close'].iloc[-2]
        except:
            ex_val, ex_chg_pct, ex_sign, ex_delta = 0, 0, "-", 0
        
        # 글로벌 지수
        global_idx = get_global_indices(days=10)
        
        nasdaq_val, nasdaq_chg, nasdaq_sign = 0, 0, "-"
        sox_val, sox_chg, sox_sign = 0, 0, "-"
        
        if "NASDAQ" in global_idx and len(global_idx["NASDAQ"]) >= 2:
            nasdaq_val, nasdaq_chg, nasdaq_sign = _calc_change(global_idx["NASDAQ"])
        if "SOX" in global_idx and len(global_idx["SOX"]) >= 2:
            sox_val, sox_chg, sox_sign = _calc_change(global_idx["SOX"])
        
        # 수급 (전체)
        df_foreign_all = get_market_net_purchases(target_date, investor="외국인", top_n=None)
        df_inst_all = get_market_net_purchases(target_date, investor="기관합계", top_n=None)
        df_indi_all = get_market_net_purchases(target_date, investor="개인", top_n=None)
        
        foreign_total = df_foreign_all['순매수(억)'].sum() if not df_foreign_all.empty else 0
        inst_total = df_inst_all['순매수(억)'].sum() if not df_inst_all.empty else 0
        indi_total = df_indi_all['순매수(억)'].sum() if not df_indi_all.empty else 0
        
        # 수급 상위/하위
        df_foreign_buy = df_foreign_all.sort_values('순매수(억)', ascending=False).head(10) if not df_foreign_all.empty else pd.DataFrame()
        df_inst_buy = df_inst_all.sort_values('순매수(억)', ascending=False).head(10) if not df_inst_all.empty else pd.DataFrame()
        df_foreign_sell = df_foreign_all.sort_values('순매수(억)', ascending=True).head(5) if not df_foreign_all.empty else pd.DataFrame()
        
        # 섹터 등락률
        sector_returns = get_sector_returns(target_date)
        top_sectors = sector_returns.head(3) if not sector_returns.empty else pd.Series()
        bottom_sectors = sector_returns.tail(3).sort_values() if not sector_returns.empty else pd.Series()
        
        # 주도 섹터 (수급 기반)
        leading_set = get_leading_sectors(target_date)
        leading_list = list(leading_set)[:3]
        
        # 섹터별 수급 집중도 (외국인/기관 각각의 섹터별 합산)
        foreign_sector_flow = ""
        inst_sector_flow = ""
        foreign_sell_sector_flow = ""
        
        if not df_foreign_all.empty and 'Sector' in df_foreign_all.columns:
            fs = df_foreign_all.groupby('Sector')['순매수(억)'].sum().sort_values(ascending=False)
            fs = fs[fs.index != '']
            top_fs = fs.head(3)
            # 각 섹터의 대표 종목 1개씩 매칭
            foreign_picks = []
            for sec in top_fs.index:
                sub = df_foreign_all[df_foreign_all['Sector'] == sec].head(1)
                if not sub.empty:
                    foreign_picks.append(f"{sec}({sub.iloc[0]['종목명']})")
                else:
                    foreign_picks.append(sec)
            foreign_sector_flow = ", ".join(foreign_picks)
            
            # 외국인 순매도 섹터
            bottom_fs = fs[fs < 0].sort_values().head(3)
            sell_picks = []
            for sec in bottom_fs.index:
                sub = df_foreign_all[df_foreign_all['Sector'] == sec].sort_values('순매수(억)').head(1)
                if not sub.empty:
                    sell_picks.append(f"{sec}({sub.iloc[0]['종목명']})")
                else:
                    sell_picks.append(sec)
            foreign_sell_sector_flow = ", ".join(sell_picks) if sell_picks else "없음"
                
        if not df_inst_all.empty and 'Sector' in df_inst_all.columns:
            is_ = df_inst_all.groupby('Sector')['순매수(억)'].sum().sort_values(ascending=False)
            is_ = is_[is_.index != '']
            top_is = is_.head(3)
            inst_picks = []
            for sec in top_is.index:
                sub = df_inst_all[df_inst_all['Sector'] == sec].head(1)
                if not sub.empty:
                    inst_picks.append(f"{sec}({sub.iloc[0]['종목명']})")
                else:
                    inst_picks.append(sec)
            inst_sector_flow = ", ".join(inst_picks)
        
        # ══════════════════════════════════════════
        # 2. 리포트 작성 (1.md 형식 복제)
        # ══════════════════════════════════════════
        
        date_str = datetime.now().strftime('%Y년 %m월 %d일')
        
        # 투자 판단 문구 자동 생성
        if leading_list:
            sector_rank = " > ".join(leading_list[:3])
        else:
            sector_rank = "뚜렷한 주도 섹터 미확인"
        
        # 시장 방향 판단
        if kospi_chg > 1:
            market_tone = "강세"
            market_desc = f"KOSPI가 전일 대비 {abs(kospi_chg):.2f}% 상승하며 강한 매수세를 보이고 있습니다."
        elif kospi_chg > 0:
            market_tone = "약보합 상승"
            market_desc = f"KOSPI가 소폭 상승하며 안정적인 흐름을 유지하고 있습니다."
        elif kospi_chg > -1:
            market_tone = "약보합 하락"
            market_desc = f"KOSPI가 소폭 하락했으나 하방 지지가 견고한 모습입니다."
        else:
            market_tone = "약세"
            market_desc = f"KOSPI가 전일 대비 {abs(kospi_chg):.2f}% 하락하며 조정 국면에 진입했습니다."
        
        report = f"""# 📊 KOSPI Top-Down 시장 분석 보고서

**작성일: {date_str}** | **기준일: {target_date}** | **KOSPI {kospi_val:,.0f}pt**

---

## Executive Summary

{market_desc} """

        if foreign_total > 0 and inst_total > 0:
            report += f"외국인({foreign_total:+,.0f}억)과 기관({inst_total:+,.0f}억)이 동반 순매수하며 수급이 우호적입니다. "
        elif foreign_total > 0:
            report += f"외국인이 {foreign_total:+,.0f}억원 순매수를 기록한 반면, 기관은 {inst_total:+,.0f}억원으로 소극적입니다. "
        elif inst_total > 0:
            report += f"기관이 {inst_total:+,.0f}억원 순매수를 기록한 반면, 외국인은 {foreign_total:+,.0f}억원으로 관망세입니다. "
        else:
            report += f"외국인({foreign_total:+,.0f}억)과 기관({inst_total:+,.0f}억) 모두 순매도로 전환하여 주의가 필요합니다. "
        
        if leading_list:
            report += f"수급 주도 섹터는 **{', '.join(leading_list)}** 중심으로 형성되고 있습니다."
        
        report += f"""

> **투자 판단**: 수급 주도 섹터 기준, **{sector_rank}** 순으로 시장 수익률 상회 가능성이 높습니다.

---

## 1. 거시경제 분석

### 1-1. 시장 지수 및 환율

| 지표 | 현재치 | 전일 대비 |
|---|---|---|
| **KOSPI** | **{kospi_val:,.0f}** | {kospi_sign} {abs(kospi_chg):.2f}% |
| **USD/KRW** | **{ex_val:,.0f}원** | {ex_sign} {abs(ex_delta):.0f}원 ({abs(ex_chg_pct):.2f}%) |
| **NASDAQ** | {nasdaq_val:,.0f} | {nasdaq_sign} {abs(nasdaq_chg):.2f}% |
| **SOX (반도체)** | {sox_val:,.0f} | {sox_sign} {abs(sox_chg):.2f}% |

"""
        # 환율 해석
        if ex_delta > 0:
            report += f"""- **원화 약세**: 환율이 {ex_val:,.0f}원으로 상승. 수출주에 우호적이나 외국인 매수세 약화 가능성
- **KOSPI 영향**: 환율 상승 시 외국인 투자자의 달러 기준 수익률 하락 → 순매도 전환 위험 모니터링 필요
"""
        else:
            report += f"""- **원화 강세**: 환율이 {ex_val:,.0f}원으로 하락. 외국인 원화자산 매력도 상승 → 순매수 유인
- **KOSPI 영향**: 원화 강세 시 외국인 투자자의 원화 자산 매력도 상승 → KOSPI 상승 지지
"""

        report += f"""
---

## 2. 수급 분석

### 2-1. 투자 주체별 자금 흐름

| 투자 주체 | 당일 순매수(추정) | 기조 |
|---|---|---|
| 외국인 | **{foreign_total:+,.0f}억원** | {'순매수' if foreign_total > 0 else '순매도'} |
| 기관 | **{inst_total:+,.0f}억원** | {'순매수' if inst_total > 0 else '순매도'} |
| 개인 | **{indi_total:+,.0f}억원** | {'순매수' if indi_total > 0 else '순매도'} (차익실현) |

### 2-2. 섹터별 수급 집중도

```
외국인 순매수 집중  →  {foreign_sector_flow if foreign_sector_flow else 'N/A'}
기관 순매수 집중    →  {inst_sector_flow if inst_sector_flow else 'N/A'}
외국인 순매도 집중  →  {foreign_sell_sector_flow if foreign_sell_sector_flow else 'N/A'}
```

"""
        # 외국인 순매수 TOP 5 테이블
        report += "### 외국인 순매수 TOP 5\n\n"
        if not df_foreign_buy.empty:
            report += "| 종목명 | 섹터 | 순매수(억) | 등락률 |\n|---|---|---|---|\n"
            for i in range(min(5, len(df_foreign_buy))):
                row = df_foreign_buy.iloc[i]
                pct = row.get('등락률', 0)
                pct_val = pct if isinstance(pct, (int, float)) else 0
                report += f"| **{row['종목명']}** | {row.get('Sector', '')} | {row['순매수(억)']:+,.1f} | {pct_val:+.2f}% |\n"
        
        report += "\n### 기관 순매수 TOP 5\n\n"
        if not df_inst_buy.empty:
            report += "| 종목명 | 섹터 | 순매수(억) | 등락률 |\n|---|---|---|---|\n"
            for i in range(min(5, len(df_inst_buy))):
                row = df_inst_buy.iloc[i]
                pct = row.get('등락률', 0)
                pct_val = pct if isinstance(pct, (int, float)) else 0
                report += f"| **{row['종목명']}** | {row.get('Sector', '')} | {row['순매수(억)']:+,.1f} | {pct_val:+.2f}% |\n"
        
        report += """
---

## 3. 리스크 요인

### 🔴 High Risk

| 리스크 | 세부 내용 | 영향도 |
|---|---|---|
| **미국 관세 정책** | 자동차·반도체 품목 관세 인상 시나리오. 대미 수출 타격 및 환율 변동성 확대 | ★★★★★ |
| **단기 과열 시그널** | 급등 구간 진입 시 차익실현 매물 출회 가능성 | ★★★★☆ |

### 🟡 Medium Risk

| 리스크 | 세부 내용 | 영향도 |
|---|---|---|
| **가계부채** | GDP 대비 높은 수준 유지. 금리 동결 장기화 시 상환 부담 증가 | ★★★★☆ |
| **미-중 기술 패권 경쟁** | 반도체·AI 분야 수출 통제 강화 시 국내 기업 공급망 교란 가능 | ★★★☆☆ |

### 🟢 Low Risk (모니터링)

| 리스크 | 세부 내용 | 영향도 |
|---|---|---|
| 부동산 시장 | 수도권 공급 부족, 전세가 상승 → 내수 소비 위축 가능성 | ★★☆☆☆ |
| 지정학적 불안 | 글로벌 분쟁 장기화, 에너지 수입 비용 부담 | ★★☆☆☆ |

---

## 4. 유망 섹터 선정 (수급 기반)

"""
        # 유망 섹터 TOP 3 상세 분석
        if not top_sectors.empty:
            medals = ["🥇 1위", "🥈 2위", "🥉 3위"]
            stars = ["★★★★★", "★★★★☆", "★★★★☆"]
            confidence = ["Very High", "High", "High"]
            
            for rank_idx, (sec_name, sec_ret) in enumerate(top_sectors.items()):
                if rank_idx >= 3:
                    break
                
                # 해당 섹터의 외국인/기관 수급 방향 확인
                f_flow = ""
                i_flow = ""
                if not df_foreign_all.empty and 'Sector' in df_foreign_all.columns:
                    sec_f = df_foreign_all[df_foreign_all['Sector'] == sec_name]['순매수(억)'].sum()
                    f_flow = "순매수" if sec_f > 0 else "순매도"
                if not df_inst_all.empty and 'Sector' in df_inst_all.columns:
                    sec_i = df_inst_all[df_inst_all['Sector'] == sec_name]['순매수(억)'].sum()
                    i_flow = "순매수" if sec_i > 0 else "순매도"
                
                # 해당 섹터 대표 종목 3개
                rep_stocks = []
                if not df_foreign_all.empty and 'Sector' in df_foreign_all.columns:
                    sec_stocks = df_foreign_all[df_foreign_all['Sector'] == sec_name].head(3)
                    rep_stocks = sec_stocks['종목명'].tolist()
                rep_str = ", ".join(rep_stocks) if rep_stocks else "N/A"
                
                report += f"""### {medals[rank_idx]}: {sec_name}

**추천 강도: {stars[rank_idx]} | 확신도: {confidence[rank_idx]}**

| 모멘텀 | 내용 |
|---|---|
| 등락률 | 당일 섹터 평균 **{sec_ret:+.2f}%** |
| 외국인 수급 | {f_flow} 기조 |
| 기관 수급 | {i_flow} 기조 |
| 대표 종목 | {rep_str} |

> **핵심 논리**: {sec_name} 섹터는 당일 {sec_ret:+.2f}%의 등락률을 기록하며 시장을 주도하고 있습니다. 외국인({f_flow})과 기관({i_flow}) 수급이 집중되고 있어, 단기적으로 관심이 확대될 가능성이 높습니다. 대표 종목({rep_str})의 기술적 타점을 2페이지 [Swing Trading]에서 확인하세요.

"""

        # 섹터 비교 매트릭스
        report += "---\n\n## 섹터 비교 매트릭스\n\n"
        
        if not top_sectors.empty and not bottom_sectors.empty:
            all_sectors_for_matrix = list(top_sectors.index[:3])
            if not bottom_sectors.empty:
                worst = bottom_sectors.index[0]
                if worst not in all_sectors_for_matrix:
                    all_sectors_for_matrix.append(worst)
            
            header = "| 기준 |"
            separator = "|---|"
            for s in all_sectors_for_matrix:
                header += f" {s} |"
                separator += ":---:|"
            report += header + "\n" + separator + "\n"
            
            for metric_name in ["등락률", "외국인 수급", "기관 수급"]:
                row_str = f"| {metric_name} |"
                for s in all_sectors_for_matrix:
                    if metric_name == "등락률":
                        ret = sector_returns.get(s, 0)
                        row_str += " 🟢 |" if ret > 0.5 else (" 🟡 |" if ret > -0.5 else " 🔴 |")
                    elif metric_name == "외국인 수급":
                        if not df_foreign_all.empty and 'Sector' in df_foreign_all.columns:
                            sv = df_foreign_all[df_foreign_all['Sector'] == s]['순매수(억)'].sum()
                            row_str += " 🟢 |" if sv > 50 else (" 🟡 |" if sv > -50 else " 🔴 |")
                        else:
                            row_str += " 🟡 |"
                    elif metric_name == "기관 수급":
                        if not df_inst_all.empty and 'Sector' in df_inst_all.columns:
                            sv = df_inst_all[df_inst_all['Sector'] == s]['순매수(억)'].sum()
                            row_str += " 🟢 |" if sv > 50 else (" 🟡 |" if sv > -50 else " 🔴 |")
                        else:
                            row_str += " 🟡 |"
                report += row_str + "\n"
            
            # 종합 판정
            verdict_row = "| **종합 판정** |"
            for idx, s in enumerate(all_sectors_for_matrix):
                if idx == 0:
                    verdict_row += " **1위** |"
                elif idx == 1:
                    verdict_row += " **2위** |"
                elif idx == 2:
                    verdict_row += " **3위** |"
                else:
                    verdict_row += " 회피 |"
            report += verdict_row + "\n"
        
        # 회피 섹터
        if not bottom_sectors.empty:
            worst_sec = bottom_sectors.index[0]
            worst_ret = bottom_sectors.iloc[0]
            report += f"""
---

## Appendix: 회피 섹터

### ⚠️ {worst_sec} — 단기 비중 축소 권고

- 당일 섹터 평균 등락률 **{worst_ret:+.2f}%**로 시장 대비 부진
"""
            if not df_foreign_all.empty and 'Sector' in df_foreign_all.columns:
                sv = df_foreign_all[df_foreign_all['Sector'] == worst_sec]['순매수(억)'].sum()
                if sv < 0:
                    report += f"- 외국인 **{sv:,.0f}억원 순매도** 진행 중\n"
            report += "- 수급과 모멘텀이 동시에 약화되어 단기 회복은 제한적\n"

        report += f"""
---

> **면책조항**: 본 보고서는 공개된 시장 데이터(pykrx, FinanceDataReader)에 기반하여 AI 알고리즘이 자동 생성한 분석이며, 투자 권유가 아닙니다. 투자 결정은 본인의 판단과 책임 하에 이루어져야 합니다.
"""
        
        # ══════════════════════════════════════════
        # 3. 저장 (Supabase 우선 → 로컬 파일 fallback)
        # ══════════════════════════════════════════
        saved_to_db = False
        try:
            from utils.supabase_client import save_report
            saved_to_db = save_report(target_date, report)
        except Exception:
            pass
        
        # 로컬 파일도 항상 저장 (개발 편의)
        filename = f"kospi_topdown_report_{target_date}.md"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(report)
        except:
            filename = None  # 서버리스 환경에서 쓰기 실패 가능
        
        storage_info = "DB" if saved_to_db else ("파일" if filename else "메모리")
        return report, filename, storage_info

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"리포트 생성 중 오류가 발생했습니다: {str(e)}", None, None
