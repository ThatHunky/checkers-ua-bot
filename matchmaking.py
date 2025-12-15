"""Matchmaking utilities for Checkers bot."""

from __future__ import annotations

import logging
import random
import string
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from repository import GameRepository
from ratings import RatingSystem, INITIAL_RATING

logger = logging.getLogger(__name__)


@dataclass
class TicketStatus:
    user_id: int
    chat_id: int
    mode: str
    status: str
    created_at: datetime
    rating: int
    opponent: Optional[int] = None


class MatchmakingService:
    """High-level matchmaking coordination built on top of GameRepository."""

    BASE_DELTA = 50
    STEP_DELTA = 50
    STEP_SECONDS = 10
    MAX_DELTA = 400

    def __init__(self, repository: GameRepository, rating_system: Optional[RatingSystem] = None):
        self.repo = repository
        self.rating_system = rating_system

    async def _get_rating(self, user_id: int, username: Optional[str]) -> int:
        if not self.rating_system:
            return self.repo.get_user_rating(user_id, INITIAL_RATING)
        try:
            player = await self.rating_system.get_player(user_id, username)
            return int(player.get("rating", INITIAL_RATING))
        except Exception:
            logger.exception("Failed to fetch rating, falling back to default")
            return INITIAL_RATING

    async def enqueue(self, user_id: int, chat_id: int, mode: str, username: Optional[str]):
        rating = await self._get_rating(user_id, username)
        ticket = self.repo.mm_enqueue(user_id, chat_id, mode, rating)
        return TicketStatus(
            user_id=user_id,
            chat_id=chat_id,
            mode=mode,
            status=ticket.get("status", "unknown"),
            created_at=datetime.fromisoformat(ticket["created_at"]),
            rating=rating,
        )

    def cancel(self, user_id: int) -> bool:
        return self.repo.mm_cancel(user_id)

    def status(self, user_id: int) -> Optional[TicketStatus]:
        ticket = self.repo.mm_status(user_id)
        if not ticket:
            return None
        return TicketStatus(
            user_id=user_id,
            chat_id=int(ticket.get("chat_id", 0)),
            mode=ticket.get("mode", "rated"),
            status=ticket.get("status", "unknown"),
            created_at=datetime.fromisoformat(ticket["created_at"]),
            rating=int(float(ticket.get("rating", INITIAL_RATING))),
            opponent=int(ticket["opponent"]) if ticket.get("opponent") else None,
        )

    def try_match(self, mode: str):
        return self.repo.mm_try_match(
            mode,
            base_delta=self.BASE_DELTA,
            step=self.STEP_DELTA,
            step_seconds=self.STEP_SECONDS,
            max_delta=self.MAX_DELTA,
        )

    def create_invite(self, user_id: int, chat_id: int, mode: str) -> dict:
        code = self._generate_code()
        data = self.repo.mm_create_invite(user_id, chat_id, mode, code)
        data["code"] = code
        return data

    def accept_invite(self, user_id: int, chat_id: int, code: str):
        return self.repo.mm_accept_invite(user_id, chat_id, code)

    @staticmethod
    def _generate_code(length: int = 6) -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(random.choice(alphabet) for _ in range(length))

