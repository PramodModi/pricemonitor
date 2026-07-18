from sqlalchemy import text
from app.core.database import SessionLocal

def test_connection():
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT 1"))
        print("✅ Database connection successful")
        
        # Check all tables exist
        result = db.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result]
        print(f"\n── Tables in database ─────────────────────────")
        for table in tables:
            print(f"  ✅ {table}")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    finally:
        db.close()

test_connection()