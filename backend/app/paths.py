from __future__ import annotations

from pathlib import Path


def resolve_data_file_path(stored_file_path: str, data_dir: Path) -> Path | None:
    """Resolve stored document paths across Docker and local dev layouts.

    Documents may have been stored with Docker paths (/data/pdfs/x.pdf), host
    absolute paths (.../maktaba/data/pdfs/x.pdf), or relative paths. Try the
    stored path first, then map known data-dir-style paths under the configured
    DATA_DIR.
    """
    data_dir = data_dir.resolve()
    stored_path = Path(stored_file_path)
    candidates = [stored_path]

    if stored_path.is_absolute():
        try:
            candidates.append(data_dir / stored_path.relative_to("/data"))
        except ValueError:
            pass

        if "data" in stored_path.parts:
            data_index = len(stored_path.parts) - 1 - stored_path.parts[::-1].index("data")
            relative_after_data = Path(*stored_path.parts[data_index + 1 :])
            if str(relative_after_data) != ".":
                candidates.append(data_dir / relative_after_data)

        relative = stored_path.relative_to(stored_path.anchor) if stored_path.anchor else stored_path
        candidates.append(data_dir / relative)
    else:
        candidates.append(data_dir / stored_path)

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate
    return None
