from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class AutoreplyRule(Base, TimestampMixin):
    __tablename__ = "autoreply_rules"
    __table_args__ = (
        UniqueConstraint(
            "rule_set_id", "source_row", name="uq_autoreply_rules_set_row"
        ),
        Index(
            "ix_autoreply_rules_set_disabled_row",
            "rule_set_id",
            "disabled",
            "source_row",
        ),
        CheckConstraint("source_row > 0", name="ck_autoreply_rules_source_row"),
        CheckConstraint("command <> ''", name="ck_autoreply_rules_command"),
        CheckConstraint(
            "message_template <> ''", name="ck_autoreply_rules_message_template"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_set_id: Mapped[int] = mapped_column(
        ForeignKey("autoreply_rule_sets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_command: Mapped[str] = mapped_column(Text, nullable=False)
    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    response_type: Mapped[str] = mapped_column(String(16), nullable=False)
    media_file_id: Mapped[str | None] = mapped_column(Text)
    match_all: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reply_to_sender: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    reply_to_replied: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    admin_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
