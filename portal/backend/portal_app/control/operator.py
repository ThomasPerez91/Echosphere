"""Technical operator shell only, never a public player create/join API."""

import argparse
import json
from uuid import UUID

from portal_app.accounts.service import Accounts
from portal_app.control.service import Lobby
from portal_app.core.config import Settings
from portal_app.persistence.database import create_database_engine, create_session_factory


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    provision = commands.add_parser("provision")
    provision.add_argument("--universe-id", required=True, type=UUID)
    provision.add_argument("--backend", required=True)
    provision.add_argument("--name", required=True)
    provision.add_argument("--seed", required=True)
    access = commands.add_parser("set-access")
    access.add_argument("--user-id", required=True, type=UUID)
    access.add_argument("--universe-id", required=True, type=UUID)
    access.add_argument("--status", required=True, choices=("active", "suspended", "revoked"))
    # Explicit JSON, including [] for no Empire rights; no inferred owner or default permission.
    access.add_argument("--bindings", required=True, type=json.loads)
    args = parser.parse_args()
    engine = create_database_engine(Settings())
    try:
        lobby = Lobby(Accounts(create_session_factory(engine), Settings()))
        if args.command == "provision":
            result = {
                "operation_id": lobby.provision(
                    args.universe_id, args.name, args.seed, args.backend
                )
            }
        else:
            result = lobby.set_access(args.user_id, args.universe_id, args.status, args.bindings)
        print(json.dumps(result))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
