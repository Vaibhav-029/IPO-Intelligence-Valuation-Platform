import sqlite3
conn = sqlite3.connect('ipo_intelligence.db')
print(conn.execute("SELECT sql FROM sqlite_master WHERE name='sources'").fetchone()[0])
