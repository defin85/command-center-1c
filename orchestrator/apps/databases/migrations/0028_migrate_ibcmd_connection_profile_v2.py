from __future__ import annotations

from django.db import migrations


_FORBIDDEN_OFFLINE_KEYS = {"db_user", "db_pwd", "db_password"}


def _normalize_ibcmd_connection_profile_v2(raw):
    if not isinstance(raw, dict):
        return None

    remote_raw = raw.get("remote")
    if remote_raw in (None, ""):
        remote_raw = raw.get("remote_url")
    remote = str(remote_raw).strip() if remote_raw not in (None, "") else ""
    if remote and not remote.lower().startswith("ssh://"):
        remote = ""

    pid_raw = raw.get("pid")
    pid = pid_raw if isinstance(pid_raw, int) and pid_raw > 0 else None

    offline_in = raw.get("offline")
    offline = None
    if isinstance(offline_in, dict):
        offline_safe = {}
        for k, v in offline_in.items():
            key = str(k).strip()
            if not key:
                continue
            if key.lower() in _FORBIDDEN_OFFLINE_KEYS:
                continue
            if v in (None, ""):
                continue
            rendered = str(v).strip()
            if not rendered:
                continue
            offline_safe[key] = rendered
        offline = offline_safe or None

    out = {}
    if remote:
        out["remote"] = remote
    if pid is not None:
        out["pid"] = pid
    if offline:
        out["offline"] = offline
    return out


def forwards(apps, schema_editor):
    Database = apps.get_model("databases", "Database")
    qs = Database.objects.all().only("id", "metadata")
    for db in qs.iterator(chunk_size=2000):
        meta = getattr(db, "metadata", None)
        if not isinstance(meta, dict):
            continue
        if "ibcmd_connection" not in meta:
            continue

        raw = meta.get("ibcmd_connection")
        normalized = _normalize_ibcmd_connection_profile_v2(raw)
        if normalized is None:
            # Drop invalid non-dict values.
            next_meta = dict(meta)
            next_meta.pop("ibcmd_connection", None)
        else:
            next_meta = dict(meta)
            next_meta["ibcmd_connection"] = normalized

        if next_meta == meta:
            continue
        db.metadata = next_meta
        db.save(update_fields=["metadata"])


class Migration(migrations.Migration):
    dependencies = [
        ("databases", "0027_alter_cluster_tenant_alter_database_tenant"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]

