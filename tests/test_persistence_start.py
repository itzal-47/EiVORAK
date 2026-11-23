import subprocess
import sys

from scripts.start import LITESTREAM_CONFIG, start


class ExecReached(Exception):
    pass


def _raise_exec(executable, arguments, environment):
    raise ExecReached((executable, arguments, environment))


def test_local_start_does_not_require_litestream(monkeypatch):
    try:
        start(environment={"PATH": ""}, exec_process=_raise_exec)
    except ExecReached as exc:
        executable, arguments, environment = exc.args[0]
    else:
        raise AssertionError("o processo do bot devia ser iniciado")
    assert executable == sys.executable
    assert arguments == [sys.executable, "-m", "eivorak"]
    assert environment["DATABASE_PATH"] == "eivorak_brain.db"


def test_missing_database_without_replica_still_starts_litestream_exec():
    env = {
        "DATABASE_PATH": "/tmp/eivorak-test.db",
        "LITESTREAM_ENDPOINT": "https://s3.example.test",
        "LITESTREAM_BUCKET": "test-bucket",
        "LITESTREAM_ACCESS_KEY_ID": "test-key",
        "LITESTREAM_SECRET_ACCESS_KEY": "test-secret",
    }
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        # Litestream's -if-replica-exists behavior returns success for an empty bucket.
        return subprocess.CompletedProcess(command, 0)

    try:
        start(environment=env, run=fake_run, exec_process=_raise_exec, database_exists=lambda path: False)
    except ExecReached as exc:
        executable, arguments, passed_environment = exc.args[0]
    else:
        raise AssertionError("Litestream devia passar a supervisionar o bot")

    assert len(commands) == 1
    restore_command, restore_options = commands[0]
    assert restore_command[:3] == ["litestream", "restore", "-config"]
    assert str(LITESTREAM_CONFIG) in restore_command
    assert "-if-replica-exists" in restore_command
    assert restore_options["env"]["LITESTREAM_SECRET_ACCESS_KEY"] == "test-secret"
    assert executable == "litestream"
    assert arguments[:3] == ["litestream", "replicate", "-config"]
    assert "-restore-if-db-not-exists" in arguments
    assert "-exec" in arguments
    assert passed_environment["DATABASE_PATH"] == "/tmp/eivorak-test.db"


def test_partial_litestream_settings_fail_clearly():
    status = start(environment={"LITESTREAM_BUCKET": "bucket"})
    assert status == 2
