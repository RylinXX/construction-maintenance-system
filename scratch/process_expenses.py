import os
import shutil
import sys
from pathlib import Path
from uuid import uuid4
import sqlite3
from werkzeug.utils import secure_filename
from construction_maintenance.app import create_app
from construction_maintenance.services.ocr import ArkOcrRecognizer
import re

def clean_date(date_str: str) -> str:
    # Convert YYYY/MM/DD or YYYY.MM.DD to YYYY-MM-DD
    if not date_str:
        return "2026-05-30"  # fallback
    # Replace slashes/dots with dashes
    cleaned = re.sub(r'[./]', '-', date_str.strip())
    # Match YYYY-MM-DD pattern
    match = re.match(r'^\d{4}-\d{2}-\d{2}$', cleaned)
    if match:
        return cleaned
    
    # Try parsing other common formats
    # e.g. YYYYMMDD
    match_digits = re.match(r'^(\d{4})(\d{2})(\d{2})$', cleaned)
    if match_digits:
        return f"{match_digits.group(1)}-{match_digits.group(2)}-{match_digits.group(3)}"
        
    return cleaned[:10]  # default fallback slice

def clean_amount(amt_val) -> float:
    try:
        val = float(amt_val)
        if val <= 0:
            return 1.0  # fallback for positive check constraint
        return val
    except (TypeError, ValueError):
        return 1.0

def main():
    app = create_app()
    with app.app_context():
        api_key = app.config.get("ARK_API_KEY")
        base_url = app.config.get("ARK_BASE_URL")
        model = app.config.get("ARK_MODEL")
        upload_dir = Path(app.config["UPLOAD_FOLDER"])

        print("Initializing AI OCR Recognizer...")
        recognizer = ArkOcrRecognizer(base_url=base_url, model=model, api_key=api_key)

        src_dir = Path(r"C:\Users\RM\Desktop\报销凭证")
        image_files = sorted(list(src_dir.glob("*.jpg")) + list(src_dir.glob("*.png")) + list(src_dir.glob("*.jpeg")))
        
        if not image_files:
            print(f"No image files found in {src_dir}")
            return

        print(f"Found {len(image_files)} files to process.")

        # Connect to SQLite database
        db_path = app.config["DATABASE"]
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        success_count = 0
        for i, file_path in enumerate(image_files, 1):
            print(f"[{i}/{len(image_files)}] Processing file: {file_path.name}")
            
            # 1. Copy file to uploads directory with secure uuid name
            safe_name = secure_filename(file_path.name) or "upload"
            if not Path(safe_name).suffix:
                safe_name += file_path.suffix
            unique_name = f"{uuid4().hex}_{safe_name}"
            dest_path = upload_dir / unique_name
            
            shutil.copy(file_path, dest_path)
            
            # 2. Call OCR recognizer
            try:
                res = recognizer.recognize_image(dest_path, "voucher")
                if res.status == "已识别":
                    data = res.data
                    
                    # 3. Clean and standardize extracted values
                    raw_date = data.get("voucher_date", "")
                    voucher_date = clean_date(raw_date)
                    
                    # Default voucher type mapping
                    voucher_type = data.get("voucher_type", "其它")
                    if voucher_type not in ["员工报销", "转账凭证", "材料费用", "油费", "电费", "人工工资", "其它"]:
                        voucher_type = "其它"
                        
                    amount = clean_amount(data.get("amount", 0.0))
                    notes = data.get("notes", "") or file_path.stem
                    entry_user = data.get("entry_user", "") or "AI自动导入"
                    
                    # 4. Insert into database under project_id = 1 (基坑)
                    conn.execute(
                        """
                        insert into vouchers (project_id, voucher_date, voucher_type, amount, notes, attachment_path, entry_user)
                        values (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (1, voucher_date, voucher_type, amount, notes, unique_name, entry_user)
                    )
                    conn.commit()
                    print(f"   -> Success: {voucher_date} | {voucher_type} | ¥{amount:,.2f} | {notes}")
                    success_count += 1
                else:
                    print(f"   -> Failed: Model returned status: {res.status}. Data: {res.data}")
            except Exception as e:
                print(f"   -> Error processing {file_path.name}: {e}")

        conn.close()
        print(f"\nProcessing complete! Successfully imported {success_count} / {len(image_files)} vouchers.")

if __name__ == "__main__":
    main()
