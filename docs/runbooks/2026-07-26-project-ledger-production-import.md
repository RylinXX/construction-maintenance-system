# Project Ledger Production Import Runbook

Date: 2026-07-26

This runbook deploys the tested release and imports the approved six-project
ledger archive. Run every gate in order. Commands marked "local" run from the
release workstation; all other commands run as `root` on the production host.

## Scope

| Item | Path or name |
| --- | --- |
| Local release | `/Users/rylinx/Documents/ylt-PAM` |
| Production SSH target | `root@192.144.171.234` |
| Remote application | `/root/cam` |
| Remote database | `/root/cam/instance/construction.sqlite3` |
| Remote uploads | `/root/cam/uploads` |
| Remote service | `cam.service` |
| Remote Nginx site | `/www/server/panel/vhost/nginx/pam.etgq.com.conf` |
| Staged source archive | `/root/cam-deploy/imports/各项目独立账套_汇总.zip` |
| Backup root | `/root/cam-backups/${pam_release_stamp}` |

## Acceptance Values

The dry-run and final database checks must match all of these values exactly:

```text
projects=6
entries=4907
review_entries=483
pending_items=276
expense=11643311.78
expense_reduction=17573.00
net_expense=11625738.78
income=43670.00
fund_transfer=50128.83
```

The planned pre-deploy demo baseline is 12 projects, 3 vouchers, and 2
contracts. Record the live values even if they differ. Stop and investigate an
unexpected baseline before continuing.

## 1. Validate The Local Release

Run locally:

```bash
cd /Users/rylinx/Documents/ylt-PAM
git status --short
git rev-parse HEAD
.venv/bin/pytest -q
CAM_AUTH_REQUIRED=0 CAM_SESSION_COOKIE_SECURE=0 .venv/bin/flask --app construction_maintenance ledger-import '/Users/rylinx/Downloads/各项目独立账套_汇总.zip'
```

The dry-run must report 6 projects, 4,907 entries, 276 pending items, and the
five exact financial totals above. The CLI preview does not display
`review_entries`; the copy verifier and post-import SQL verify its exact value.

## 2. Record Pre-Deploy Counts

Open one remote shell and keep it open through backup and Nginx configuration
so the same `pam_release_stamp` is used throughout:

```bash
ssh root@192.144.171.234
set -euo pipefail
pam_release_stamp=$(date +%Y%m%d_%H%M%S)
pam_backup_dir="/root/cam-backups/${pam_release_stamp}"
mkdir -p "$pam_backup_dir"
printf '%s\n' "$pam_backup_dir"

sqlite3 -separator '|' /root/cam/instance/construction.sqlite3 <<'SQL' \
  | tee "$pam_backup_dir/predeploy-protected-counts.psv"
select 'companies', count(*) from companies
union all select 'people', count(*) from people
union all select 'qualifications', count(*) from qualifications
union all select 'attendance', count(*) from attendance
union all select 'salary_payments', count(*) from salary_payments
union all select 'salary_sheets', count(*) from salary_sheets
union all select 'admin_users', count(*) from admin_users
union all select 'system_settings', count(*) from system_settings;
SQL

sqlite3 -separator '|' /root/cam/instance/construction.sqlite3 <<'SQL' \
  | tee "$pam_backup_dir/predeploy-ledger-counts.psv"
select 'projects', count(*) from projects
union all select 'vouchers', count(*) from vouchers
union all select 'contracts', count(*) from contracts;
SQL
```

Keep the printed backup directory for every later command and for release
evidence.

## 3. Stop Writes And Back Up

Continue in the same remote shell:

```bash
systemctl stop cam.service
sqlite3 /root/cam/instance/construction.sqlite3 ".backup '/root/cam-backups/${pam_release_stamp}/construction.sqlite3'"
tar -C /root/cam -czf "/root/cam-backups/${pam_release_stamp}/uploads.tar.gz" uploads
tar -C /root -czf "/root/cam-backups/${pam_release_stamp}/cam-code.tar.gz" cam

test -s "$pam_backup_dir/construction.sqlite3"
test -s "$pam_backup_dir/uploads.tar.gz"
test -s "$pam_backup_dir/cam-code.tar.gz"
ls -lh "$pam_backup_dir/construction.sqlite3" \
  "$pam_backup_dir/uploads.tar.gz" \
  "$pam_backup_dir/cam-code.tar.gz"
```

Do not deploy unless all three backup artifacts exist and are non-empty. Leave
`cam.service` stopped until the import has completed.

## 4. Verify The Backup Copy

In a second local terminal, replace `<release-stamp>` with the value printed in
Step 2. This applies the import only to a temporary local copy:

```bash
cd /Users/rylinx/Documents/ylt-PAM
pam_release_stamp='<release-stamp>'
pam_verify_dir=$(mktemp -d /tmp/pam-ledger-verify.XXXXXX)
scp \
  "root@192.144.171.234:/root/cam-backups/${pam_release_stamp}/construction.sqlite3" \
  "$pam_verify_dir/construction.sqlite3"
.venv/bin/python scripts/verify_ledger_import_copy.py \
  --database "$pam_verify_dir/construction.sqlite3" \
  --source '/Users/rylinx/Downloads/各项目独立账套_汇总.zip'
```

Expected output is one JSON object. Its `protected` counts must match the
pre-deploy snapshot, and its `import` object must match every acceptance value.
Successful completion also proves internally that a second import inserts zero
entries and zero pending items.

## 5. Stage The Release And Source

Run locally:

```bash
rsync -av \
  --exclude '.venv/' \
  --exclude 'instance/' \
  --exclude 'uploads/' \
  --exclude 'exports/' \
  --exclude '__pycache__/' \
  /Users/rylinx/Documents/ylt-PAM/ root@192.144.171.234:/root/cam/
ssh root@192.144.171.234 'mkdir -p /root/cam-deploy/imports'
scp '/Users/rylinx/Downloads/各项目独立账套_汇总.zip' \
  'root@192.144.171.234:/root/cam-deploy/imports/各项目独立账套_汇总.zip'
```

The exclusions preserve the virtual environment, database, uploads, exports,
and generated bytecode.

## 6. Install And Dry-Run

In the original remote shell:

```bash
cd /root/cam
.venv/bin/pip install -e .
CAM_AUTH_REQUIRED=0 CAM_SESSION_COOKIE_SECURE=0 .venv/bin/flask --app construction_maintenance ledger-import '/root/cam-deploy/imports/各项目独立账套_汇总.zip' | tee "$pam_backup_dir/dry-run.txt"
```

Compare the output to the acceptance values before continuing. This command is
a preview and must not change ledger rows.

## 7. Apply The Import

Run exactly once in the same remote shell:

```bash
cd /root/cam
CAM_AUTH_REQUIRED=0 CAM_SESSION_COOKIE_SECURE=0 .venv/bin/flask --app construction_maintenance ledger-import '/root/cam-deploy/imports/各项目独立账套_汇总.zip' --apply --replace-demo-projects | tee "$pam_backup_dir/apply.txt"
```

The import is transactional. An exception must leave the pre-import
project/voucher/contract state unchanged. Do not retry an uncertain result;
run the SQL acceptance checks first.

## 8. Start And Check The Service

```bash
systemctl start cam.service
systemctl is-active cam.service | tee "$pam_backup_dir/service-status.txt"
curl -fsS -o /dev/null -w '%{http_code}\n' \
  https://pam.etgq.com/login | tee "$pam_backup_dir/login-status.txt"
journalctl -u cam.service --since "15 minutes ago" --no-pager \
  | tail -n 100 > "$pam_backup_dir/service-log-tail.txt"
```

Expected results are `active`, HTTP `200`, and no startup or request exception
in the captured service log.

## 9. Back Up And Harden Nginx

Use the same remote shell and release stamp. The following commands set TLS
1.2/1.3, the 20 MB upload limit, and all three proxy timeouts. Configuration is
tested before reload.

```bash
cp /www/server/panel/vhost/nginx/pam.etgq.com.conf \
  "/root/cam-backups/${pam_release_stamp}/pam.etgq.com.conf"
test -s "$pam_backup_dir/pam.etgq.com.conf"

if grep -Eq '^[[:space:]]*ssl_protocols[[:space:]]' \
  /www/server/panel/vhost/nginx/pam.etgq.com.conf; then
  sed -i -E \
    's/^[[:space:]]*ssl_protocols .*/    ssl_protocols TLSv1.2 TLSv1.3;/' \
    /www/server/panel/vhost/nginx/pam.etgq.com.conf
else
  sed -i '/server_name pam.etgq.com;/a\    ssl_protocols TLSv1.2 TLSv1.3;' \
    /www/server/panel/vhost/nginx/pam.etgq.com.conf
fi

if grep -Eq '^[[:space:]]*client_max_body_size[[:space:]]' \
  /www/server/panel/vhost/nginx/pam.etgq.com.conf; then
  sed -i -E \
    's/^[[:space:]]*client_max_body_size .*/    client_max_body_size 20m;/' \
    /www/server/panel/vhost/nginx/pam.etgq.com.conf
else
  sed -i '/server_name pam.etgq.com;/a\    client_max_body_size 20m;' \
    /www/server/panel/vhost/nginx/pam.etgq.com.conf
fi

sed -i -E \
  '/^[[:space:]]*proxy_(connect|send|read)_timeout[[:space:]]/d' \
  /www/server/panel/vhost/nginx/pam.etgq.com.conf
sed -i '/client_max_body_size 20m;/a\    proxy_read_timeout 120s;' \
  /www/server/panel/vhost/nginx/pam.etgq.com.conf
sed -i '/client_max_body_size 20m;/a\    proxy_send_timeout 120s;' \
  /www/server/panel/vhost/nginx/pam.etgq.com.conf
sed -i '/client_max_body_size 20m;/a\    proxy_connect_timeout 60s;' \
  /www/server/panel/vhost/nginx/pam.etgq.com.conf

grep -F 'ssl_protocols TLSv1.2 TLSv1.3;' \
  /www/server/panel/vhost/nginx/pam.etgq.com.conf
grep -F 'client_max_body_size 20m;' \
  /www/server/panel/vhost/nginx/pam.etgq.com.conf
grep -F 'proxy_connect_timeout 60s;' \
  /www/server/panel/vhost/nginx/pam.etgq.com.conf
grep -F 'proxy_send_timeout 120s;' \
  /www/server/panel/vhost/nginx/pam.etgq.com.conf
grep -F 'proxy_read_timeout 120s;' \
  /www/server/panel/vhost/nginx/pam.etgq.com.conf
nginx -t 2>&1 | tee "$pam_backup_dir/nginx-test.txt"
systemctl reload nginx
```

Do not reload Nginx if `nginx -t` fails. Restore the saved site file before
investigating further.

## 10. Verify Preservation And Exact Totals

Run the protected query again and require an empty `diff`:

```bash
sqlite3 -separator '|' /root/cam/instance/construction.sqlite3 <<'SQL' \
  > "$pam_backup_dir/postdeploy-protected-counts.psv"
select 'companies', count(*) from companies
union all select 'people', count(*) from people
union all select 'qualifications', count(*) from qualifications
union all select 'attendance', count(*) from attendance
union all select 'salary_payments', count(*) from salary_payments
union all select 'salary_sheets', count(*) from salary_sheets
union all select 'admin_users', count(*) from admin_users
union all select 'system_settings', count(*) from system_settings;
SQL
diff -u "$pam_backup_dir/predeploy-protected-counts.psv" \
  "$pam_backup_dir/postdeploy-protected-counts.psv"
```

Run the financial acceptance queries and compare every result to the approved
values:

```bash
sqlite3 -header -column /root/cam/instance/construction.sqlite3 <<'SQL' \
  | tee "$pam_backup_dir/postdeploy-ledger-acceptance.txt"
select count(distinct project_id) as projects
from vouchers
where source_record_id is not null and is_void = 0;

select count(*) as entries
from vouchers
where source_record_id is not null and is_void = 0;

select count(*) as review_entries
from vouchers
where source_record_id is not null
  and is_void = 0
  and review_status = '待复核';

select count(*) as pending_items
from ledger_pending_items
where status = '待补录';

select transaction_type,
       count(*) as records,
       printf('%.2f', sum(amount)) as amount
from vouchers
where source_record_id is not null and is_void = 0
group by transaction_type
order by transaction_type;

select printf('%.2f',
         sum(case when transaction_type = '支出' then amount else 0 end)
         - sum(case when transaction_type = '冲减支出' then amount else 0 end)
       ) as net_expense
from vouchers
where source_record_id is not null and is_void = 0;
SQL
```

Rerun the source preview and require the same accepted totals:

```bash
cd /root/cam
CAM_AUTH_REQUIRED=0 CAM_SESSION_COOKIE_SECURE=0 .venv/bin/flask --app construction_maintenance ledger-import '/root/cam-deploy/imports/各项目独立账套_汇总.zip'
```

## 11. Smoke Checks

Run unauthenticated checks without changing application data:

```bash
systemctl is-active cam.service
nginx -t
curl -fsS -o /dev/null -w 'login=%{http_code}\n' \
  https://pam.etgq.com/login
curl -sS -o /dev/null -w 'dashboard=%{http_code}\n' \
  https://pam.etgq.com/
curl -sS -o /dev/null -w 'projects=%{http_code}\n' \
  https://pam.etgq.com/projects
curl -sS -o /dev/null -w 'vouchers=%{http_code}\n' \
  https://pam.etgq.com/vouchers
```

Expected: login is `200`; protected routes return the configured login redirect
rather than `5xx`. With an authorized authenticated session, check the
dashboard, project list, one populated project ledger, category tree, pending
queue, and one project export. If such a session is unavailable, record those
authenticated checks as skipped. Do not alter administrator access to perform
the smoke test.

## 12. Rollback Triggers And Procedure

Roll back immediately if any protected count changes, any imported count or
financial total differs, `cam.service` is not active, the login page is not
HTTP `200`, or a key route returns `5xx`.

Use the exact `pam_release_stamp` from Step 2:

```bash
set -euo pipefail
pam_release_stamp='<release-stamp>'
pam_backup_dir="/root/cam-backups/${pam_release_stamp}"
test -s "$pam_backup_dir/construction.sqlite3"
test -s "$pam_backup_dir/cam-code.tar.gz"
test -s "$pam_backup_dir/uploads.tar.gz"

systemctl stop cam.service
cp "/root/cam-backups/${pam_release_stamp}/construction.sqlite3" /root/cam/instance/construction.sqlite3
tar -C /root -xzf "/root/cam-backups/${pam_release_stamp}/cam-code.tar.gz"
tar -C /root/cam -xzf "/root/cam-backups/${pam_release_stamp}/uploads.tar.gz"

if test -s "$pam_backup_dir/pam.etgq.com.conf"; then
  cp "$pam_backup_dir/pam.etgq.com.conf" \
    /www/server/panel/vhost/nginx/pam.etgq.com.conf
  nginx -t
  systemctl reload nginx
fi

systemctl start cam.service
systemctl is-active cam.service
curl -fsS -o /dev/null -w '%{http_code}\n' https://pam.etgq.com/login
```

After rollback, rerun the pre-deploy ledger and protected-count queries. The
project/voucher/contract state must match the Step 2 snapshot and all protected
data must remain available.

## Release Evidence

Leave this section blank until the production run. Populate it only with fresh
output from this runbook, then commit that evidence separately.

- Backup path:
- Deployed commit:
- Full test result and count:
- Copy-verifier JSON:
- Dry-run totals:
- Apply result:
- Pre-deploy protected SQL counts:
- Post-deploy protected SQL counts and diff:
- Post-deploy ledger SQL counts and totals:
- Service status:
- Nginx validation result:
- Live login status:
- Authenticated smoke checks skipped, if any:

After filling the fields, record the evidence locally:

```bash
cd /Users/rylinx/Documents/ylt-PAM
git add docs/runbooks/2026-07-26-project-ledger-production-import.md
git commit -m "docs: record project ledger release evidence"
```
