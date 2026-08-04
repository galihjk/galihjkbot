from __future__ import annotations


def parse_list_command_args(
    raw_args: str, valid_statuses: set[str]
) -> tuple[str | None, int]:
    """Parse argumen command list seperti 'active page 2' -> ('active', 2)."""
    tokens = raw_args.split()
    status: str | None = None
    page = 1

    i = 0
    while i < len(tokens):
        token = tokens[i].lower()
        if token in valid_statuses:
            status = token
        elif token == "page" and i + 1 < len(tokens):
            try:
                page = int(tokens[i + 1])
            except ValueError:
                pass
            i += 1
        i += 1

    return status, max(page, 1)
