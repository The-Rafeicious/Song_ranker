import sqlite3

conn = sqlite3.connect("song_ranker_v2.db")
print("history:", [r[1] for r in conn.execute("PRAGMA table_info(history)")])
print("elo_history:", [r[1] for r in conn.execute("PRAGMA table_info(elo_history)")])
conn.close()