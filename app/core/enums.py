from __future__ import annotations

from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    BANNED = "banned"
    INACTIVE = "inactive"


class GroupStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class AdminRole(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class GameStatus(str, Enum):
    CREATED = "created"
    LOBBY = "lobby"
    STARTING = "starting"
    RUNNING = "running"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    ABORTED = "aborted"
    FAILED = "failed"


ACTIVE_GAME_STATUSES = frozenset(
    {GameStatus.CREATED, GameStatus.LOBBY, GameStatus.STARTING, GameStatus.RUNNING}
)


class GamePlayerStatus(str, Enum):
    JOINED = "joined"
    ACTIVE = "active"
    LEFT = "left"
    ELIMINATED = "eliminated"
    WINNER = "winner"
    DISQUALIFIED = "disqualified"


class GameEventType(str, Enum):
    LOBBY_CREATED = "lobby_created"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    LOBBY_EXTENDED = "lobby_extended"
    READY_CHECK_STARTED = "ready_check_started"
    PLAYER_READY = "player_ready"
    PLAYER_KICKED_NOT_READY = "player_kicked_not_ready"
    GAME_STARTED = "game_started"
    PLAYER_ACTION = "player_action"
    GAME_FINISHED = "game_finished"
    GAME_CANCELLED = "game_cancelled"
