from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="admin", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), index=True, nullable=False)
    sector = Column(String(50), default="defense", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    uploads = relationship("Upload", back_populates="company", cascade="all, delete-orphan")
    analyses = relationship("Analysis", back_populates="company", cascade="all, delete-orphan")


class Upload(Base):
    __tablename__ = "uploads"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    kind = Column(String(50), nullable=False)  # "excel"
    filename = Column(String(255), nullable=False)
    path = Column(String(500), nullable=False)

    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="uploads")


class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    # JSON string (basit)
    result_json = Column(Text, nullable=False)
    pdf_path = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="analyses")
