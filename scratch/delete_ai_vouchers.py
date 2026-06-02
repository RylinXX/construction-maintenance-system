import sqlite3

db = sqlite3.connect('instance/construction.sqlite3')
cursor = db.execute("DELETE FROM vouchers WHERE entry_user = 'AI自动导入'")
db.commit()
print(f"Deleted {cursor.rowcount} vouchers.")
db.close()
