import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import date

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
DATA_FILE = os.path.join(DATA_DIR, "trade_journal.csv")

# data/ 디렉토리 자동 생성
os.makedirs(DATA_DIR, exist_ok=True)

st.header("📝 Trading Journal")
st.caption("매매 기록을 관리하고 복기하세요.")

# 데이터 로드
REQUIRED_COLS = ["Date", "Ticker", "Type", "Price", "Qty", "Note"]

if os.path.exists(DATA_FILE):
    try:
        df = pd.read_csv(DATA_FILE)
        # 컬럼 검증 및 누락 컬럼 추가
        for col in REQUIRED_COLS:
            if col not in df.columns:
                df[col] = "" if col in ["Ticker", "Type", "Note"] else 0
    except Exception:
        df = pd.DataFrame(columns=REQUIRED_COLS)
else:
    df = pd.DataFrame(columns=REQUIRED_COLS)

# 입력 폼 (Expander로 깔끔하게 정리)
with st.expander("➕ 새 매매 기록 추가하기", expanded=False):
    with st.form("trade_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        trade_date = col1.date_input("날짜", date.today())
        ticker = col2.text_input("종목명")

        col3, col4, col5 = st.columns(3)
        trade_type = col3.selectbox("구분", ["매수", "매도"])
        price = col4.number_input("가격", min_value=0, step=100)
        qty = col5.number_input("수량", min_value=1, step=1)

        note = st.text_area("매매 메모/원칙", placeholder="진입/청산 근거를 기록하세요.")

        submitted = st.form_submit_button("기록 저장", type="primary", use_container_width=True)

        if submitted:
            new_data = pd.DataFrame([{
                "Date": trade_date,
                "Ticker": ticker,
                "Type": trade_type,
                "Price": price,
                "Qty": qty,
                "Note": note
            }])
            df = pd.concat([df, new_data], ignore_index=True)
            df.to_csv(DATA_FILE, index=False)
            st.success("저장되었습니다!")
            st.rerun()

# 데이터 편집 테이블
st.subheader("📋 매매 기록장")
st.caption("셀을 더블 클릭하여 내용을 수정할 수 있습니다.")

edited_df = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Date": st.column_config.DateColumn("날짜"),
        "Ticker": st.column_config.TextColumn("종목명"),
        "Type": st.column_config.SelectboxColumn("구분", options=["매수", "매도"]),
        "Price": st.column_config.NumberColumn("가격", format="%d원"),
        "Qty": st.column_config.NumberColumn("수량", format="%d주"),
        "Note": st.column_config.TextColumn("메모"),
    }
)

# 변경사항 저장 버튼
if st.button("💾 변경사항 저장 (테이블 수정 후 클릭)", use_container_width=True):
    edited_df.to_csv(DATA_FILE, index=False)
    st.success("데이터가 업데이트되었습니다.")

# ────────────────────────────────────
# 매매 통계 & 손익 분석 (P&L)
# ────────────────────────────────────
if not df.empty and 'Type' in df.columns and 'Price' in df.columns:
    st.markdown("---")
    st.subheader("📊 매매 분석")

    buy_count = len(df[df['Type'] == '매수'])
    sell_count = len(df[df['Type'] == '매도'])

    # 기본 통계
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("총 매수", f"{buy_count}회")
    m_col2.metric("총 매도", f"{sell_count}회")

    # 종목별 매수/매도 금액 계산
    df_calc = df.copy()
    df_calc['Price'] = pd.to_numeric(df_calc['Price'], errors='coerce').fillna(0)
    df_calc['Qty'] = pd.to_numeric(df_calc['Qty'], errors='coerce').fillna(0)
    df_calc['금액'] = df_calc['Price'] * df_calc['Qty']

    total_buy_amount = df_calc[df_calc['Type'] == '매수']['금액'].sum()
    total_sell_amount = df_calc[df_calc['Type'] == '매도']['금액'].sum()

    m_col3.metric("총 매수금액", f"{total_buy_amount:,.0f}원")
    m_col4.metric("총 매도금액", f"{total_sell_amount:,.0f}원")

    # ── 종목별 실현 손익 계산 (FIFO 방식) ──
    st.markdown("---")
    st.subheader("💰 종목별 실현 손익 (P&L)")

    tickers = df_calc[df_calc['Ticker'].str.strip() != '']['Ticker'].unique()

    pnl_records = []
    for tk in tickers:
        tk_df = df_calc[df_calc['Ticker'] == tk].sort_values('Date')
        buy_queue = []  # FIFO 큐: [(price, qty), ...]
        realized_pnl = 0.0
        total_buy_qty = 0
        total_sell_qty = 0

        for _, row in tk_df.iterrows():
            if row['Type'] == '매수' and row['Qty'] > 0:
                buy_queue.append((row['Price'], row['Qty']))
                total_buy_qty += row['Qty']
            elif row['Type'] == '매도' and row['Qty'] > 0:
                sell_qty = row['Qty']
                sell_price = row['Price']
                total_sell_qty += sell_qty

                # FIFO 매칭
                while sell_qty > 0 and buy_queue:
                    buy_price, buy_qty = buy_queue[0]
                    match_qty = min(sell_qty, buy_qty)
                    realized_pnl += (sell_price - buy_price) * match_qty
                    sell_qty -= match_qty
                    if match_qty >= buy_qty:
                        buy_queue.pop(0)
                    else:
                        buy_queue[0] = (buy_price, buy_qty - match_qty)

        # 잔여 보유 수량
        remaining_qty = sum(q for _, q in buy_queue)
        avg_cost = sum(p * q for p, q in buy_queue) / remaining_qty if remaining_qty > 0 else 0

        pnl_records.append({
            "종목명": tk,
            "매수 횟수": int(total_buy_qty),
            "매도 횟수": int(total_sell_qty),
            "실현손익": round(realized_pnl),
            "잔여수량": int(remaining_qty),
            "평균매수가": round(avg_cost),
        })

    if pnl_records:
        df_pnl = pd.DataFrame(pnl_records)
        total_realized = df_pnl['실현손익'].sum()

        # 총 실현 손익
        pnl_color = "#2ecc71" if total_realized >= 0 else "#e74c3c"
        st.markdown(
            f"<h3 style='color:{pnl_color};'>총 실현 손익: {total_realized:+,.0f}원</h3>",
            unsafe_allow_html=True
        )

        # 종목별 P&L 테이블
        st.dataframe(
            df_pnl,
            use_container_width=True,
            hide_index=True,
            column_config={
                "실현손익": st.column_config.NumberColumn("실현손익", format="%+,.0f원"),
                "평균매수가": st.column_config.NumberColumn("평균매수가", format="%,.0f원"),
            }
        )

        # P&L 차트 (종목별 바 차트)
        if len(df_pnl[df_pnl['실현손익'] != 0]) > 0:
            df_pnl_chart = df_pnl[df_pnl['실현손익'] != 0].sort_values('실현손익', ascending=True)
            fig_pnl = go.Figure(go.Bar(
                x=df_pnl_chart['실현손익'],
                y=df_pnl_chart['종목명'],
                orientation='h',
                marker_color=[
                    '#2ecc71' if v >= 0 else '#e74c3c'
                    for v in df_pnl_chart['실현손익']
                ],
                text=df_pnl_chart['실현손익'].apply(lambda x: f"{x:+,.0f}원"),
                textposition='outside'
            ))
            fig_pnl.update_layout(
                height=max(200, len(df_pnl_chart) * 40),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=10, r=80, t=10, b=10),
                xaxis=dict(title='실현손익(원)', showgrid=True, gridcolor='rgba(200,200,200,0.3)'),
                yaxis=dict(title=None),
                showlegend=False
            )
            st.plotly_chart(fig_pnl, use_container_width=True)
    else:
        st.info("매매 기록이 없습니다.")
