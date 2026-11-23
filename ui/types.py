"""Small, dependency-free contracts used by shared interface components."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelIdentity:
    """Display metadata for one dashboard quadrant."""

    number: int
    key: str
    title: str
    subtitle: str
    owner: str

    @property
    def label(self) -> str:
        """Return the compact uppercase label used in panel chrome."""
        return f"{self.number:02d} / {self.title}".upper()
