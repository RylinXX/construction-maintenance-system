import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

db = sqlite3.connect('instance/construction.sqlite3')
db.row_factory = sqlite3.Row

# Query categories
categories = db.execute("SELECT id, name, is_active FROM expense_categories").fetchall()
print("EXPENSE CATEGORIES:")
for c in categories:
    print(f"ID: {c['id']}, Name: {c['name']}, Active: {c['is_active']}")

# Query AI-imported vouchers
ai_vouchers = db.execute("SELECT id, voucher_date, voucher_type, amount, entry_user, notes FROM vouchers WHERE entry_user LIKE '%AI%'").fetchall()
print(f"\nAI-IMPORTED VOUCHERS COUNT: {len(ai_vouchers)}")
for v in ai_vouchers:
    print(f"ID: {v['id']}, Date: {v['voucher_date']}, Type: {v['voucher_type']}, Amount: {v['amount']}, User: {v['entry_user']}, Notes: {v['notes']}")

db.close()
