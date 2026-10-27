import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "orunex_knowledge.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS AgentMemory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            topic TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_memory(agent_name: str, topic: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO AgentMemory (agent_name, topic, content)
        VALUES (?, ?, ?)
    ''', (agent_name, topic, content))
    conn.commit()
    conn.close()

def get_memories(agent_name: str, limit: int = 5) -> str:
    """Returns a formatted string of the most recent memories for an agent."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT topic, content FROM AgentMemory 
        WHERE agent_name = ? 
        ORDER BY timestamp DESC LIMIT ?
    ''', (agent_name, limit))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return ""
    
    memories = ""
    for row in rows:
        memories += f"{row[0]}: {row[1]}\n"
    return memories + "\n"

def clear_all_memories():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM AgentMemory")
    conn.commit()
    conn.close()

# Inicializar DB al importar
init_db()
