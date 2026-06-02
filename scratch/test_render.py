import sys
from pathlib import Path
from construction_maintenance.app import create_app

app = create_app()
with app.test_client() as client:
    # qualifications page
    res_qual = client.get("/qualifications")
    Path("scratch/rendered_qualifications.html").write_bytes(res_qual.data)
    print("Rendered qualifications page to scratch/rendered_qualifications.html")

    # people page
    res_people = client.get("/people")
    Path("scratch/rendered_people.html").write_bytes(res_people.data)
    print("Rendered people page to scratch/rendered_people.html")
