import streamlit as st
from datetime import datetime

# 페이지 설정 (모바일 최적화)
st.set_page_config(
    page_title="Stock Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── 모바일 최적화 CSS (아이폰 앱 대비) ──
st.markdown("""
<style>
/* ─── 전역 폰트 ─── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* ─── 다크 호환 메트릭 카드 ─── */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
    border: 1px solid rgba(102, 126, 234, 0.15);
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(102, 126, 234, 0.15);
}

[data-testid="stMetricLabel"] {
    font-weight: 600;
    font-size: 0.85em;
    letter-spacing: 0.3px;
}

[data-testid="stMetricValue"] {
    font-weight: 700;
    font-size: 1.4em !important;
}

/* ─── 카드 컨테이너 (border=True) ─── */
[data-testid="stVerticalBlock"] > div:has(> [data-testid="stVerticalBlockBorderWrapper"]) {
    margin-bottom: 8px;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    border: 1px solid rgba(102, 126, 234, 0.12) !important;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(102, 126, 234, 0.12);
}

/* ─── 버튼 스타일 ─── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border: none;
    border-radius: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
    padding: 12px 24px;
    transition: all 0.3s ease;
}

.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4);
}

/* ─── 탭 스타일 ─── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    font-weight: 600;
    padding: 8px 16px;
}

/* ─── Expander 개선 ─── */
details[data-testid="stExpander"] {
    border-radius: 12px !important;
    border: 1px solid rgba(0, 0, 0, 0.08) !important;
}

details[data-testid="stExpander"] summary {
    font-weight: 600;
}

/* ─── 모바일 반응형 ─── */
@media (max-width: 768px) {
    .main .block-container {
        padding: 1rem 0.8rem !important;
        max-width: 100% !important;
    }
    
    [data-testid="stMetric"] {
        padding: 12px 14px;
    }
    
    [data-testid="stMetricValue"] {
        font-size: 1.2em !important;
    }
    
    h1 {
        font-size: 1.5em !important;
    }
    
    h2 {
        font-size: 1.25em !important;
    }
    
    h3 {
        font-size: 1.1em !important;
    }
    
    /* 사이드바 숨김 (모바일) */
    [data-testid="stSidebar"] {
        min-width: 0px !important;
        max-width: 0px !important;
    }
}

/* ─── 스크롤바 커스텀 (iOS 느낌) ─── */
::-webkit-scrollbar {
    width: 4px;
    height: 4px;
}

::-webkit-scrollbar-track {
    background: transparent;
}

::-webkit-scrollbar-thumb {
    background: rgba(102, 126, 234, 0.3);
    border-radius: 4px;
}

/* ─── DataFrame 스타일 ─── */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
}

/* ─── 프로그레스바 (분석 중) ─── */
.stProgress > div > div {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 8px;
}

/* ─── 알림 메시지 둥글게 ─── */
.stAlert {
    border-radius: 12px !important;
}
</style>
""", unsafe_allow_html=True)

st.title("📈 주식 분석 대시보드")
st.caption(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

st.markdown("---")

# ── 메인 내비게이션 (모바일 최적화 대형 버튼) ──
st.markdown("### 📍 메뉴")

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.markdown("### 📊 Top-Down 리포트")
        st.caption("시장 지표 · 섹터 수급 · AI 분석")
        st.page_link("pages/1_Daily_Top_Down.py", label="📊 리포트 보기", use_container_width=True)
    
with col2:
    with st.container(border=True):
        st.markdown("### 🚀 스윙 트레이딩")
        st.caption("TOP 3 추천 · 기술적 분석 · 매매 전략")
        st.page_link("pages/2_Swing_Trading.py", label="🚀 종목 분석", use_container_width=True)

col3, col4 = st.columns(2)

with col3:
    with st.container(border=True):
        st.markdown("### 📝 매매일지")
        st.caption("매매 기록 · 수익률 분석 · 복기")
        st.page_link("pages/3_Trading_Journal.py", label="📝 매매일지", use_container_width=True)

with col4:
    with st.container(border=True):
        st.markdown("### 📈 KOSPI 차트")
        st.caption("최근 60일 일봉 · 이동평균선")
        # 미니 KOSPI 차트 표시
        try:
            from utils.data_fetcher import get_kospi_chart_data
            import plotly.graph_objects as go
            _kospi = get_kospi_chart_data(days=30)
            if not _kospi.empty:
                _fig = go.Figure(go.Scatter(
                    x=_kospi.index, y=_kospi['종가'],
                    mode='lines', fill='tozeroy',
                    line=dict(color='#667eea', width=2),
                    fillcolor='rgba(102, 126, 234, 0.1)'
                ))
                _fig.update_layout(
                    margin=dict(l=0, r=0, t=0, b=0),
                    height=120,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(visible=False),
                    yaxis=dict(visible=False),
                    showlegend=False
                )
                st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False})
        except:
            st.caption("차트 로딩 중...")

st.markdown("---")

# 데이터 갱신 버튼
if st.button("🔄 데이터 캐시 초기화 (새로고침)", type="primary", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #888; font-size: 0.85em;'>"
    "Made by <b>Antigravity</b> | Powered by <code>pykrx</code> & <code>Streamlit</code>"
    "</p>", 
    unsafe_allow_html=True
)

