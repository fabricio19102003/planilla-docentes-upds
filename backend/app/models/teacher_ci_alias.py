from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TeacherCiAlias(Base):
    """A CI a teacher used before a correction.

    Published billing snapshots are immutable and keep the CI that was current
    when they were published; the portal resolves them through these aliases.
    """

    __tablename__ = "teacher_ci_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    previous_ci: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="CASCADE"), nullable=False, index=True
    )
    # Snapshots published after this moment under previous_ci belong to whoever holds it then.
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<TeacherCiAlias {self.previous_ci} -> {self.teacher_ci}>"
