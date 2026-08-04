from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar

DEFAULT_PAGE_SIZE = 10

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: Sequence[T]
    page: int
    page_size: int
    total_items: int

    @property
    def total_pages(self) -> int:
        if self.total_items == 0:
            return 1
        return -(-self.total_items // self.page_size)


def clamp_page(page: int, total_pages: int) -> int:
    return max(1, min(page, total_pages))


def offset_for_page(page: int, page_size: int) -> int:
    return (page - 1) * page_size
