import sqlite3
conn = sqlite3.connect('./data/homecloud.db')
cursor = conn.execute('SELECT name FROM sqlite_master WHERE type="table"')
print([row[0] for row in cursor])
conn.close()
