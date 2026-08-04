from __future__ import annotations


class GameNotFoundError(Exception):
    pass


class ActiveGameExistsError(Exception):
    pass


class SessionNotFoundError(Exception):
    pass


class InvalidGameStateError(Exception):
    pass


class PlayerAlreadyJoinedError(Exception):
    pass


class PlayerLimitReachedError(Exception):
    pass


class InsufficientPlayersError(Exception):
    pass
