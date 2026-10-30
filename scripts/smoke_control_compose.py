"""Real mTLS/control delivery using two disposable databases; preserve all retained volumes."""

import json
import subprocess
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def run(*args, input=None):
    result = subprocess.run(
        args, input=input, text=True, cwd=ROOT, capture_output=True, check=False
    )
    if result.returncode:
        for line in result.stderr.splitlines():
            if line.startswith("control-smoke:"):
                print(line)
        # Never include subprocess arguments/environment or unfiltered DB errors in a failure.
        raise RuntimeError(
            f"Control smoke subprocess failed: {args[0]} (exit {result.returncode})"
        )
    return result.stdout.strip()


def compose(*args, input=None):
    return run("docker", "compose", *args, input=input)


def inspect_service(service):
    return json.loads(run("docker", "inspect", compose("ps", "-aq", service)))[0]


def psql(service, *args):
    return compose(
        "exec", "-T", service, "sh", "-c", 'exec "$@" -U "$POSTGRES_USER"', "sh", *args
    )


def main():
    suffix = uuid4().hex[:8]
    database = f"echosphere_control_{suffix}_test"
    network, container, rogue = (
        f"echosphere-control-{suffix}-{part}" for part in ("net", "game", "rogue")
    )
    created_databases = []
    network_created = volume_created = container_started = False
    try:
        for service in ("postgres", "portal-postgres"):
            psql(service, "createdb", database)
            created_databases.append(service)
        run("docker", "network", "create", "--internal", network)
        network_created = True
        run("docker", "volume", "create", rogue)
        volume_created = True
        compose(
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "--user",
            "0:0",
            "-v",
            rogue + ":/run/rogue",
            "control-tls-init",
            "python",
            "-c",
            "from pathlib import Path; from portal_app.core.init_control_tls import ca,leaf; leaf(Path('/run/rogue'),'client','untrusted-service',ca(Path('/run/control-ca'),'portal-client-ca'),client=True)",
        )
        game, portal = (
            inspect_service("game-control"),
            inspect_service("portal-control-worker"),
        )
        game_network = next(
            iter(inspect_service("postgres")["NetworkSettings"]["Networks"])
        )
        portal_network = next(
            iter(inspect_service("portal-postgres")["NetworkSettings"]["Networks"])
        )

        def mount(info, path):
            return next(
                row["Name"] for row in info["Mounts"] if row["Destination"] == path
            )

        game_environment = [
            entry
            for entry in game["Config"]["Env"]
            if entry.startswith("POSTGRES_") and not entry.startswith("POSTGRES_DB=")
        ]
        args = [
            "docker",
            "run",
            "-d",
            "--name",
            container,
            "--network",
            game_network,
            "--network",
            f"name={network},alias=game-control",
            "-v",
            mount(game, "/run/game-control") + ":/run/game-control:ro",
        ]
        for entry in game_environment:
            args.extend(("-e", entry))
        args.extend(
            (
                "-e",
                "POSTGRES_DB=" + database,
                game["Config"]["Image"],
                "sh",
                "-c",
                "alembic upgrade head && python -m app.control.http",
            )
        )
        run(*args)
        container_started = True
        portal_environment = [
            entry
            for entry in portal["Config"]["Env"]
            if entry.startswith("PORTAL_POSTGRES_")
            and not entry.startswith("PORTAL_POSTGRES_DB=")
        ]
        args = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--network",
            portal_network,
            "--network",
            network,
            "-v",
            mount(portal, "/run/portal-control") + ":/run/portal-control:ro",
            "-v",
            rogue + ":/run/rogue:ro",
        ]
        for entry in portal_environment:
            args.extend(("-e", entry))
        args.extend(
            (
                "-e",
                "PORTAL_POSTGRES_DB=" + database,
                "-e",
                "RUN_CONTROL_SMOKE=1",
                portal["Config"]["Image"],
                "sh",
                "-c",
                "alembic upgrade head && python -",
            )
        )
        print(run(*args, input=(ROOT / "scripts/control_smoke_client.py").read_text()))
    finally:
        if container_started:
            run("docker", "stop", "--timeout", "5", container)
            run("docker", "rm", container)
        for service in reversed(created_databases):
            psql(service, "dropdb", database)
        if network_created:
            run("docker", "network", "rm", network)
        if volume_created:
            run("docker", "volume", "rm", rogue)
    print(
        "Control smoke passed: real private mTLS, isolated Portal→Game delivery and revocations; temporary data removed"
    )


if __name__ == "__main__":
    main()
