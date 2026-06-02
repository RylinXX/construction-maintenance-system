import os
import sys
from pathlib import Path
from construction_maintenance.app import create_app
from construction_maintenance.services.ocr import ArkOcrRecognizer

app = create_app()
with app.app_context():
    api_key = app.config.get("ARK_API_KEY")
    base_url = app.config.get("ARK_BASE_URL")
    model = app.config.get("ARK_MODEL")

    print(f"API Key: {api_key[:10]}...{api_key[-5:] if api_key else ''}")
    print(f"Base URL: {base_url}")
    print(f"Model: {model}")

    recognizer = ArkOcrRecognizer(base_url=base_url, model=model, api_key=api_key)
    
    # Try recognizing a simple file
    image_dir = Path(r"C:\Users\RM\Desktop\报销凭证")
    # find first jpg
    jpg_files = list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png"))
    if not jpg_files:
        print("No image files found in C:\\Users\\RM\\Desktop\\报销凭证")
        sys.exit(1)
        
    test_file = jpg_files[0]
    print(f"Testing OCR on: {test_file.name}")
    res = recognizer.recognize_image(test_file, "voucher")
    print(f"Status: {res.status}")
    print(f"Data: {res.data}")
    print(f"Confidence: {res.confidence}")
