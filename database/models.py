"""SQLAlchemy ORM models (SQLite locally, PostgreSQL in production)."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    student_name: Mapped[str] = mapped_column(String(120), default="")
    student_id: Mapped[str] = mapped_column(String(60), default="")
    department: Mapped[str] = mapped_column(String(120), default="", index=True)
    year: Mapped[str] = mapped_column(String(20), default="", index=True)
    course: Mapped[str] = mapped_column(String(160), default="", index=True)
    language: Mapped[str] = mapped_column(String(40), default="Unknown", index=True)   # detected
    language_hint: Mapped[str] = mapped_column(String(40), default="Auto Detect")      # chosen in the form
    feedback_text: Mapped[str] = mapped_column(Text)
    rating: Mapped[int] = mapped_column(Integer, nullable=True)
    # --- v2: category hierarchy, issue tracking, admin response
    category: Mapped[str] = mapped_column(String(40), default="Others", index=True)          # final category
    category_selected: Mapped[str] = mapped_column(String(40), default="Auto Detect")      # chosen by student
    category_detected: Mapped[str] = mapped_column(String(40), default="")                 # predicted by NLP
    status: Mapped[str] = mapped_column(String(20), default="", index=True)                # Open / In Progress / ...
    admin_response: Mapped[str] = mapped_column(Text, default="")                          # latest response
    issue_id: Mapped[str] = mapped_column(String(30), default="", index=True)              # EDU-2026-0001
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    results: Mapped[list["AnalysisResult"]] = relationship(
        back_populates="feedback", cascade="all, delete-orphan", order_by="AnalysisResult.id")
    issue: Mapped["Issue"] = relationship(cascade="all, delete-orphan", uselist=False)
    responses: Mapped[list["AdminResponse"]] = relationship(
        cascade="all, delete-orphan", order_by="AdminResponse.id")


class AnalysisResult(Base):
    """One row per (feedback, aspect). Feedback-level sentiment is repeated on each row."""
    __tablename__ = "analysis_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback.id", ondelete="CASCADE"), index=True)
    sentiment: Mapped[str] = mapped_column(String(20), index=True)
    sentiment_confidence: Mapped[float] = mapped_column(Float)
    aspect: Mapped[str] = mapped_column(String(40), index=True)
    category: Mapped[str] = mapped_column(String(40), default="", index=True)
    aspect_sentiment: Mapped[str] = mapped_column(String(20), index=True)
    aspect_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[str] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(20), index=True)
    priority_score: Mapped[float] = mapped_column(Float)
    frequency: Mapped[int] = mapped_column(Integer, default=0)
    explanation: Mapped[str] = mapped_column(Text, default="{}")      # JSON
    recommendation: Mapped[str] = mapped_column(Text, default="{}")   # JSON {en,ta,hi,escalate}
    model_version: Mapped[str] = mapped_column(String(80), default="")
    nlp_mode: Mapped[str] = mapped_column(String(60), default="")

    feedback: Mapped["Feedback"] = relationship(back_populates="results")


class User(Base):
    """Authentication account. Passwords are stored ONLY as salted hashes (werkzeug.security)."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="admin")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AdminUser(Base):
    """LEGACY table of earlier EduPulse versions. Rows are copied into `users` on start-up; never written to."""
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    model_name: Mapped[str] = mapped_column(String(160))
    mode: Mapped[str] = mapped_column(String(60))
    dataset_size: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    macro_f1: Mapped[float] = mapped_column(Float, default=0.0)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="{}")


class Issue(Base):
    """A trackable ticket created for a negative feedback (or manually by an admin)."""
    __tablename__ = "issues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)       # EDU-2026-0001
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback.id", ondelete="CASCADE"), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(40), default="Others", index=True)
    aspect: Mapped[str] = mapped_column(String(40), default="General", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="LOW", index=True)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="Open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    history: Mapped[list["IssueHistory"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan", order_by="IssueHistory.id")


class IssueHistory(Base):
    __tablename__ = "issue_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_pk: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    old_status: Mapped[str] = mapped_column(String(20), default="")
    new_status: Mapped[str] = mapped_column(String(20), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    changed_by: Mapped[str] = mapped_column(String(80), default="system")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    issue: Mapped["Issue"] = relationship(back_populates="history")


class AdminResponse(Base):
    __tablename__ = "admin_responses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback.id", ondelete="CASCADE"), index=True)
    response: Mapped[str] = mapped_column(Text)
    admin: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
