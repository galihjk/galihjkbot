from __future__ import annotations


def chunk_lines(lines: list[str], max_chars: int = 4000) -> list[str]:
    """Gabungkan `lines` jadi sesedikit mungkin pesan, tiap pesan maksimal
    `max_chars` karakter (default di bawah limit Telegram ~4096, sisakan
    margin) -- dipakai untuk leaderboard yang bisa berisi banyak baris.
    Satu baris yang sendirian sudah melebihi `max_chars` tetap dikirim utuh
    sebagai pesannya sendiri (tidak dipotong di tengah kata)."""
    if not lines:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # +1 utk newline penggabung
        if current and current_len + line_len > max_chars:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks


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
