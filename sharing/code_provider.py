from abc import ABC, abstractmethod


class CodeProvider(ABC):
    """
    Abstract interface for share-code storage and retrieval.

    Swap implementations (S3, DynamoDB, Redis, etc.) by injecting a different
    concrete subclass — the rest of the app only depends on this interface.
    """

    @abstractmethod
    def generate_code(self, path: str) -> str:
        """Persist a code → S3 path mapping and return the generated code."""
        ...

    @abstractmethod
    def resolve_code(self, code: str) -> str | None:
        """Return the S3 path prefix for the given code, or None if not found."""
        ...

    @abstractmethod
    def revoke_code(self, code: str) -> None:
        """Delete a code so it can no longer be redeemed."""
        ...
