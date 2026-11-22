from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

MatchSource = Literal["steam", "faceit"]

@dataclass
class MatchSummary:
    match_id: str
    source: MatchSource
    played_at: str | None = None
    map_name: str | None = None
    demo_url: str | None = None

class MatchProvider(ABC):
    source: MatchSource

    @abstractmethod
    async def list_matches(self, player_id: str, limit: int = 20) -> list[MatchSummary]:
        """Return verified matches for a player. Never synthesize records."""
        raise NotImplementedError

    @abstractmethod
    async def get_demo_url(self, match_id: str) -> str | None:
        """Return a provider-authorized demo URL, if available."""
        raise NotImplementedError
