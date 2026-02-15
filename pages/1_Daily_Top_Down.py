import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import sys
import os

# utils 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.data_fetcher import get_latest_business_day, get_kospi_chart_data, get_market_net_purchases, get_exchange_rate_data, get_global_indices, get_sector_returns

st.header("📊 Daily Top-Down Report")

# 날짜 설정
target_date = get_latest_business_day()
st.caption(f"기준 데이터: {target_date} (최근 유효 거래일)")

# 1. 거시경제 지표 (Metric Cards)
st.subheader("1. 거시경제 (Macro)")

# 데이터 로드
with st.spinner('데이터 로딩 중...'):
    kospi_df = get_kospi_chart_data(days=5)
    ex_df = get_exchange_rate_data(days=5)
    global_indices = get_global_indices(days=10)

# 지표 계산
if not kospi_df.empty:
    kospi_now = kospi_df['종가'].iloc[-1]
    kospi_prev = kospi_df['종가'].iloc[-2]
    kospi_delta = kospi_now - kospi_prev
    kospi_pct = (kospi_delta / kospi_prev) * 100
else:
    kospi_now, kospi_delta, kospi_pct = 0, 0, 0

if not ex_df.empty:
    ex_now = ex_df['Close'].iloc[-1]
    ex_prev = ex_df['Close'].iloc[-2]
    ex_delta = ex_now - ex_prev
else:
    ex_now, ex_delta = 1400, 0

nasdaq_now, nasdaq_delta, sox_now, sox_delta = "N/A", None, "N/A", None
if "NASDAQ" in global_indices and len(global_indices["NASDAQ"]) >= 2:
    nd = global_indices["NASDAQ"]
    nasdaq_now = f"{nd['Close'].iloc[-1]:,.0f}"
    nasdaq_chg = (nd['Close'].iloc[-1] - nd['Close'].iloc[-2]) / nd['Close'].iloc[-2] * 100
    nasdaq_delta = f"{nasdaq_chg:+.2f}%"
    
if "SOX" in global_indices and len(global_indices["SOX"]) >= 2:
    sx = global_indices["SOX"]
    sox_now = f"{sx['Close'].iloc[-1]:,.0f}"
    sox_chg = (sx['Close'].iloc[-1] - sx['Close'].iloc[-2]) / sx['Close'].iloc[-2] * 100
    sox_delta = f"{sox_chg:+.2f}%"

# 모바일 2x2 배치
row1_c1, row1_c2 = st.columns(2)
with row1_c1:
    st.metric("KOSPI", f"{kospi_now:,.0f}", f"{kospi_delta:,.0f} ({kospi_pct:.2f}%)")
with row1_c2:
    st.metric("USD/KRW", f"{ex_now:,.0f}원", f"{ex_delta:,.0f}원", delta_color="inverse")

row2_c1, row2_c2 = st.columns(2)
with row2_c1:
    st.metric("NASDAQ", nasdaq_now, nasdaq_delta)
with row2_c2:
    st.metric("SOX (반도체)", sox_now, sox_delta)

# 1-2. 섹터 등락률 Top/Bottom
st.markdown("---")
st.subheader("1-2. 섹터 등락률 (Top & Bottom)")
sector_returns = get_sector_returns(target_date)

if not sector_returns.empty:
    s_col1, s_col2 = st.columns(2)
    with s_col1:
        st.markdown("##### 🔥 상승 섹터 TOP 5")
        top5 = sector_returns.head(5)
        for sec, ret in top5.items():
            color = "🟢" if ret > 0 else "🔴"
            st.markdown(f"{color} **{sec}** `{ret:+.2f}%`")
    with s_col2:
        st.markdown("##### 🧊 하락 섹터 TOP 5")
        bot5 = sector_returns.tail(5).sort_values()
        for sec, ret in bot5.items():
            color = "🔴" if ret < 0 else "🟢"
            st.markdown(f"{color} **{sec}** `{ret:+.2f}%`")
else:
    st.info("섹터 등락률 데이터를 불러오지 못했습니다.")

# 2. 섹터 수급 분석 (Charts)
st.markdown("---")
st.subheader("2. 투자자별 수급 (Top Net Buy/Sell)")
st.caption(f"기준일: {target_date} | 단위: 억원")

tab1, tab2, tab3 = st.tabs(["외국인", "기관", "개인"])

def plot_investor_flow(date, investor_name):
    # 전체 데이터 로드 (순매도 분석 위해)
    df_net = get_market_net_purchases(date, investor=investor_name, top_n=None)
    
    if df_net.empty:
        st.warning("데이터가 없습니다.")
        return

    # 순매수 상위 10
    df_buy = df_net.sort_values("순매수(억)", ascending=False).head(10)
    # 순매도 상위 10 (순매수 오름차순)
    df_sell = df_net.sort_values("순매수(억)", ascending=True).head(10)
    
    # 2열 배치 (좌: 순매수, 우: 순매도)
    col1, col2 = st.columns(2)
    
    common_layout = dict(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Pretendard, Malgun Gothic, sans-serif"),
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(showgrid=True, gridcolor='lightgray'),
    )
    
    with col1:
        st.markdown(f"##### 🔴 {investor_name} 순매수 TOP 10")
        if not df_buy.empty:
            text_col = 'Sector' if 'Sector' in df_buy.columns else None
            # Sector 정보가 너무 길면 잘릴 수 있으니 종목명 뒤에 붙이는 것도 방법
            # 여기선 기존 유지하되 텍스트 포맷 개선
            
            fig = px.bar(
                df_buy, 
                x='순매수(억)', y='종목명', orientation='h',
                text=text_col,
                color='순매수(억)', 
                color_continuous_scale='Reds',
            )
            fig.update_traces(textposition='inside', textfont_size=11)
            
            # 1. 공통 레이아웃 및 기본 설정 적용
            fig.update_layout(
                yaxis={'categoryorder':'total ascending', 'title': None},
                coloraxis_showscale=False,
                height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                **common_layout
            )
            # 2. X축 타이틀 별도 설정 (중복 방지)
            fig.update_xaxes(title='순매수금액(억)')
            
            st.plotly_chart(fig, use_container_width=True)
            
    with col2:
        st.markdown(f"##### 🔵 {investor_name} 순매도 TOP 10")
        if not df_sell.empty:
            text_col = 'Sector' if 'Sector' in df_sell.columns else None
            fig = px.bar(
                df_sell, 
                x='순매수(억)', y='종목명', orientation='h',
                text=text_col,
                color='순매수(억)', 
                color_continuous_scale='Blues_r' 
            )
            fig.update_traces(textposition='inside', textfont_size=11)
            
            # 1. 공통 레이아웃 적용
            fig.update_layout(
                yaxis={'categoryorder':'total descending', 'title': None, 'side': 'right'},
                coloraxis_showscale=False,
                height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                **common_layout
            )
            # 2. X축 타이틀 및 Y축 위치 조정
            fig.update_xaxes(title='순매수금액(억)')
            fig.update_yaxes(side='right')
            
            st.plotly_chart(fig, use_container_width=True)

    with st.expander(f"📊 {investor_name} 순매수/도 전체 데이터 보기"):
        # 표시할 컬럼 동적 선택 (등락률 없을 경우 대비)
        display_cols = ['종목명', '순매수(억)', 'Sector']
        format_dict = {'순매수(억)': '{:,.1f}'}
        
        if '등락률' in df_net.columns:
            display_cols.insert(2, '등락률')
            format_dict['등락률'] = '{:,.2f}%'
            
        st.dataframe(
            df_net[display_cols].style.format(format_dict), 
            use_container_width=True
        )

with tab1:
    plot_investor_flow(target_date, "외국인")

with tab2:
    plot_investor_flow(target_date, "기관합계")

with tab3:
    plot_investor_flow(target_date, "개인")

# 3. 매크로 코멘트 (Memo)
st.subheader("3. 시장 코멘트 (Memo)")
st.text_area("오늘의 시장 한줄평을 기록하세요", height=100, placeholder="예: 환율 안정화, 반도체 수급 지속...")

# 4. AI 리포트 출력
st.markdown("---")
col_rep1, col_rep2 = st.columns([0.7, 0.3])
with col_rep1:
    st.subheader("4. AI 일일 리포트")
with col_rep2:
    if st.button("🔄 리포트 최신화 (AI 분석)", use_container_width=True):
        with st.spinner("AI가 최신 시장 데이터를 분석하여 리포트를 작성 중입니다..."):
            try:
                from utils.report_generator import generate_topdown_report
                report_text, file_name, storage_info = generate_topdown_report(target_date)
                if report_text and not report_text.startswith("리포트 생성 중 오류"):
                    st.success(f"리포트 생성 완료! (저장: {storage_info})")
                    st.query_params["report_updated"] = datetime.now().strftime('%H%M%S')
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(report_text)
            except Exception as e:
                st.error(f"리포트 생성 실패: {e}")

# 리포트 조회 (Supabase 우선 → 로컬 파일 fallback)
report_content = None
report_source = None

# 1순위: Supabase DB
try:
    from utils.supabase_client import load_report, load_report_latest
    report_content = load_report(target_date)
    if report_content:
        report_source = "Supabase DB"
    else:
        # 최신 리포트도 시도
        report_content, _ = load_report_latest()
        if report_content:
            report_source = "Supabase DB (최신)"
except:
    pass

# 2순위: 로컬 파일
if not report_content:
    today_str = datetime.now().strftime('%Y%m%d')
    report_files = [
        f"kospi_topdown_report_{today_str}.md",
        f"kospi_topdown_report_{target_date}.md",
        "kospi_topdown_report_20260215.md"
    ]
    
    for f_name in report_files:
        if os.path.exists(f_name):
            try:
                with open(f_name, "r", encoding="utf-8") as f:
                    report_content = f.read()
                report_source = f"로컬 파일 ({f_name})"
                break
            except:
                pass

if report_content:
    with st.expander(f"📄 AI 리포트 전문 보기 (Source: {report_source})", expanded=True):
        st.markdown(report_content)
else:
    st.info("아직 생성된 리포트가 없습니다. 위 '리포트 최신화' 버튼을 눌러주세요.")
