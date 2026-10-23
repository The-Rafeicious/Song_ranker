"""Whole-snapshot database sync. No row merge and no network or Flask imports."""

from contextlib import contextmanager
from pathlib import Path
import json
import os
import sqlite3
import tempfile
import uuid
from songranker.storage.database import initialize_database
from songranker.storage.database_io import (
    DatabaseValidationError,
    capture,
    create_backup,
    digest,
    publish,
    quote,
    readonly,
    replace_contents,
    snapshot,
    validate,
)

HISTORY_LIMIT = 32
MAX_SQL_BYTES = 64 * 1024 * 1024


def model(conn):
    """Compare stored facts by primary key; only install metadata is device-local.

    Hidden rowids matter for tables without explicit keys. Junction rowids do not
    turn a re-saved link into a different song/tag relationship.
    """
    state = capture(conn)
    facts = {}
    for name, data in state["tables"].items():
        if name in ("@schema", "@sequences", "@application"):
            raise DatabaseValidationError(
                "An extension uses a reserved sync comparison name; compare backups manually."
            )
        keys = sorted(
            (r[5], r[1])
            for r in conn.execute("PRAGMA table_info(" + quote(name) + ")")
            if r[5]
        )
        columns = data["columns"]
        values = {}
        rowids = data.get("rowids")
        for i, row in enumerate(data["rows"]):
            record = dict(zip(columns, row))
            key = (
                [record[column] for _, column in keys]
                if keys
                else [rowids[i] if rowids is not None else i]
            )
            if name == "competition_state":
                record.pop("started_at", None)
                record.pop("migration_report", None)
            identity = json.dumps(key, sort_keys=True)
            if identity in values:
                raise DatabaseValidationError(
                    "A table has ambiguous nullable primary keys; automatic database sync was skipped."
                )
            values[identity] = digest(record)
        facts[name] = values
    facts["@schema"] = {
        obj["type"] + ":" + obj["name"]: digest(obj["sql"]) for obj in state["objects"]
    }
    facts["@sequences"] = state["sequences"]
    facts["@application"] = {"id": state["application_id"]}
    return facts


def delta(base, changed):
    """Count added, removed and edited rows for each table between two indexed
    snapshots.
    """
    result = {}
    for table in base.keys() | changed.keys():
        before, after = base.get(table, {}), changed.get(table, {})
        added = len(after.keys() - before.keys())
        removed = len(before.keys() - after.keys())
        edited = sum(before[k] != after[k] for k in before.keys() & after.keys())
        if added or removed or edited:
            result[table] = dict(added=added, removed=removed, edited=edited)
    return result


def placeholder(sql):
    """Detect an empty or comments-only Git SQL snapshot."""
    return not any(
        line.strip() and not line.lstrip().startswith("--") for line in sql.splitlines()
    )


def prepare_sql(sql, folder, name, historical=False):
    """Materialise and validate bounded SQL in disposable storage, preserving full
    competition facts.
    """
    if len(sql.encode("utf-8")) > MAX_SQL_BYTES:
        raise DatabaseValidationError(
            "Git SQL snapshot exceeds the supported 64 MiB limit."
        )
    path = Path(folder) / (name + ".sql")
    path.write_text(sql, encoding="utf-8")
    database = Path(folder) / (name + ".db")
    initialize_database(database, path)
    with readonly(database) as conn:
        validate(conn)
        is_v3 = conn.execute(
            "SELECT 1 FROM competition_state WHERE id=1 AND generation=3"
        ).fetchone()
    if not is_v3:
        if not historical:
            raise DatabaseValidationError(
                "Git snapshot is not a V3 competition; it was not installed over local results."
            )
        # Only an ancestry witness may use the old catalogue-only V5 transfer.
        # The current remote candidate must always retain full V3 game facts.
        from songranker.storage.competition import start_competition

        transferred = Path(folder) / (name + "_v3.db")
        start_competition(transferred, database)
        database = transferred
    with readonly(database) as conn:
        return database, model(conn)


class DatabaseSync:
    def __init__(self, git, state):
        self.git, self.state = git, state
        self.binding = digest(
            dict(
                repo=str(git.repo),
                database=str(git.database),
                branch=state["branch"],
                remote=state["remote"],
                target=state["target"],
                destination=digest(
                    git.run("remote", "get-url", state["remote"]).stdout.strip()
                ),
            )
        )
        self.receipt_path = git.state_dir / ("database_" + self.binding + ".json")

    def blob(self, commit):
        """Resolve the tracked SQL snapshot's blob at a commit, returning no value
        when absent.
        """
        result = self.git.run(
            "rev-parse", "--verify", commit + ":" + self.git.sql_rel, check=False
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def sql(self, blob):
        """Read the SQL text stored in an already resolved Git blob."""
        return self.git.run("show", blob).stdout

    def device_key(self):
        """Persist a random installation identity bound to the configured live database."""
        path = self.git.state_dir / (
            "device_" + digest(str(self.git.database)) + ".json"
        )
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            key = value.get("key", "")
            if len(key) != 32 or any(c not in "0123456789abcdef" for c in key):
                raise DatabaseValidationError(
                    "Local device identity is invalid; review the saved database copies."
                )
            return key
        key = uuid.uuid4().hex
        self.git.state_dir.mkdir(exist_ok=True)
        # The operation lock serializes creation; atomic replacement survives interruption.
        with tempfile.NamedTemporaryFile(
            dir=self.git.state_dir, mode="w", delete=False
        ) as stream:
            name = stream.name
            json.dump(dict(key=key), stream)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(name, path)
        finally:
            Path(name).unlink(missing_ok=True)
        return key

    def remote_identity(self):
        """Read the latest snapshot commit's numbered-device registry and timestamp.

        The registry travels in the backup commit message, leaving the SQL header
        limited to the commit time and device number. Missing legacy identities
        never prove that a remote writer is this installation.
        """
        commit = self.state.get("tracking_head")
        if not commit:
            return dict(device=None, committed_at=None, snapshot_commit=None), {}
        text = self.git.run(
            "log", "-1", "--format=%H%x00%cI%x00%B", commit, "--", self.git.sql_rel
        ).stdout
        parts = text.split("\0", 2)
        if len(parts) != 3:
            return dict(device=None, committed_at=None, snapshot_commit=None), {}
        snapshot_commit, at, message = parts
        registry = {}
        writer = None
        for line in message.splitlines():
            if line.startswith("Song-Ranker-Devices: "):
                registry = json.loads(line.split(": ", 1)[1])
            if line.startswith("Song-Ranker-Device: "):
                writer = int(line.split(": ", 1)[1])
        if not registry:
            # Manual SQL commits may omit trailers; recover allocated numbers
            # without attributing that unidentified write to a known device.
            older = self.git.run(
                "log",
                "-1",
                "--format=%B",
                "--grep=^Song-Ranker-Devices: ",
                commit,
                "--",
                self.git.sql_rel,
            ).stdout
            for line in older.splitlines():
                if line.startswith("Song-Ranker-Devices: "):
                    registry = json.loads(line.split(": ", 1)[1])
        if (
            not isinstance(registry, dict)
            or len(registry) > 10000
            or any(
                not isinstance(k, str)
                or len(k) != 32
                or any(c not in "0123456789abcdef" for c in k)
                or type(v) is not int
                or v < 1
                for k, v in registry.items()
            )
            or len(set(registry.values())) != len(registry)
        ):
            raise DatabaseValidationError(
                "Remote device registry is invalid; review the incoming backup."
            )
        if writer is not None and writer not in registry.values():
            raise DatabaseValidationError(
                "Remote backup device is missing from its registry."
            )
        return (
            dict(
                device=writer,
                committed_at=at.replace("+00:00", "Z"),
                snapshot_commit=snapshot_commit,
            ),
            registry,
        )

    def remember(self, commit, blob, model_hash=None):
        """Persist the accepted remote hash and Git witness, bound to this database."""
        if model_hash is None:
            with tempfile.TemporaryDirectory(
                dir=self.git.database.parent, prefix=".git_database_"
            ) as folder:
                _, facts = prepare_sql(self.sql(blob), folder, "receipt")
                model_hash = digest(facts)
        self.git.state_dir.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=self.git.state_dir, mode="w", encoding="utf-8", delete=False
        ) as stream:
            name = stream.name
            json.dump(
                dict(
                    version=2,
                    commit=commit,
                    blob=blob,
                    binding=self.binding,
                    model_hash=model_hash,
                ),
                stream,
            )
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(name, self.receipt_path)
        finally:
            Path(name).unlink(missing_ok=True)

    def receipt(self):
        """Read old or hash-based receipts without accepting another database's baseline."""
        if not self.receipt_path.exists():
            return None
        value = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        if value.get("version") not in (1, 2) or value.get("binding") != self.binding:
            raise DatabaseValidationError(
                "Database sync receipt changed; compare the saved copies before continuing."
            )
        for key, length in [
            ("commit", 40),
            ("blob", 40),
            *([("model_hash", 64)] if value["version"] == 2 else []),
        ]:
            if (
                not isinstance(value.get(key), str)
                or len(value[key]) != length
                or any(c not in "0123456789abcdef" for c in value[key])
            ):
                raise DatabaseValidationError(
                    "Database sync receipt is invalid; local data was kept."
                )
        return value

    @contextmanager
    def review(self):
        """Compare logical hashes before every pull/push, independently of code ancestry."""
        remote_commit = self.state.get("tracking_head")
        blob = self.blob(remote_commit) if remote_commit else None
        if not blob or placeholder(self.sql(blob)):
            # Removing an existing remote backup is a change requiring review, not
            # permission to silently replace it with an unrelated database.
            if self.receipt():
                yield dict(
                    code="database_conflict",
                    message="The previously accepted remote backup is now missing or empty. Review Git history before uploading.",
                )
            else:
                yield dict(
                    code="no_remote_snapshot",
                    message="No committed remote database is available; the first backup can be uploaded.",
                )
            return
        sql = self.sql(blob)
        self.git.database.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=self.git.database.parent, prefix=".git_database_"
        ) as folder:
            candidate, remote = prepare_sql(sql, folder, "remote")
            with snapshot(self.git.database) as conn:
                validate(conn)
                local, live_hash = model(conn), digest(capture(conn))
            identity, registry = self.remote_identity()
            key = self.device_key()
            same_device = (
                identity["device"] is not None
                and registry.get(key) == identity["device"]
            )
            local_hash, remote_hash = digest(local), digest(remote)
            common = dict(
                blob=blob,
                commit=remote_commit,
                candidate=candidate,
                live_hash=live_hash,
                local_hash=local_hash,
                remote_hash=remote_hash,
                baseline_hash=None,
                local_device=registry.get(key),
                remote_device=identity["device"],
                remote_time=identity["committed_at"],
                snapshot_commit=identity["snapshot_commit"],
                same_device=same_device,
                local_songs=len(local.get("songs", {})),
                remote_songs=len(remote.get("songs", {})),
                different_rows=delta(remote, local),
            )
            if local_hash == remote_hash:
                yield dict(
                    common,
                    code="database_matches",
                    message="Local and remote database hashes match. No upload is needed.",
                )
                return
            receipt = self.receipt()
            if receipt is None:
                for event in self.git.history():
                    if (
                        not isinstance(event, dict)
                        or event.get("database_binding") != self.binding
                    ):
                        continue
                    commit = event.get("commit")
                    confirmed = event.get("action") in (
                        "upload",
                        "keep_local",
                        "use_remote",
                    ) or (
                        event.get("action") == "database"
                        and event.get("code")
                        in ("database_matches", "database_updated")
                    )
                    if (
                        event.get("ok")
                        and confirmed
                        and isinstance(commit, str)
                        and len(commit) == 40
                        and all(c in "0123456789abcdef" for c in commit)
                    ):
                        old_blob = self.blob(commit)
                        if old_blob:
                            receipt = dict(commit=commit, blob=old_blob)
                            break
            base = None
            if receipt:
                old_blob = self.blob(receipt["commit"])
                if old_blob and old_blob != receipt["blob"]:
                    raise DatabaseValidationError(
                        "Database sync baseline no longer matches its Git commit."
                    )
                if old_blob:
                    _, base = prepare_sql(self.sql(old_blob), folder, "baseline")
                common["baseline_hash"] = receipt.get("model_hash") or (
                    digest(base) if base is not None else None
                )
            else:
                # Compatibility recovery proves the exact local starting point;
                # finding history alone does not authorize adopting another writer.
                commits = self.git.run(
                    "log",
                    "--format=%H",
                    "-" + str(HISTORY_LIMIT),
                    remote_commit,
                    "--",
                    self.git.sql_rel,
                ).stdout.splitlines()
                seen = {blob}
                for i, commit in enumerate(commits):
                    old_blob = self.blob(commit)
                    if not old_blob or old_blob in seen:
                        continue
                    seen.add(old_blob)
                    old_sql = self.sql(old_blob)
                    if placeholder(old_sql):
                        continue
                    try:
                        _, old = prepare_sql(
                            old_sql, folder, "history_" + str(i), historical=True
                        )
                    except (ValueError, sqlite3.Error):
                        continue
                    if old == local:
                        base = old
                        common["baseline_hash"] = digest(old)
                        break
            if base is not None:
                common.update(
                    local_changes=delta(base, local), remote_changes=delta(base, remote)
                )
            if common["baseline_hash"] == remote_hash:
                yield dict(
                    common,
                    reason="remote_unchanged",
                    code="database_local_ahead",
                    message="Remote hash still matches the accepted baseline. Local changes can upload without intervention.",
                )
            elif same_device:
                yield dict(
                    common,
                    reason="same_device",
                    code="database_local_ahead",
                    message="The last remote backup came from this device. Trusting the current local database, including local edits and deletions.",
                )
            else:
                writer = (
                    "Device " + str(identity["device"])
                    if identity["device"] is not None
                    else "An unidentified device"
                )
                yield dict(
                    common,
                    reason=(
                        "different_device"
                        if identity["device"] is not None
                        else "unknown_device"
                    ),
                    code="database_conflict",
                    message=writer
                    + " changed the remote database since the accepted baseline. Compare both copies and choose which to keep; neither live database is replaced automatically.",
                )

    def incoming_backup(self, review):
        """Preserve the incoming candidate as a verified backup without replacing
        different saved data.
        """
        directory = self.git.database.parent / "database_backups"
        directory.mkdir(exist_ok=True)
        destination = directory / ("incoming_git_" + review["blob"] + ".db")
        if destination.exists():
            with readonly(destination) as saved, readonly(
                review["candidate"]
            ) as source:
                if digest(capture(saved)) != digest(capture(source)):
                    raise DatabaseValidationError(
                        "The incoming backup filename already contains different data; it was not replaced."
                    )
        else:
            publish(review["candidate"], destination)
        return destination.name

    def adopt(self, review):
        """Archive, check again under a write lock, replace and validate atomically."""
        from songranker.storage.database_access import gate

        with gate.maintenance():
            backup = create_backup(self.git.database, "pre_git_database")
            with readonly(review["candidate"]) as candidate:
                replacement = capture(candidate)
            conn = sqlite3.connect(self.git.database, timeout=30)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA foreign_keys=OFF")
                conn.execute("BEGIN IMMEDIATE")
                if digest(capture(conn)) != review["live_hash"]:
                    raise DatabaseValidationError(
                        "Local data changed during the Git database check; nothing was replaced. Restart to retry."
                    )
                if self.git.inspect()["tracking_head"] != review["commit"]:
                    raise DatabaseValidationError(
                        "Git changed during the database check; restart to retry."
                    )
                replace_contents(conn, replacement)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()
        return backup.name

    @staticmethod
    def public(review):
        """Remove temporary paths and private comparison witnesses from a
        reconciliation review.
        """
        return {
            key: value
            for key, value in review.items()
            if key not in ("candidate", "live_hash", "blob")
        }
