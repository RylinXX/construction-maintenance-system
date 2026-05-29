from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from flask import current_app
from flask import g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database = Path(current_app.config["DATABASE"])
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys = on")
        g.db = connection
    return g.db


def close_db(_: Any = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        create table if not exists companies (
            id integer primary key autoincrement,
            name text not null unique,
            credit_code text not null default '',
            legal_person text not null default '',
            phone text not null default '',
            notes text not null default '',
            is_main integer not null default 0,
            created_at text not null default current_timestamp
        );

        create table if not exists projects (
            id integer primary key autoincrement,
            company_id integer not null references companies(id),
            name text not null,
            status text not null default '进行中',
            owner text not null default '',
            start_date text not null default '',
            end_date text not null default '',
            notes text not null default '',
            created_at text not null default current_timestamp
        );

        create table if not exists vouchers (
            id integer primary key autoincrement,
            project_id integer not null references projects(id),
            voucher_date text not null,
            voucher_type text not null,
            amount real not null check(amount > 0),
            notes text not null default '',
            attachment_path text not null default '',
            entry_user text not null default '',
            created_at text not null default current_timestamp
        );

        create table if not exists people (
            id integer primary key autoincrement,
            name text not null,
            id_number text not null unique,
            gender text not null default '',
            birth_date text not null default '',
            age integer,
            phone text not null default '',
            address text not null default '',
            job_type text not null default '',
            bank_card text not null default '',
            bank_name text not null default '',
            entry_date text not null default '',
            notes text not null default '',
            review_status text not null default '已确认',
            created_at text not null default current_timestamp
        );

        create table if not exists qualifications (
            id integer primary key autoincrement,
            company_id integer not null references companies(id),
            name text not null,
            certificate_no text not null,
            issue_date text not null default '',
            expiry_date text not null default '',
            is_long_term integer not null default 0,
            attachment_path text not null default '',
            notes text not null default '',
            created_at text not null default current_timestamp
        );

        create table if not exists batch_items (
            id integer primary key autoincrement,
            item_type text not null,
            source_filename text not null,
            stored_path text not null default '',
            status text not null default '待确认',
            recognized_json text not null default '{}',
            confidence real,
            created_at text not null default current_timestamp
        );
        """
    )
    db.execute(
        """
        insert into companies (name, is_main)
        select '主公司', 1
        where not exists (select 1 from companies where is_main = 1)
        """
    )
    db.commit()
