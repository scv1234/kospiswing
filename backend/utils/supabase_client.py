"""Supabase 클라이언트 (FastAPI용 — streamlit 의존성 제거)"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_supabase_client():
    try:
        from supabase import create_client, Client
    except ImportError:
        return None
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        return None
    
    try:
        return create_client(url, key)
    except:
        return None


def save_report(target_date: str, report_content: str) -> bool:
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("reports").upsert(
            {"target_date": target_date, "content": report_content, "report_type": "topdown"},
            on_conflict="target_date,report_type"
        ).execute()
        return True
    except:
        return False


def load_report(target_date: str) -> str | None:
    client = get_supabase_client()
    if not client:
        return None
    try:
        result = client.table("reports").select("content").eq(
            "target_date", target_date
        ).eq("report_type", "topdown").order("created_at", desc=True).limit(1).execute()
        if result.data:
            return result.data[0]["content"]
        return None
    except:
        return None


def load_report_latest() -> tuple[str | None, str | None]:
    client = get_supabase_client()
    if not client:
        return None, None
    try:
        result = client.table("reports").select("content, target_date").eq(
            "report_type", "topdown"
        ).order("created_at", desc=True).limit(1).execute()
        if result.data:
            return result.data[0]["content"], result.data[0]["target_date"]
        return None, None
    except:
        return None, None
