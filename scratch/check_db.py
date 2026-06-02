import sqlite3

conn = sqlite3.connect('instance/construction.sqlite3')
conn.row_factory = sqlite3.Row

print("TABLES:")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    tname = t['name']
    print(f"\nTable: {tname}")
    # columns
    columns = conn.execute(f"PRAGMA table_info({tname})").fetchall()
    print("  Columns: " + ", ".join([col['name'] for col in columns]))
    # foreign keys
    fks = conn.execute(f"PRAGMA foreign_key_list({tname})").fetchall()
    if fks:
        print("  Foreign Keys:")
        for fk in fks:
            print(f"    {fk['from']} -> {fk['table']}({fk['to']})")
