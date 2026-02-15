import streamlit as st
import pandas as pd
import os
from datetime import date

st.set_page_config(page_title="Trading Journal", page_icon="📝", layout="wide")

DATA_FILE = "data/trade_journal.csv"

st.header("📝 Trading Journal")
st.caption("매매 기록을 관리하고 복기하세요.")

# 데이터 로드
if os.path.exists(DATA_FILE):
    try:
        df = pd.read_csv(DATA_FILE)
    except:
        df = pd.DataFrame(columns=["Date", "Ticker", "Type", "Price", "Qty", "Note"])
else:
    df = pd.DataFrame(columns=["Date", "Ticker", "Type", "Price", "Qty", "Note"])

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
            # 데이터 연결 (concat 사용 권장)
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
        "Price": st.column_config.NumberColumn("가격", format="%d원"),
        "Qty": st.column_config.NumberColumn("수량", format="%d주"),
    }
)

# 변경사항 저장 버튼
if st.button("💾 변경사항 저장 (테이블 수정 후 클릭)", use_container_width=True):
    edited_df.to_csv(DATA_FILE, index=False)
    st.success("데이터가 업데이트되었습니다.")

# 간단 통계 (데이터 있을 경우)
if not df.empty and 'Type' in df.columns:
    st.markdown("---")
    st.subheader("📊 매매 요약")
    
    buy_count = len(df[df['Type'] == '매수'])
    sell_count = len(df[df['Type'] == '매도'])
    
    m_col1, m_col2 = st.columns(2)
    m_col1.metric("총 매수 횟수", f"{buy_count}회")
    m_col2.metric("총 매도 횟수", f"{sell_count}회")
