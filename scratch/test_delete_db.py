import sqlite3
from construction_maintenance.app import create_app

app = create_app()
with app.app_context():
    # Let's check if we can delete qualification 37 or 38, or a test qualification
    # We will do a rollback transaction so we do not actually destroy user data
    db = sqlite3.connect('instance/construction.sqlite3')
    db.row_factory = sqlite3.Row
    db.execute("pragma foreign_keys = on")
    
    print("Testing qualification deletion in a transaction...")
    try:
        cursor = db.cursor()
        cursor.execute("BEGIN TRANSACTION")
        
        # Insert a temporary qualification and delete it
        cursor.execute(
            "insert into qualifications (company_id, name, certificate_no) values (?, ?, ?)",
            (2, "Test Qual", "TQ-123")
        )
        qual_id = cursor.lastrowid
        print(f"Inserted temporary qualification with ID {qual_id}")
        
        cursor.execute("delete from qualifications where id = ?", (qual_id,))
        print("Deleted temporary qualification successfully")
        
        # Try to delete qualification 37
        cursor.execute("delete from qualifications where id = ?", (37,))
        print("Deleted qualification 37 successfully")
        
        # Try to delete person 14
        cursor.execute("delete from people where id = ?", (14,))
        print("Deleted person 14 successfully")
        
        # Rollback so we don't affect real data
        db.execute("ROLLBACK")
        print("Transaction rolled back successfully. No real data was modified.")
    except Exception as e:
        print("Error during deletion:")
        import traceback
        traceback.print_exc()
        try:
            db.execute("ROLLBACK")
        except:
            pass
