"""
Supabase 클라이언트 유틸리티
- 환경변수 또는 Streamlit secrets에서 인증 정보를 가져옵니다.
- Vercel/Streamlit Cloud 배포 시에도 동작합니다.
"""
import os
import streamlit as st

# .env 파일 로드 (로컬 개발용)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_supabase_client():
    """
    Supabase 클라이언트를 생성합니다.
    우선순위: Streamlit secrets > 환경변수 > None
    """
    try:
        from supabase import create_client, Client
    except ImportError:
        st.error("supabase 패키지가 설치되지 않았습니다. `pip install supabase` 를 실행해주세요.")
        return None
    
    # 1순위: Streamlit secrets (Streamlit Cloud / 배포 환경)
    url = None
    key = None
    
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except (FileNotFoundError, KeyError):
        pass
    
    # 2순위: 환경변수 (Vercel / 로컬 .env)
    if not url:
        url = os.environ.get("SUPABASE_URL")
    if not key:
        key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        return None
    
    try:
        client: Client = create_client(url, key)
        return client
    except Exception as e:
        st.error(f"Supabase 연결 실패: {e}")
        return None


def save_report(target_date: str, report_content: str) -> bool:
    """
    리포트를 Supabase에 저장합니다 (upsert).
    테이블: reports
    """
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        data = {
            "target_date": target_date,
            "content": report_content,
            "report_type": "topdown"
        }
        # upsert: target_date가 같으면 덮어쓰기
        result = client.table("reports").upsert(
            data, 
            on_conflict="target_date,report_type"
        ).execute()
        return True
    except Exception as e:
        st.warning(f"Supabase 저장 실패 (로컬 파일에 저장됨): {e}")
        return False


def load_report(target_date: str) -> str | None:
    """
    Supabase에서 리포트를 조회합니다.
    가장 최신 리포트를 반환합니다.
    """
    client = get_supabase_client()
    if not client:
        return None
    
    try:
        # 1. 특정 날짜 리포트 조회
        result = client.table("reports").select("content, created_at").eq(
            "target_date", target_date
        ).eq(
            "report_type", "topdown"
        ).order(
            "created_at", desc=True
        ).limit(1).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]["content"]
        
        # 2. 없으면 가장 최신 리포트
        result = client.table("reports").select("content, target_date, created_at").eq(
            "report_type", "topdown"
        ).order(
            "created_at", desc=True
        ).limit(1).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]["content"]
        
        return None
    except Exception as e:
        return None


def load_report_latest() -> tuple[str | None, str | None]:
    """
    가장 최신 리포트와 해당 날짜를 반환합니다.
    Returns: (content, target_date) 또는 (None, None)
    """
    client = get_supabase_client()
    if not client:
        return None, None

    try:
        result = client.table("reports").select("content, target_date, created_at").eq(
            "report_type", "topdown"
        ).order(
            "created_at", desc=True
        ).limit(1).execute()

        if result.data and len(result.data) > 0:
            row = result.data[0]
            return row["content"], row["target_date"]

        return None, None
    except Exception as e:
        return None, None


# ═══════════════════════════════════════
# 스윙 분석 결과 조회 (GitHub Actions가 저장한 데이터)
# ═══════════════════════════════════════
def load_swing_results(target_date: str = None):
    """
    Supabase에서 스윙 분석 결과를 조회합니다.

    Args:
        target_date: 특정 날짜 (None이면 최신)

    Returns:
        (df_result, top_picks, source_date) 또는 (None, None, None)
    """
    import json
    import pandas as pd

    client = get_supabase_client()
    if not client:
        return None, None, None

    try:
        query = client.table("analysis_results").select(
            "results_json, top_picks_json, target_date, created_at"
        ).eq("result_type", "swing")

        if target_date:
            query = query.eq("target_date", target_date)

        result = query.order("created_at", desc=True).limit(1).execute()

        if not result.data or len(result.data) == 0:
            return None, None, None

        row = result.data[0]

        # JSON → DataFrame 복원
        df_result = pd.read_json(row["results_json"], orient='records')

        # 태그 복원 (JSON 문자열 → 리스트)
        if '태그' in df_result.columns:
            def parse_tags(x):
                if isinstance(x, list):
                    return x
                try:
                    return json.loads(x)
                except:
                    return []
            df_result['태그'] = df_result['태그'].apply(parse_tags)

        top_picks = json.loads(row["top_picks_json"])

        # top_picks의 태그도 복원
        for pick in top_picks:
            if '태그' in pick and isinstance(pick['태그'], str):
                try:
                    pick['태그'] = json.loads(pick['태그'])
                except:
                    pick['태그'] = []

        return df_result, top_picks, row["target_date"]

    except Exception as e:
        return None, None, None
