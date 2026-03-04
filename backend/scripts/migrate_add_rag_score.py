"""Migration script to add rag_score column to scores table."""
from sqlalchemy import text
from backend.app.db import engine

def migrate():
    with engine.connect() as conn:
        # Check if column already exists
        inspector = __import__('sqlalchemy.inspect', fromlist=['inspect']).inspect(engine)
        columns = [c['name'] for c in inspector.get_columns('scores')]
        
        if 'rag_score' in columns:
            print("Column 'rag_score' already exists. Skipping migration.")
            return
        
        # Add the column
        conn.execute(text('ALTER TABLE scores ADD COLUMN rag_score REAL DEFAULT 0.0'))
        conn.commit()
        print("✅ Successfully added 'rag_score' column to scores table")

if __name__ == '__main__':
    migrate()

