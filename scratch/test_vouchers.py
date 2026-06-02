from construction_maintenance.app import create_app
from construction_maintenance.repositories import list_vouchers

app = create_app()
with app.app_context():
    vouchers = list_vouchers(1)
    print(f"Total: {len(vouchers)}")
    for v in vouchers[:5]:
        print(v['id'], v['voucher_date'], v['voucher_type'], v['amount'])
