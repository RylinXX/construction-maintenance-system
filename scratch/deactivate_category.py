import sqlite3

db = sqlite3.connect('instance/construction.sqlite3')
cursor = db.execute("UPDATE expense_categories SET is_active = 0 WHERE name = '转账凭证'")
db.commit()
print(f"Deactivated category '转账凭证' (rows affected: {cursor.rowcount}).")
db.close()
