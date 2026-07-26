from __future__ import annotations

from pathlib import Path

import click

from .services.ledger_import import apply_ledger_import, parse_ledger_source


def init_app(app) -> None:
    @app.cli.command("ledger-import")
    @click.argument("source", type=click.Path(exists=True, path_type=Path))
    @click.option("--apply", "apply_changes", is_flag=True, default=False)
    @click.option("--replace-demo-projects", is_flag=True, default=False)
    def ledger_import(source: Path, apply_changes: bool, replace_demo_projects: bool):
        preview = parse_ledger_source(source)
        click.echo("APPLY" if apply_changes else "DRY RUN")
        click.echo(f"projects={preview.project_count}")
        click.echo(f"entries={len(preview.entries)}")
        click.echo(f"pending_items={len(preview.pending_items)}")
        for key, value in preview.totals.items():
            click.echo(f"{key}={value:.2f}")
        if apply_changes:
            result = apply_ledger_import(
                preview,
                replace_demo_projects=replace_demo_projects,
                actor_admin_id=None,
            )
            click.echo(f"inserted_entries={result['entries']}")
            click.echo(f"inserted_pending_items={result['pending_items']}")
