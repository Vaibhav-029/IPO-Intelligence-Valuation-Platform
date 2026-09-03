import sqlite3
conn = sqlite3.connect('ipo_intelligence.db')
conn.execute("UPDATE alembic_version SET version_num='f16da429c593'")
conn.commit()
conn.close()
