from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UploadedFile(Base):
    """One row per uploaded file."""

    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)            # COMPLETED or FAILED
    crs: Mapped[str | None] = mapped_column(String, nullable=True)
    feature_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # One file has many features. Deleting a file deletes its features too.
    features: Mapped[list["Feature"]] = relationship(
        back_populates="file", cascade="all, delete-orphan", order_by="Feature.index"
    )


class Feature(Base):
    """One row per feature inside an uploaded file."""

    __tablename__ = "features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)
    geometry_type: Mapped[str | None] = mapped_column(String, nullable=True)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)

    status: Mapped[str] = mapped_column(String)
    area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    perimeter_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    projected_crs: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    file: Mapped[UploadedFile] = relationship(back_populates="features")