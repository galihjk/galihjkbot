from __future__ import annotations


class AutoreplyError(Exception):
    pass


class AutoreplySourceFetchError(AutoreplyError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class AutoreplySourceTooLargeError(AutoreplyError):
    pass


class AutoreplyCSVParseError(AutoreplyError):
    pass


class AutoreplyHeaderError(AutoreplyError):
    pass


class AutoreplyRuleValidationError(AutoreplyError):
    pass


class AutoreplySyncInProgressError(AutoreplyError):
    pass


class AutoreplySnapshotNotFoundError(AutoreplyError):
    pass


class AutoreplyTemplateError(AutoreplyError):
    pass


class AutoreplySendError(AutoreplyError):
    pass


class UnsupportedMediaTypeError(AutoreplyError):
    pass
