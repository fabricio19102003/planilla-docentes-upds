from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ContractCiCorrection(Base):
    """Audit record and one-transaction grant for moving issued contracts to a corrected CI.

    The contract immutability trigger lets an UPDATE through only when teacher_ci is the
    single changed column and a row for (old_ci, new_ci) exists in the same transaction
    (txid, on PostgreSQL).
    """

    __tablename__ = "contract_ci_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    old_ci: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    new_ci: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    contract_count: Mapped[int] = mapped_column(Integer, nullable=False)
    corrected_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    corrected_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    txid: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
