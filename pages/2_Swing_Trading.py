import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
import os

# utils 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.analysis import run_swing_analysis

st.header("🚀 Swing Trading Report")
st.caption("알고리즘 기반 스윙 종목 추천 (Foreign/Inst Net Buy + Tech Signals)")

# 분석 실행 버튼
if st.button("🔍 시장 분석 및 종목 추출 실행", type="primary", use_container_width=True):
    with st.spinner("데이터 수집 및 분석 중입니다... (약 30초 소요)"):
        # 분석 실행
        df_result, top3 = run_swing_analysis()
        
        if df_result.empty:
            st.warning("조건에 맞는 종목이 없습니다.")
        else:
            st.success(f"분석 완료! 총 {len(df_result)}개 종목이 추출되었습니다.")
            
            # ────────────────────────────────────
            # 1. TOP 3 카드 뷰 (모바일 최적화)
            # ────────────────────────────────────
            st.subheader("🏆 오늘의 TOP 3 추천")
            st.caption("AI 알고리즘이 선정한 최고의 스윙 트레이딩 기회입니다.")
            
            cols = st.columns(3)
            for i, stock_item in enumerate(top3):
                with cols[i]:
                    with st.container(border=True):
                        # 헤더
                        medal = ["🥇", "🥈", "🥉"][i]
                        st.markdown(f"### {medal} {stock_item['종목명']}")
                        
                        # 섹터 + Code
                        sector_info = stock_item.get('Sector', '')
                        rsi_info = f" | RSI: {stock_item['RSI']}" if 'RSI' in stock_item else ""
                        st.caption(f"{sector_info} | {stock_item['Code']}{rsi_info}")
                        
                        # 가격 정보
                        st.metric(
                            label="현재가", 
                            value=f"{stock_item['현재가']:,}원", 
                            delta=f"{stock_item['등락률']:+.2f}%"
                        )
                        
                        # 핵심 태그 (뱃지)
                        tags = stock_item.get('태그', [])
                        if isinstance(tags, list) and tags:
                            tag_html = " ".join([
                                f"<span style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); "
                                f"color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.75em; "
                                f"margin: 2px; display: inline-block;'>#{t}</span>" 
                                for t in tags
                            ])
                            st.markdown(tag_html, unsafe_allow_html=True)
                        
                        st.divider()
                        
                        # 스윙 점수 바
                        score = stock_item.get('스윙점수', 0)
                        score_color = "#2ecc71" if score >= 50 else ("#f39c12" if score >= 30 else "#e74c3c")
                        st.markdown(f"""
                        <div style='background: #f0f2f6; border-radius: 8px; padding: 2px; margin-bottom: 8px;'>
                            <div style='background: {score_color}; width: {min(score, 100)}%; border-radius: 8px; 
                                        padding: 4px 8px; color: white; font-size: 0.85em; font-weight: bold;
                                        text-align: center; min-width: 40px;'>
                                {score}점
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 목표/손절가 (색상 강조)
                        c1, c2 = st.columns(2)
                        with c1:
                            target_rate = stock_item.get('목표수익률', 0)
                            st.markdown("**🎯 목표가**")
                            st.markdown(
                                f"<span style='color:#d62728; font-size:1.1em; font-weight:bold;'>"
                                f"{stock_item['목표가']:,}원</span><br>"
                                f"<span style='color:#d62728; font-size:0.85em;'>({target_rate:+.1f}%)</span>", 
                                unsafe_allow_html=True
                            )
                        with c2:
                            stop_rate = stock_item.get('손절수익률', 0)
                            st.markdown("**🛡️ 손절가**")
                            st.markdown(
                                f"<span style='color:#1f77b4; font-size:1.1em; font-weight:bold;'>"
                                f"{stock_item['손절가']:,}원</span><br>"
                                f"<span style='color:#1f77b4; font-size:0.85em;'>({stop_rate:+.1f}%)</span>", 
                                unsafe_allow_html=True
                            )

                        # 배당 정보
                        if stock_item.get('배당수익률', 0) > 0:
                             st.caption(f"💰 배당수익률: {stock_item['배당수익률']}%")
                        
                        # AI 분석 코멘트 (Expander)
                        with st.expander("💡 AI 분석 코멘트", expanded=False):
                            st.info(stock_item['추천사유'])

            # ────────────────────────────────────
            # 2. 전체 스크리닝 결과 테이블
            # ────────────────────────────────────
            st.divider()
            st.subheader("📋 전체 스크리닝 결과")
            
            # 표시할 컬럼 정의 (모바일 최적화)
            display_cols = ['종목명', 'Sector', '현재가', '등락률', '스윙점수', '목표수익률', '손절수익률', 'RSI']
            available_cols = [c for c in display_cols if c in df_result.columns]
            display_df = df_result[available_cols]
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "종목명": st.column_config.TextColumn("종목명", width="medium"),
                    "Sector": st.column_config.TextColumn("업종", width="small"),
                    "현재가": st.column_config.NumberColumn("현재가", format="%d원"),
                    "등락률": st.column_config.NumberColumn("등락률", format="%.2f%%"),
                    "스윙점수": st.column_config.ProgressColumn("점수", min_value=0, max_value=100, format="%.1f점"),
                    "목표수익률": st.column_config.NumberColumn("목표%", format="%.1f%%"),
                    "손절수익률": st.column_config.NumberColumn("손절%", format="%.1f%%"),
                    "RSI": st.column_config.NumberColumn("RSI", format="%.1f"),
                }
            )
            
            # ────────────────────────────────────
            # 3. 개별 종목 상세 (Expander)
            # ────────────────────────────────────
            st.divider()
            st.subheader("🔎 종목별 상세 분석")
            st.caption("각 종목을 펼치면 AI 분석 코멘트와 매매 전략을 확인할 수 있습니다.")
            
            for _, row in df_result.iterrows():
                score_emoji = "🟢" if row['스윙점수'] >= 50 else ("🟡" if row['스윙점수'] >= 30 else "🔴")
                with st.expander(f"{score_emoji} {row['종목명']} ({row.get('Sector', '')}) — {row['스윙점수']}점"):
                    # 2열 레이아웃
                    d_c1, d_c2 = st.columns(2)
                    with d_c1:
                        st.metric("현재가", f"{row['현재가']:,}원", f"{row['등락률']:+.2f}%")
                        st.metric("RSI", f"{row['RSI']:.1f}")
                    with d_c2:
                        st.metric("🎯 목표가", f"{row['목표가']:,}원", f"{row['목표수익률']:+.1f}%")
                        st.metric("🛡️ 손절가", f"{row['손절가']:,}원", f"{row['손절수익률']:+.1f}%", delta_color="inverse")
                    
                    # 태그
                    tags = row.get('태그', [])
                    if isinstance(tags, list) and tags:
                        tag_html = " ".join([
                            f"<span style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); "
                            f"color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.75em;'>#{t}</span>"
                            for t in tags
                        ])
                        st.markdown(tag_html, unsafe_allow_html=True)
                    
                    # 추천 사유
                    st.markdown("---")
                    st.markdown(f"**💡 AI 분석**: {row['추천사유']}")
