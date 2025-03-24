from fastapi import FastAPI, HTTPException, APIRouter
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
from ..config import DB_HOST,DB_NAME,DB_USER,DB_PASSWORD

# Azure PostgreSQL Connection Details

# Connect to PostgreSQL
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            sslmode="require",
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print("Database connection error:", e)
        return None

router = APIRouter(prefix="/chathistory", tags=["Chat History"])
# ✅ **1. Store Chat Message in Database**
@router.post("/history")
async def store_chat_history(user_id: int, message: str, response: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO chat_history (user_id, message, response, timestamp)
            VALUES (%s, %s, %s, %s)
        """, (user_id, message, response, datetime.utcnow()))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ **2. Retrieve Chat History for a User**
@router.get("history/{user_id}")
async def get_chat_history(user_id: int):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT message, response, timestamp
            FROM chat_history
            WHERE user_id = %s
            ORDER BY timestamp DESC
            LIMIT 10
        """, (user_id,))
        
        history = cur.fetchall()
        cur.close()
        conn.close()
        
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
