"""Validate required documents and repository-local Markdown links without dependencies."""

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "context.md",
    "progress.md",
    "docs/00-product-vision.md",
    *[
        f"docs/01-game-design/{name}.md"
        for name in (
            "core-loop",
            "player-session",
            "resources-economy",
            "planets-colonies",
            "buildings",
            "research",
            "galaxy",
            "system-view",
            "exploration",
            "fleets",
            "combat",
            "colonization",
            "artificial-intelligence",
            "fog-of-war",
            "balance-philosophy",
            "progression",
            "game-modes",
            "colony-economy-v0.1",
            "planetary-defense",
        )
    ],
    *[
        f"docs/02-ux-ui/{name}.md"
        for name in (
            "information-architecture",
            "desktop",
            "mobile",
            "design-system",
            "accessibility",
        )
    ],
    *[
        f"docs/03-technical/{name}.md"
        for name in (
            "architecture",
            "data-model",
            "event-engine",
            "resource-calculation",
            "api",
            "frontend",
            "system-view",
            "backend",
            "ai-engine",
            "security",
            "identity-contracts",
            "portal-foundation",
            "portal-registration",
            "portal-sessions",
            "portal-account-security",
            "portal-mfa",
            "portal-game-control",
            "colony-api-ui",
            "game-handoff",
            "portal-game-ui",
            "portal-operations",
            "deployment",
        )
    ],
    *[
        f"docs/04-quality/{name}.md"
        for name in ("testing-strategy", "performance", "definition-of-done")
    ],
    *[
        f"docs/05-project/{name}.md"
        for name in ("roadmap", "backlog", "releases", "open-questions", "step-8-plan")
    ],
    *[
        f"docs/adr/{name}.md"
        for name in (
            "README",
            "0001-modular-monolith",
            "0002-event-driven-time-model",
            "0003-responsive-web-ui",
            "0004-world-persistence",
            "0005-colony-time-engine",
            "0006-universe-game-instance",
            "0007-colony-economy",
            "0008-control-plane-game-data-plane",
        )
    ],
    *[
        f"docs/06-handoff/{name}.md"
        for name in (
            "README", "source-map", "decision-status", "work-codex-handoff",
            "known-gaps", "pr-5-audit",
        )
    ],
}
errors = [
    f"Missing: {name}" for name in sorted(REQUIRED) if not (ROOT / name).is_file()
]
files = list(ROOT.glob("*.md")) + list((ROOT / "docs").rglob("*.md"))
files += [ROOT / "game_data/README.md"]
for file in files:
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", file.read_text()):
        if target.startswith(("https://", "http://", "mailto:", "#")):
            continue
        path = unquote(target.split("#", 1)[0])
        if not (file.parent / path).exists():
            errors.append(f"Broken link: {file.relative_to(ROOT)} -> {target}")
if errors:
    raise SystemExit("\n".join(errors))
print(f"Documentation OK: {len(files)} files, required paths and local links verified")
