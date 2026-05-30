from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feishu_open_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    profile = relationship("LearningProfile", back_populates="user", uselist=False)
    plans = relationship("LearningPlan", back_populates="user")


class LearningProfile(Base):
    __tablename__ = "learning_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    goal: Mapped[str] = mapped_column(String(64), default="提升")
    domains: Mapped[dict] = mapped_column(JSON, default=list)
    baselines: Mapped[dict] = mapped_column(JSON, default=dict)
    time_budget: Mapped[str] = mapped_column(String(64), default="")
    content_pref: Mapped[str] = mapped_column(String(32), default="混合")
    tone_pref: Mapped[str] = mapped_column(String(32), default="轻松")
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    growth_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    recent_feedback: Mapped[dict] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="profile")


class CourseTemplate(Base):
    __tablename__ = "course_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(32), index=True)
    stage: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512))
    roadmap: Mapped[dict] = mapped_column(JSON)
    sample_plan: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LearningPlan(Base):
    __tablename__ = "learning_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("course_templates.id"), nullable=True)
    outline: Mapped[dict] = mapped_column(JSON)
    locked_units: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="plans")


class LearningUnit(Base):
    __tablename__ = "learning_units"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("learning_plans.id"), index=True)
    domain: Mapped[str] = mapped_column(String(32))
    stage: Mapped[str] = mapped_column(String(32))
    unit_type: Mapped[str] = mapped_column(String(32))
    content: Mapped[dict] = mapped_column(JSON)
    scheduled_date: Mapped[str] = mapped_column(String(10))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


class Checkin(Base):
    __tablename__ = "checkins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("learning_units.id"))
    feedback: Mapped[str] = mapped_column(String(32), default="")
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
