"""AGENTS.md loader for project-level agent instructions.

Implements the AGENTS.md open standard — project-level instruction files
that are auto-loaded into the agent's system prompt at init time.
Unlike skills (progressively disclosed), AGENTS.md content is eagerly loaded.

See: https://agents.md
"""
import logging
from pathlib import Path
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

# Guard against huge files
MAX_AGENTS_MD_SIZE = 100_000


def discover_agents_md(start_dir: Union[str, Path]) -> List[Path]:
    """Walk from start_dir upward, collecting all AGENTS.md files.

    Returns paths ordered root-first, closest-last so that the closest
    file's instructions naturally take precedence (appended last).

    Args:
        start_dir: Directory to start searching from.

    Returns:
        List of Path objects to AGENTS.md files, root-first ordering.
    """
    start = Path(start_dir).resolve()
    found: List[Path] = []

    current = start
    while True:
        candidate = current / "AGENTS.md"
        if candidate.is_file():
            found.append(candidate)
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            break
        current = parent

    # found is closest-first; reverse to root-first
    found.reverse()
    return found


def load_agents_md(
    agents_md: Optional[Union[bool, str, List[str]]] = None,
    base_dir: Optional[Union[str, Path]] = None,
) -> str:
    """Load AGENTS.md content based on the configuration value.

    Args:
        agents_md: Configuration value controlling AGENTS.md loading:
            - None (default): no auto-discovery, return ""
            - True: auto-discover from base_dir (or CWD) upward
            - False: explicitly disabled, return ""
            - str: explicit path to one file
            - List[str]: multiple explicit paths
        base_dir: Base directory for auto-discovery (used when agents_md=True).
                  Defaults to CWD if not provided.

    Returns:
        Combined content string from all loaded AGENTS.md files,
        joined with "\\n\\n---\\n\\n". Empty string if nothing loaded.
    """
    if agents_md is None or agents_md is False:
        return ""

    paths: List[Path] = []

    if agents_md is True:
        dir_to_search = Path(base_dir) if base_dir else Path.cwd()
        paths = discover_agents_md(dir_to_search)
    elif isinstance(agents_md, str):
        paths = [Path(agents_md)]
    elif isinstance(agents_md, list):
        paths = [Path(p) for p in agents_md]
    else:
        logger.warning(f"Unexpected agents_md type: {type(agents_md)}, ignoring")
        return ""

    if not paths:
        logger.debug("No AGENTS.md files found")
        return ""

    contents: List[str] = []

    for path in paths:
        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            logger.warning(f"AGENTS.md not found: {resolved}, skipping")
            continue

        try:
            text = resolved.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read {resolved}: {e}, skipping")
            continue

        contents.append(text)

    result = "\n\n---\n\n".join(contents)
    if len(result) > MAX_AGENTS_MD_SIZE:
        logger.warning(
            f"AGENTS.md content exceeds {MAX_AGENTS_MD_SIZE} chars, truncating"
        )
        result = result[:MAX_AGENTS_MD_SIZE]
    return result
