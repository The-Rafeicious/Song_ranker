"""Database-only Git uploads and guarded, startup-only fast-forward updates.

No Flask imports: startup can update before loading any application modules.
All process calls use argument lists; remote errors never expose credential URLs.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
import gzip
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile


class SyncError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def stamp():
    """Return a UTC timestamp at whole-second precision for local Git operation
    history.
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(value):
    """Hash deterministic JSON to bind Git reviews to their observed repository
    state.
    """
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def display_remote(value):
    """Show the destination, excluding URL credentials, query strings and fragments."""
    try:
        if "://" in value:
            parsed = urlsplit(value)
            return (
                (parsed.hostname or "Local remote")
                + "/"
                + ("/".join(parsed.path.strip("/").split("/")[-2:]))
            )
        if "@" in value and ":" in value:
            return value.split("@", 1)[1].split("?", 1)[0].split("#", 1)[0]
        return "Local remote / " + Path(value).name
    except ValueError:
        return "Configured remote"


class GitSync:
    def __init__(self, root, database):
        self.root = Path(root).resolve()
        self.database = Path(database).resolve()
        self.repo = None
        self.gitdir = None
        self.prefix = ""
        self.sql = self.root / "database_backup.sql"

    def run(self, *args, check=True, network=False, extra_env=None, maintenance=False):
        """Run noninteractive Git with bounded timeouts and translate execution or
        authentication failures.
        """
        env = os.environ.copy()
        env.update(
            GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never", GIT_OPTIONAL_LOCKS="0"
        )
        env.update(extra_env or {})
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo or self.root,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120 if maintenance else 25 if network else 12,
            )
        except FileNotFoundError as error:
            raise SyncError(
                "git_missing", "Git is not installed or is unavailable to this app."
            ) from error
        except subprocess.TimeoutExpired as error:
            raise SyncError(
                "timeout",
                "Git did not finish in time. Check the target and retry; local data is kept.",
            ) from error
        except OSError as error:
            raise SyncError(
                "git_unavailable",
                "Git could not run. Check the local repository and permissions.",
            ) from error
        if check and result.returncode:
            text = (result.stderr + " " + result.stdout).lower()
            if any(
                s in text
                for s in (
                    "authentication failed",
                    "permission denied",
                    "could not read username",
                    "could not read password",
                )
            ):
                raise SyncError(
                    "authentication_failed",
                    "Git could not authenticate. Check access in your terminal; no credentials are entered here.",
                )
            raise SyncError(
                "remote_unavailable" if network else "git_failed",
                (
                    "Could not contact the configured remote. Check network/access and retry."
                    if network
                    else "Git could not complete this operation. Review repository state in your terminal."
                ),
            )
        return result

    def discover(self):
        """Locate the repository, application-relative SQL snapshot and private Git
        state directory.
        """
        result = self.run("rev-parse", "--show-toplevel", check=False)
        if result.returncode:
            raise SyncError(
                "not_repo",
                "This app folder is not in a Git repository. Local backups and downloads still work.",
            )
        self.repo = Path(result.stdout.strip()).resolve()
        try:
            relative = self.root.relative_to(self.repo).as_posix()
            self.prefix = "" if relative == "." else relative
        except ValueError:
            raise SyncError(
                "outside_repo", "The app folder is outside the reported repository."
            )
        self.sql_rel = (
            self.prefix + "/" if self.prefix else ""
        ) + "database_backup.sql"
        raw = self.run("rev-parse", "--absolute-git-dir").stdout.strip()
        self.gitdir = Path(raw)
        return self

    @property
    def state_dir(self):
        """Resolve the installation's private sync-state directory inside its Git
        metadata.
        """
        return self.gitdir / "song_ranker_sync"

    @contextmanager
    def lock(self):
        """Hold a nonblocking cross-process lock for one Git/database sync operation."""
        self.state_dir.mkdir(exist_ok=True)
        path = self.state_dir / "operation.lock"
        f = path.open("a+b")
        if path.stat().st_size == 0:
            f.write(b"0")
            f.flush()
        f.seek(0)
        try:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise SyncError(
                    "busy",
                    "Another Git task is running. Wait for it to finish before trying again.",
                ) from error
            yield
        finally:
            f.close()  # OS locks are released even if a process exits unexpectedly.

    def history(self):
        """Read up to ten recent local Git operation results, tolerating absent or
        invalid history.
        """
        try:
            return json.loads((self.state_dir / "history.json").read_text())[:10]
        except (OSError, ValueError, TypeError):
            return []

    def record(self, result):
        """Atomically prepend a timestamped operation result to the bounded local Git
        history.
        """
        result = dict(result, at=stamp())
        events = [result, *self.history()][:10]
        self.state_dir.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=self.state_dir, mode="w", encoding="utf-8", delete=False
        ) as f:
            json.dump(events, f, ensure_ascii=True, indent=2)
            f.flush()
            os.fsync(f.fileno())
            temp = f.name
        os.replace(temp, self.state_dir / "history.json")
        return result

    def protected(self, path):
        """Identify live data, backups, secrets and generated files excluded from
        code-change handling.
        """
        p = PurePosixPath(path)
        parts = {s.casefold() for s in p.parts}
        name = p.name.casefold()
        try:
            db_rel = self.database.relative_to(self.repo).as_posix().casefold()
        except ValueError:
            db_rel = None
        return (
            path.casefold()
            in {
                db_rel,
                (db_rel or "") + "-wal",
                (db_rel or "") + "-shm",
                (db_rel or "") + "-journal",
            }
            or name.endswith(
                (".db", ".sqlite", ".sqlite3", ".pyc", "-wal", "-shm", "-journal")
            )
            or bool(
                parts
                & {
                    "instance",
                    "database_backups",
                    "__pycache__",
                    ".venv",
                    "venv",
                    "node_modules",
                    ".pytest_cache",
                }
            )
            or name in {"database_snapshot.txt", "current_elo_rankings.txt", ".env"}
            or any(
                s.startswith((".restore_", ".export_", ".git_database_"))
                for s in p.parts
            )
        )

    def changes(self):
        """Read staged and unstaged Git changes, retaining rename origins and
        protected-file flags.
        """
        fields = self.run(
            "status", "--porcelain=v1", "-z", "--untracked-files=all"
        ).stdout.split("\0")
        result = []
        i = 0
        while i < len(fields):
            item = fields[i]
            i += 1
            if not item:
                continue
            code = item[:2]
            path = item[3:]
            old = None
            if "R" in code or "C" in code:
                if i < len(fields):
                    old = fields[i]
                    i += 1
            result.append(
                dict(
                    path=path,
                    old_path=old,
                    status=code,
                    staged=code[0] not in (" ", "?"),
                    protected=self.protected(path),
                )
            )
        return result

    def inspect(self):
        """Inspect branch, upstream, code changes and database status and produce a
        review fingerprint.
        """
        if self.repo is None:
            self.discover()
        branch = self.run(
            "symbolic-ref", "--quiet", "--short", "HEAD", check=False
        ).stdout.strip()
        head = self.run("rev-parse", "--verify", "HEAD", check=False).stdout.strip()
        if not head:
            raise SyncError(
                "unborn",
                "The repository has no initial commit. Finish Git setup in your terminal first.",
            )
        if not branch:
            raise SyncError(
                "detached",
                "Git is on a detached commit. Choose the intended branch in your terminal first.",
            )
        remote = (
            self.run(
                "config", "--get", f"branch.{branch}.remote", check=False
            ).stdout.strip()
            or "origin"
        )
        merge = (
            self.run(
                "config", "--get", f"branch.{branch}.merge", check=False
            ).stdout.strip()
            or "refs/heads/" + branch
        )
        if remote not in self.run("remote").stdout.splitlines() or not merge.startswith(
            "refs/heads/"
        ):
            raise SyncError(
                "no_remote",
                "No usable named remote/upstream is configured for this branch. Finish Git setup first.",
            )
        if remote.startswith("-") or any(c.isspace() for c in remote):
            raise SyncError("invalid_target", "The configured remote name is invalid.")
        target = merge[len("refs/heads/") :]
        tracking = f"refs/remotes/{remote}/{target}"
        if self.run("check-ref-format", tracking, check=False).returncode:
            raise SyncError(
                "invalid_target", "The configured target branch is invalid."
            )
        url = self.run("remote", "get-url", remote).stdout.strip()
        push_url = self.run("remote", "get-url", "--push", remote).stdout.strip()
        # Multiple destinations make a single target/receipt ambiguous.
        push_urls = self.run(
            "remote", "get-url", "--push", "--all", remote
        ).stdout.splitlines()
        if len(push_urls) != 1:
            raise SyncError(
                "multiple_targets",
                "This remote has multiple push destinations. Use a single destination for app backup uploads.",
            )
        if push_url != url:
            raise SyncError(
                "different_targets",
                "Fetch and push use different destinations. Configure one destination or sync this setup through Git manually.",
            )
        remote_head = (
            self.run("rev-parse", "--verify", tracking, check=False).stdout.strip()
            or None
        )
        ahead = behind = None
        pending_files = []
        commits = []
        if remote_head:
            counts = self.run(
                "rev-list", "--left-right", "--count", head + "..." + remote_head
            ).stdout.split()
            ahead, behind = map(int, counts)
            if ahead:
                pending_files = sorted(
                    set(
                        filter(
                            None,
                            self.run(
                                "log",
                                "--format=",
                                "--name-only",
                                "-z",
                                remote_head + ".." + head,
                            )
                            .stdout.replace("\n", "\0")
                            .split("\0"),
                        )
                    )
                )
                commits = [
                    dict(
                        hash=line.split(" ", 1)[0],
                        subject=line.split(" ", 1)[1] if " " in line else "",
                    )
                    for line in self.run(
                        "log", "--format=%h %s", "-10", remote_head + ".." + head
                    ).stdout.splitlines()
                ]
        conflicts = bool(self.run("ls-files", "-u", "-z").stdout)
        in_progress = conflicts or any(
            (self.gitdir / name).exists()
            for name in (
                "MERGE_HEAD",
                "CHERRY_PICK_HEAD",
                "REVERT_HEAD",
                "rebase-merge",
                "rebase-apply",
            )
        )
        changes = self.changes()
        code_changes = [
            r for r in changes if not r["protected"] and r["path"] != self.sql_rel
        ]
        state = (
            "operation_in_progress"
            if in_progress
            else (
                "not_checked"
                if remote_head is None
                else (
                    "diverged"
                    if ahead and behind
                    else "behind" if behind else "ahead" if ahead else "up_to_date"
                )
            )
        )
        fingerprint = digest(
            dict(
                repo=str(self.repo),
                prefix=self.prefix,
                branch=branch,
                head=head,
                remote=remote,
                target=target,
                url=url,
                push_url=push_url,
            )
        )
        return dict(
            available=True,
            state=state,
            branch=branch,
            head=head,
            remote=remote,
            target=target,
            destination=display_remote(push_url),
            tracking_head=remote_head,
            ahead=ahead,
            behind=behind,
            pending_files=pending_files,
            commits=commits,
            pending_code=any(p != self.sql_rel for p in pending_files),
            changes=changes,
            code_changes=len(code_changes),
            staged_changes=sum(r["staged"] for r in changes),
            in_progress=in_progress,
            fingerprint=fingerprint,
            history=self.history(),
            storage=self.storage(),
            database_sync=self.database_status(),
            snapshot=dict(
                name="database_backup.sql",
                exists=self.sql.is_file(),
                bytes=self.sql.stat().st_size if self.sql.is_file() else 0,
            ),
        )

    def database_status(self):
        """Read the latest saved database reconciliation result without contacting
        the remote.
        """
        try:
            value = json.loads(
                (self.state_dir / "database_status.json").read_text(encoding="utf-8")
            )
            return value if isinstance(value, dict) else None
        except (OSError, ValueError):
            return None

    def database_report(self, result):
        """Atomically persist a timestamped database reconciliation result."""
        self.state_dir.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=self.state_dir, mode="w", encoding="utf-8", delete=False
        ) as stream:
            path = stream.name
            json.dump(dict(result, at=stamp()), stream)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(path, self.state_dir / "database_status.json")
        finally:
            Path(path).unlink(missing_ok=True)
        return result

    def review_database(self, state):
        """Compare hashes/devices without replacing live data; preserve review copies."""
        from songranker.storage.git_database import DatabaseSync

        policy = DatabaseSync(self, state)
        with policy.review() as reviewed:
            result = dict(policy.public(reviewed), database_binding=policy.binding)
            if result["code"] == "database_matches":
                policy.remember(
                    reviewed["commit"], reviewed["blob"], reviewed.get("remote_hash")
                )
            elif result["code"] == "database_conflict":
                if "candidate" in reviewed:
                    result["incoming_backup"] = policy.incoming_backup(reviewed)
                if result.get("incoming_backup"):
                    result["message"] += (
                        " Review "
                        + result["incoming_backup"]
                        + " in Dev → Backups & restore, or compare the copies on Git sync."
                    )
            return self.database_report(result)

    def reconcile_database(self):
        """Normal-launcher only, after code re-exec and schema bootstrap, before serving."""
        if not self.database.is_file():
            return dict(
                ok=True,
                action="database",
                code="database_missing",
                message="Database bootstrap has not created a live database yet.",
            )
        try:
            self.discover()
            with self.lock():
                state = self.inspect()
                if state["in_progress"]:
                    raise SyncError(
                        "operation_in_progress",
                        "Database sync skipped: finish the current Git operation first.",
                    )
                self.fetch(state)
                state = self.inspect()
                result = self.review_database(state)
                result = dict(
                    result, ok=result["code"] != "database_conflict", action="database"
                )
                try:
                    return self.record(result)
                except OSError:
                    result["message"] += " Git outcome history could not be saved."
                    return result
        except (SyncError, OSError, sqlite3.Error, ValueError) as error:
            if not isinstance(error, SyncError):
                error = SyncError(
                    "database_check_failed",
                    "Git database could not be validated or safely compared. Local data was kept; upload will recheck before publishing.",
                )
            result = self.failure("database", error)
            if self.gitdir:
                try:
                    self.database_report(result)
                except OSError:
                    pass
            return result

    def status(self):
        """Return cached repository inspection or a structured unavailable reason for
        the Dev panel.
        """
        try:
            state = self.inspect()
            state["status_source"] = "cached"
            return state
        except SyncError as error:
            return dict(
                available=False,
                state=error.code,
                message=str(error),
                history=self.history() if self.gitdir else [],
            )

    def fetch(self, state):
        """Refresh only the configured upstream branch without changing the working
        tree.
        """
        self.run(
            "-c",
            "gc.auto=0",
            "fetch",
            "--no-tags",
            "--no-recurse-submodules",
            "--no-write-fetch-head",
            state["remote"],
            "+refs/heads/"
            + state["target"]
            + ":refs/remotes/"
            + state["remote"]
            + "/"
            + state["target"],
            network=True,
        )

    def check(self):
        try:
            self.discover()
            with self.lock():
                before = self.inspect()
                self.migrate_archives()
                self.fetch(before)
                after = self.inspect()
                comparison = (
                    self.review_database(after)
                    if self.database.is_file()
                    else dict(
                        code="database_missing", message="Live database is missing."
                    )
                )
                self.record(
                    dict(
                        ok=True,
                        action="check",
                        code=comparison["code"],
                        message="Code: "
                        + after["state"]
                        + ". "
                        + comparison["message"],
                    )
                )
                current = self.inspect()
                current.update(
                    status_source="checked",
                    checked_at=stamp(),
                    database_sync=comparison,
                )
                blocked = after["in_progress"] or comparison["code"] not in (
                    "database_matches",
                    "database_local_ahead",
                    "no_remote_snapshot",
                )
                current["upload_ready"] = not bool(blocked)
                return dict(
                    ok=True,
                    code=after["state"],
                    message=("Check complete. " + comparison["message"]),
                    git=current,
                )
        except SyncError as error:
            return self.failure("check", error)
        except (OSError, sqlite3.Error, ValueError):
            return self.failure(
                "check",
                SyncError(
                    "database_check_failed",
                    "The remote database snapshot could not be validated. Local data was kept.",
                ),
            )

    def failure(self, action, error, **extra):
        """Build a structured Git failure and record it locally when history storage
        is available.
        """
        result = dict(
            ok=False, action=action, code=error.code, message=str(error), **extra
        )
        if self.gitdir:
            try:
                self.record(result)
            except OSError:
                pass
        return result

    @property
    def archive_dir(self):
        """Store compressed SQL safety copies beside backups, outside Git metadata."""
        return self.database.parent / "database_backups" / "git_snapshots"

    def compress_archive(self, source, label):
        """Verify a durable compressed safety copy before allowing source removal."""
        source = Path(source)
        if source.is_symlink():
            raise SyncError(
                "linked_snapshot", "Linked SQL archives are not moved or replaced."
            )
        content = source.read_bytes()
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        destination = self.archive_dir / (
            label + "_" + hashlib.sha256(content).hexdigest() + ".sql.gz"
        )
        if destination.is_symlink():
            raise SyncError("linked_snapshot", "Linked SQL archives are not replaced.")
        if destination.exists():
            if gzip.decompress(destination.read_bytes()) != content:
                raise SyncError(
                    "archive_mismatch",
                    "A safety archive contains different data. Original files were kept.",
                )
            return destination
        with tempfile.NamedTemporaryFile(dir=self.archive_dir, delete=False) as stream:
            name = stream.name
            stream.write(gzip.compress(content, compresslevel=6, mtime=0))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            if gzip.decompress(Path(name).read_bytes()) != content:
                raise SyncError(
                    "archive_mismatch",
                    "Safety archive verification failed; original files were kept.",
                )
            os.replace(name, destination)
        finally:
            Path(name).unlink(missing_ok=True)
        return destination

    def migrate_archives(self):
        """Move old plain SQL safety copies out of .git without expiring any backup."""
        moved = 0
        for source in self.state_dir.glob("before_*.sql"):
            if source.is_file() and not source.is_symlink():
                self.compress_archive(source, source.stem)
                source.unlink()
                moved += 1
        return moved

    def storage(self):
        """Report packed/loose object sizes without traversing large repositories."""
        values = {}
        for line in self.run("count-objects", "-v").stdout.splitlines():
            key, _, value = line.partition(": ")
            if value.isdigit():
                values[key] = int(value)
        return dict(
            object_bytes=1024 * (values.get("size", 0) + values.get("size-pack", 0)),
            loose_objects=values.get("count", 0),
            packs=values.get("packs", 0),
        )

    def compact(self, expected=None):
        """Repack Git without pruning objects, reflogs, worktrees or backup history."""
        try:
            self.discover()
            with self.lock():
                state = self.inspect()
                if expected and expected != state["fingerprint"]:
                    raise SyncError(
                        "stale_target", "Git changed. Refresh before compacting."
                    )
                if state["in_progress"]:
                    raise SyncError(
                        "operation_in_progress",
                        "Finish the active Git operation before compacting.",
                    )
                before = self.storage()
                moved = self.migrate_archives()
                self.run("repack", "-a", "-d", "--keep-unreachable", maintenance=True)
                result = self.record(
                    dict(
                        ok=True,
                        action="compact",
                        code="compacted",
                        before=before,
                        after=self.storage(),
                        archives_moved=moved,
                        message="Git storage compacted. History and recovery objects were retained; "
                        + str(moved)
                        + " SQL safety copies moved to compressed backup storage.",
                    )
                )
                return dict(result, git=self.inspect())
        except (SyncError, OSError, ValueError) as error:
            if not isinstance(error, SyncError):
                error = SyncError(
                    "compact_failed",
                    "Storage compaction did not finish; local data and history were kept.",
                )
            return self.failure("compact", error)

    def archive_sql(self, label):
        """Preserve a changed SQL file in verified compressed storage outside .git."""
        if not self.sql.exists():
            return None
        self.migrate_archives()
        return self.compress_archive(self.sql, label)

    def write_snapshot(self, device=None, committed_at=None, expected_hash=None):
        """Export one validated read snapshot, binding it to the reviewed logical hash."""
        if not self.database.is_file():
            raise SyncError(
                "database_missing",
                "The live database does not exist. Start/restore the app before uploading a backup.",
            )
        if self.sql.is_symlink():
            raise SyncError(
                "linked_snapshot",
                "The SQL snapshot is a symbolic link. Use a normal file before syncing.",
            )
        from songranker.storage.database_io import snapshot, validate, sql_dump
        from songranker.storage.git_database import model

        with snapshot(self.database) as db:
            validate(db)
            actual = digest(model(db))
            if expected_hash and actual != expected_hash:
                raise SyncError(
                    "stale_database",
                    "Local data changed after comparison. Retry to compare the latest snapshot.",
                )
            content = sql_dump(db)
            if device is not None:
                content = (
                    "-- Song Ranker backup · commit time: "
                    + committed_at
                    + " · device: "
                    + str(device)
                    + "\n"
                    + content
                )
            with tempfile.NamedTemporaryFile(
                dir=self.root,
                mode="w",
                encoding="utf-8",
                newline="\n",
                delete=False,
                prefix=".git_snapshot_",
            ) as stream:
                name = stream.name
                try:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                except BaseException:
                    Path(name).unlink(missing_ok=True)
                    raise
        try:
            if (
                not self.sql.is_file()
                or Path(name).read_bytes() != self.sql.read_bytes()
            ):
                self.archive_sql("before_upload")
                os.replace(name, self.sql)
        finally:
            Path(name).unlink(missing_ok=True)
        return actual

    def local_choice_review(self, expected=None):
        """Review both snapshots without adopting either, even before a source update."""
        try:
            self.discover()
            with self.lock():
                state = self.inspect()
                if expected and state["fingerprint"] != expected:
                    raise SyncError(
                        "stale_target",
                        "Git changed. Check remote and review the database choice again.",
                    )
                if state["in_progress"]:
                    raise SyncError(
                        "operation_in_progress",
                        "Finish the current Git operation before choosing a database.",
                    )
                self.fetch(state)
                state = self.inspect()
                from songranker.storage.git_database import DatabaseSync

                policy = DatabaseSync(self, state)
                with policy.review() as review:
                    if "candidate" not in review:
                        raise SyncError(
                            "database_check_failed",
                            "There is no validated remote database to review. Use the normal upload when no remote snapshot exists.",
                        )
                    from songranker.storage.database_io import (
                        snapshot,
                        readonly,
                        capture,
                        digest as data_digest,
                    )

                    def counts(conn):
                        """Count catalogue, result and placed-Vibe rows for the
                        local-versus-remote choice review.
                        """
                        result = {
                            label: conn.execute(
                                "SELECT COUNT(*) FROM " + table
                            ).fetchone()[0]
                            for label, table in [
                                ("Songs", "songs"),
                                ("Albums", "albums"),
                                ("Artists", "artists"),
                                ("Tags", "genres"),
                                ("Votes", "history"),
                                ("Voting events", "preference_events"),
                                ("Vibe song records", "song_vibe_progress"),
                                ("Trivia rounds", "trivia_rounds"),
                                ("Tournaments", "tournaments"),
                                ("Elo guesses", "elo_guess_rounds"),
                                ("Shelves rounds", "album_shelf_rounds"),
                            ]
                        }
                        result["Vibe positions"] = conn.execute(
                            "SELECT COUNT(*) FROM song_vibe_positions WHERE status='placed'"
                        ).fetchone()[0]
                        return result

                    with snapshot(self.database) as live:
                        if data_digest(capture(live)) != review["live_hash"]:
                            raise SyncError(
                                "stale_database",
                                "Local data changed. Review the database choice again.",
                            )
                        local = counts(live)
                    with readonly(review["candidate"]) as remote:
                        incoming = counts(remote)
                    choice = {
                        key: review[key] for key in ("commit", "blob", "live_hash")
                    }
                    choice.update(
                        fingerprint=state["fingerprint"], binding=policy.binding
                    )
                    return dict(
                        ok=True,
                        action="keep_local_review",
                        code="reviewed",
                        message="Compare both copies before keeping local. Neither database has been replaced.",
                        local=local,
                        remote=incoming,
                        comparison=review["code"],
                        details=policy.public(review),
                        choice=choice,
                        git=state,
                    )
        except (SyncError, OSError, sqlite3.Error, ValueError) as error:
            if not isinstance(error, SyncError):
                error = SyncError(
                    "database_check_failed",
                    "Could not validate both databases. Nothing was replaced.",
                )
            return self.failure("keep_local_review", error)

    def keep_local(self, choice):
        """Acknowledge the exact remote as baseline; keep local bytes and normal Git guards."""
        accepted = False
        result = None
        try:
            self.discover()
            with self.lock():
                state = self.inspect()
                if state["fingerprint"] != choice.get("fingerprint"):
                    raise SyncError(
                        "stale_target",
                        "Git changed after review. Review the database choice again.",
                    )
                if state["in_progress"]:
                    raise SyncError(
                        "operation_in_progress",
                        "Finish the current Git operation before choosing a database.",
                    )
                self.fetch(state)
                state = self.inspect()
                if state["fingerprint"] != choice.get("fingerprint"):
                    raise SyncError(
                        "stale_target",
                        "Git changed during review. Review the database choice again.",
                    )
                from songranker.storage.git_database import DatabaseSync
                from songranker.storage.database_access import gate
                from songranker.storage.database_io import (
                    create_backup,
                    readonly,
                    capture,
                    digest as data_digest,
                )

                policy = DatabaseSync(self, state)
                if policy.binding != choice.get("binding"):
                    raise SyncError(
                        "stale_target",
                        "The database or Git destination changed. Review again.",
                    )
                with policy.review() as review:
                    if any(
                        review.get(k) != choice.get(k)
                        for k in ("commit", "blob", "live_hash")
                    ):
                        raise SyncError(
                            "stale_database",
                            "Local or remote data changed after review. Neither copy was replaced; review again.",
                        )
                    with gate.maintenance():
                        incoming = policy.incoming_backup(review)
                        backup = create_backup(self.database, "pre_git_keep_local")
                        with readonly(backup) as saved:
                            if data_digest(capture(saved)) != choice["live_hash"]:
                                raise SyncError(
                                    "stale_database",
                                    "Local data changed while backing up. Review again.",
                                )
                        conn = sqlite3.connect(self.database, timeout=30)
                        conn.row_factory = sqlite3.Row
                        try:
                            conn.execute("BEGIN IMMEDIATE")
                            if (
                                data_digest(capture(conn)) != choice["live_hash"]
                                or self.inspect()["fingerprint"] != state["fingerprint"]
                            ):
                                raise SyncError(
                                    "stale_database",
                                    "Data or Git changed while preparing the choice. Review again.",
                                )
                            policy.remember(
                                review["commit"], review["blob"], review["remote_hash"]
                            )
                            accepted = True
                        finally:
                            conn.rollback()
                            conn.close()
                    message = "Local database kept. Both copies are backed up. Upload backup can now publish this local copy independently of code ahead/behind status."
                    result = dict(
                        ok=True,
                        action="keep_local",
                        code="database_local_kept",
                        message=message,
                        commit=review["commit"],
                        database_binding=policy.binding,
                        backup=backup.name,
                        incoming_backup=incoming,
                    )
                    self.database_report(
                        dict(
                            policy.public(review),
                            code="database_local_ahead",
                            reason="reviewed_local",
                            baseline_hash=review["remote_hash"],
                            message=message,
                        )
                    )
                    self.record(result)
                    return dict(
                        result,
                        git=dict(
                            self.inspect(),
                            status_source="checked",
                            checked_at=stamp(),
                            upload_ready=True,
                        ),
                    )
        except (SyncError, OSError, sqlite3.Error, ValueError) as error:
            if accepted:
                return dict(
                    result or {},
                    ok=True,
                    action="keep_local",
                    code="database_local_kept",
                    message="The reviewed local database was kept and backed up. Local status could not be saved; check Git before uploading.",
                )
            if not isinstance(error, SyncError):
                error = SyncError(
                    "database_check_failed",
                    "Could not preserve the reviewed copies and record the choice. No database was replaced.",
                )
            return self.failure("keep_local", error)

    def use_remote(self, choice):
        """Apply an explicitly reviewed remote copy with stale checks and rollback."""
        adopted = False
        result = {}
        try:
            self.discover()
            with self.lock():
                state = self.inspect()
                if state["in_progress"]:
                    raise SyncError(
                        "operation_in_progress",
                        "Finish the active Git operation first.",
                    )
                if state["fingerprint"] != choice.get("fingerprint"):
                    raise SyncError(
                        "stale_target", "Git changed. Compare the databases again."
                    )
                self.fetch(state)
                state = self.inspect()
                from songranker.storage.git_database import DatabaseSync

                policy = DatabaseSync(self, state)
                if policy.binding != choice.get("binding"):
                    raise SyncError(
                        "stale_target",
                        "Database or destination changed. Compare again.",
                    )
                with policy.review() as reviewed:
                    if any(
                        reviewed.get(k) != choice.get(k)
                        for k in ("commit", "blob", "live_hash")
                    ):
                        raise SyncError(
                            "stale_database",
                            "Local or remote data changed. Neither database was replaced; compare again.",
                        )
                    backup = policy.adopt(reviewed)
                    adopted = True
                    result = dict(
                        policy.public(reviewed),
                        ok=True,
                        action="use_remote",
                        code="database_updated",
                        message="Reviewed remote database loaded. The previous local database was backed up. Reload open game tabs.",
                        backup=backup,
                        commit=reviewed["commit"],
                        database_binding=policy.binding,
                    )
                    policy.remember(
                        reviewed["commit"], reviewed["blob"], reviewed["remote_hash"]
                    )
                    self.database_report(
                        dict(
                            policy.public(reviewed),
                            code="database_matches",
                            local_hash=reviewed["remote_hash"],
                            baseline_hash=reviewed["remote_hash"],
                            local_songs=reviewed["remote_songs"],
                            different_rows={},
                            local_changes={},
                            remote_changes={},
                            message=result["message"],
                        )
                    )
                    self.record(result)
                    return dict(
                        result,
                        git=dict(
                            self.inspect(),
                            status_source="checked",
                            checked_at=stamp(),
                            upload_ready=True,
                        ),
                    )
        except (SyncError, OSError, sqlite3.Error, ValueError) as error:
            if adopted:
                return dict(
                    result,
                    message="Reviewed remote database was loaded and local data backed up. Refresh Git status; the local receipt could not be saved.",
                )
            if not isinstance(error, SyncError):
                error = SyncError(
                    "database_check_failed",
                    "Could not apply the reviewed remote copy. Local data was retained or rolled back.",
                )
            return self.failure("use_remote", error)

    def snapshot_commit(self, state, policy, review):
        """Create only a SQL commit atop the fetched remote using a disposable index.

        The real index, code checkout and local code commits remain untouched.
        A private pending ref keeps failed uploads recoverable and reusable.
        """
        pending_ref = "refs/song-ranker/pending/" + policy.binding
        pending = self.run(
            "rev-parse", "--verify", pending_ref, check=False
        ).stdout.strip()
        if pending:
            parent = self.run("rev-parse", pending + "^", check=False).stdout.strip()
            note = self.run("show", "-s", "--format=%B", pending).stdout
            if (
                parent == state["tracking_head"]
                and ("Song-Ranker-Hash: " + review["local_hash"]) in note
            ):
                paths = set(
                    filter(
                        None,
                        self.run(
                            "diff-tree",
                            "--no-commit-id",
                            "--name-only",
                            "-z",
                            "-r",
                            pending,
                        ).stdout.split("\0"),
                    )
                )
                if paths != {self.sql_rel}:
                    raise SyncError(
                        "commit_scope_changed",
                        "The pending backup contains unexpected files. Review it before retrying.",
                    )
                from songranker.storage.git_database import prepare_sql

                with tempfile.TemporaryDirectory(
                    dir=self.database.parent, prefix=".git_database_"
                ) as folder:
                    _, facts = prepare_sql(
                        policy.sql(policy.blob(pending)), folder, "pending"
                    )
                    if digest(facts) != review["local_hash"]:
                        raise SyncError(
                            "commit_scope_changed",
                            "The pending backup does not match its reviewed hash. Nothing was pushed.",
                        )
                return pending, pending_ref
        identity, registry = policy.remote_identity()
        key = policy.device_key()
        device = registry.get(key) or max(registry.values(), default=0) + 1
        registry[key] = device
        at = stamp().replace("+00:00", "Z")
        self.write_snapshot(device, at, review["local_hash"])
        blob = self.run("hash-object", "-w", "--", str(self.sql)).stdout.strip()
        with tempfile.TemporaryDirectory(dir=self.state_dir, prefix="index_") as folder:
            env = dict(
                GIT_INDEX_FILE=str(Path(folder) / "index"),
                GIT_AUTHOR_DATE=at,
                GIT_COMMITTER_DATE=at,
            )
            self.run("read-tree", state["tracking_head"], extra_env=env)
            self.run(
                "update-index",
                "--add",
                "--cacheinfo",
                "100644",
                blob,
                self.sql_rel,
                extra_env=env,
            )
            hook = self.run(
                "hook",
                "run",
                "--ignore-missing",
                "pre-commit",
                extra_env=env,
                check=False,
            )
            if hook.returncode:
                raise SyncError(
                    "commit_failed",
                    "The snapshot was saved, but its pre-commit hook failed. Fix the hook and retry.",
                )
            paths = set(
                filter(
                    None,
                    self.run(
                        "diff",
                        "--cached",
                        "--name-only",
                        "-z",
                        state["tracking_head"],
                        extra_env=env,
                    ).stdout.split("\0"),
                )
            )
            if (
                paths != {self.sql_rel}
                or self.run(
                    "rev-parse", ":" + self.sql_rel, extra_env=env
                ).stdout.strip()
                != blob
            ):
                raise SyncError(
                    "commit_scope_changed",
                    "A hook changed the reviewed snapshot or added files. Nothing was pushed.",
                )
            tree = self.run("write-tree", extra_env=env).stdout.strip()
            message = (
                "Save Song Ranker database backup\n\nSong-Ranker-Device: "
                + str(device)
                + "\nSong-Ranker-Devices: "
                + json.dumps(registry, sort_keys=True, separators=(",", ":"))
                + "\nSong-Ranker-Hash: "
                + review["local_hash"]
            )
            message_path = Path(folder) / "message"
            message_path.write_text(message, encoding="utf-8")
            required = [
                line for line in message.splitlines() if line.startswith("Song-Ranker-")
            ]
            for name, arguments in [
                ("prepare-commit-msg", [str(message_path), "message"]),
                ("commit-msg", [str(message_path)]),
            ]:
                hook = self.run(
                    "hook",
                    "run",
                    "--ignore-missing",
                    name,
                    "--",
                    *arguments,
                    extra_env=env,
                    check=False,
                )
                if hook.returncode:
                    raise SyncError(
                        "commit_failed",
                        "The snapshot was saved, but a commit-message hook failed. Fix it and retry.",
                    )
            message = message_path.read_text(encoding="utf-8")
            trailers = [
                line for line in message.splitlines() if line.startswith("Song-Ranker-")
            ]
            if (
                trailers != required
                or self.run("write-tree", extra_env=env).stdout.strip() != tree
            ):
                raise SyncError(
                    "commit_scope_changed",
                    "A hook changed backup metadata or staged files. Nothing was pushed.",
                )
            signing = (
                ["-S"]
                if self.run(
                    "config", "--bool", "--get", "commit.gpgsign", check=False
                ).stdout.strip()
                == "true"
                else []
            )
            created = self.run(
                "commit-tree",
                tree,
                "-p",
                state["tracking_head"],
                *signing,
                "-m",
                message,
                extra_env=env,
                check=False,
            )
            if created.returncode:
                raise SyncError(
                    "commit_failed",
                    "The snapshot was saved, but Git could not create/sign its backup commit. Check Git identity/signing and retry.",
                )
            commit = created.stdout.strip()
        self.run("update-ref", pending_ref, commit)
        return commit, pending_ref

    def upload(self, expected=None):
        """Publish a hash-reviewed SQL-only fast-forward even when local code is behind."""
        commit = None
        published = False
        try:
            self.discover()
            with self.lock():
                before = self.inspect()
                if expected and expected != before["fingerprint"]:
                    raise SyncError(
                        "stale_target",
                        "Branch or target changed. Refresh Git before uploading.",
                    )
                if before["in_progress"]:
                    raise SyncError(
                        "operation_in_progress",
                        "Finish the current Git operation before uploading.",
                    )
                if not self.database.is_file():
                    raise SyncError(
                        "database_missing",
                        "The live database does not exist. Start/restore the app first.",
                    )
                self.fetch(before)
                state = self.inspect()
                from songranker.storage.git_database import DatabaseSync, model
                from songranker.storage.database_io import snapshot

                policy = DatabaseSync(self, state)
                with policy.review() as reviewed:
                    review = dict(reviewed)
                    if review["code"] not in (
                        "database_matches",
                        "database_local_ahead",
                        "no_remote_snapshot",
                    ):
                        self.database_report(policy.public(review))
                        if "candidate" in review:
                            policy.incoming_backup(review)
                        raise SyncError("database_conflict", review["message"])
                    if review["code"] == "database_matches":
                        self.database_report(policy.public(review))
                        policy.remember(
                            review["commit"], review["blob"], review["remote_hash"]
                        )
                        result = self.record(
                            dict(
                                ok=True,
                                action="upload",
                                code="unchanged",
                                message="Local and remote database hashes match. No backup commit or upload was needed.",
                            )
                        )
                        return dict(
                            result,
                            git=dict(
                                self.inspect(),
                                status_source="checked",
                                checked_at=stamp(),
                                upload_ready=True,
                            ),
                        )
                    if "local_hash" not in review:
                        with snapshot(self.database) as live:
                            review["local_hash"] = digest(model(live))
                    commit, pending_ref = self.snapshot_commit(state, policy, review)
                    # Recheck both sides immediately before publishing. A final race is
                    # rejected atomically by the expected-head lease at the remote.
                    self.fetch(state)
                    latest = self.inspect()
                    if (
                        latest["fingerprint"] != state["fingerprint"]
                        or latest["tracking_head"] != state["tracking_head"]
                    ):
                        raise SyncError(
                            "stale_target",
                            "Remote or local Git changed while preparing the backup. Retry to compare again.",
                        )
                    with snapshot(self.database) as live:
                        if digest(model(live)) != review["local_hash"]:
                            raise SyncError(
                                "stale_database",
                                "Local data changed while preparing the backup. Retry to include it.",
                            )
                    if (
                        self.run("rev-parse", commit + "^").stdout.strip()
                        != state["tracking_head"]
                    ):
                        raise SyncError(
                            "commit_scope_changed",
                            "Backup commit does not extend the reviewed remote. No push was made.",
                        )
                    lease = (
                        "--force-with-lease=refs/heads/"
                        + state["target"]
                        + ":"
                        + state["tracking_head"]
                    )
                    pushed = self.run(
                        "push",
                        "--porcelain",
                        lease,
                        state["remote"],
                        commit + ":refs/heads/" + state["target"],
                        check=False,
                        network=True,
                    )
                    if pushed.returncode:
                        raise SyncError(
                            "push_failed",
                            "Upload was not confirmed. The local snapshot and pending backup commit are kept. Refresh/retry; a changed remote must be compared again.",
                        )
                    published = True
                    self.run(
                        "update-ref",
                        "refs/remotes/" + state["remote"] + "/" + state["target"],
                        commit,
                    )
                    self.run(
                        "update-ref",
                        "refs/song-ranker/last-upload/" + policy.binding,
                        commit,
                    )
                    # Only advance a matching code checkout; a behind/diverged code
                    # branch and its real index are left for normal startup/review.
                    if state["head"] == state["tracking_head"]:
                        self.run(
                            "update-ref",
                            "refs/heads/" + state["branch"],
                            commit,
                            state["head"],
                        )
                        blob = policy.blob(commit)
                        self.run(
                            "update-index",
                            "--add",
                            "--cacheinfo",
                            "100644",
                            blob,
                            self.sql_rel,
                        )
                    self.run("update-ref", "-d", pending_ref, commit)
                    policy.remember(commit, policy.blob(commit), review["local_hash"])
                    policy.state = dict(state, tracking_head=commit)
                    identity, registry = policy.remote_identity()
                    self.database_report(
                        dict(
                            code="database_uploaded",
                            local_device=registry.get(policy.device_key()),
                            remote_device=identity["device"],
                            remote_time=identity["committed_at"],
                            snapshot_commit=identity["snapshot_commit"],
                            message="The uploaded hash is the accepted database baseline.",
                            local_hash=review["local_hash"],
                            remote_hash=review["local_hash"],
                            baseline_hash=review["local_hash"],
                        )
                    )
                result = self.record(
                    dict(
                        ok=True,
                        action="upload",
                        code="uploaded",
                        message="Database backup uploaded on the latest remote code. Local code edits, staged files and the live database were kept.",
                        commit=commit,
                        database_binding=policy.binding,
                    )
                )
                return dict(
                    result,
                    git=dict(
                        self.inspect(),
                        status_source="checked",
                        checked_at=stamp(),
                        upload_ready=True,
                    ),
                )
        except (SyncError, OSError, sqlite3.Error, ValueError) as error:
            if published:
                return dict(
                    ok=True,
                    action="upload",
                    code="uploaded",
                    commit=commit,
                    message="The remote accepted the backup. Local status could not finish updating; refresh Git before retrying.",
                )
            if not isinstance(error, SyncError):
                error = SyncError(
                    "database_check_failed",
                    "Could not validate or prepare the backup. The live database and code were kept.",
                )
            return self.failure("upload", error, commit=commit)

    def startup(self):
        """Called only before application imports, while the server is stopped."""
        sql_copy = None
        modified_sql = False
        applying = False
        backup = None
        try:
            self.discover()
            with self.lock():
                state = self.inspect()
                if state["in_progress"]:
                    raise SyncError(
                        "operation_in_progress",
                        "Update skipped: finish the existing Git operation first. Using local code/data.",
                    )
                self.fetch(state)
                state = self.inspect()
                comparison = None
                if self.database.is_file():
                    try:
                        comparison = self.review_database(state)
                    except (SyncError, OSError, sqlite3.Error, ValueError):
                        # New source may be needed to understand a future snapshot.
                        # Check before pulling, retain the live DB, then recheck with
                        # the updated schema owner after the process handoff.
                        comparison = dict(
                            code="database_check_failed",
                            message="The database needs review with the updated code; local data is retained.",
                        )
                        self.database_report(comparison)
                if state["ahead"] and state["behind"]:
                    raise SyncError(
                        "diverged",
                        "Update skipped: local and remote commits diverged. Resolve them in Git; no automatic merge/rebase is attempted.",
                    )
                if not state["behind"]:
                    return self.record(
                        dict(
                            ok=True,
                            action="startup",
                            code="unchanged",
                            message="No incoming code update. The launcher will check database sync after bootstrap.",
                            database_sync=comparison,
                        )
                    )
                if state["staged_changes"]:
                    raise SyncError(
                        "staged_changes",
                        "Update skipped: staged changes need attention in Git. Using local code/data.",
                    )
                if state["code_changes"]:
                    raise SyncError(
                        "local_changes",
                        "Update skipped: local code edits are kept. Commit/reconcile them in Git before updating.",
                    )
                changed = list(
                    filter(
                        None,
                        self.run(
                            "diff",
                            "--name-only",
                            "-z",
                            state["head"],
                            state["tracking_head"],
                        ).stdout.split("\0"),
                    )
                )
                if any(self.protected(p) for p in changed):
                    raise SyncError(
                        "protected_changes",
                        "Update skipped: the incoming commit changes a database/private/generated file. Review it manually; local data was kept.",
                    )
                if self.prefix and any(
                    not p.startswith(self.prefix + "/") for p in changed
                ):
                    raise SyncError(
                        "outside_project",
                        "Update skipped: incoming changes extend outside this app folder. Review the repository update manually.",
                    )
                if self.database.is_file():
                    from songranker.storage.database_io import create_backup

                    backup = str(create_backup(self.database, "pre_git_update"))
                if self.sql_rel in changed and any(
                    r["path"] == self.sql_rel for r in state["changes"]
                ):
                    sql_copy = self.archive_sql("before_update")
                    modified_sql = True
                    exists = (
                        self.run(
                            "cat-file",
                            "-e",
                            state["head"] + ":" + self.sql_rel,
                            check=False,
                        ).returncode
                        == 0
                    )
                    if exists:
                        self.run(
                            "restore",
                            "--source=" + state["head"],
                            "--worktree",
                            "--",
                            self.sql_rel,
                        )
                    else:
                        self.sql.unlink(missing_ok=True)
                if self.inspect()["fingerprint"] != state["fingerprint"]:
                    raise SyncError(
                        "stale_target",
                        "Update stopped: the branch/target changed while preparing. Restart after checking Git.",
                    )
                applying = True
                self.run("merge", "--ff-only", "--no-edit", state["tracking_head"])
                # Timestamp/size-only Python caches can otherwise survive a rapid update.
                for relative in changed:
                    source = self.repo / relative
                    if source.suffix == ".py":
                        cache = source.parent / "__pycache__"
                        if cache.is_dir():
                            for p in cache.glob(source.stem + ".*.pyc"):
                                p.unlink()
                return self.record(
                    dict(
                        ok=True,
                        action="startup",
                        code="updated",
                        message="Code updated by fast-forward. The live database was kept; its hash/device decision is rechecked after bootstrap.",
                        database_sync=comparison,
                        head=state["tracking_head"],
                        backup=Path(backup).name if backup else None,
                    )
                )
        except (SyncError, OSError, sqlite3.Error) as error:
            if modified_sql and sql_copy:
                try:
                    self.sql.write_bytes(gzip.decompress(Path(sql_copy).read_bytes()))
                except OSError:
                    applying = True
            error = (
                error
                if isinstance(error, SyncError)
                else SyncError(
                    "update_failed",
                    "Could not prepare the update safely. Local data is kept; check backups and Git state.",
                )
            )
            return self.failure(
                "startup", error, stop_startup=applying or error.code == "busy"
            )
