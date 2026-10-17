from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    reports = relationship("Report", back_populates="client")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    original_filename = Column(String, nullable=False)
    unique_filename = Column(String, unique=True, nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    client = relationship("Client", back_populates="reports")
    metrics = relationship("Metric", back_populates="report")


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False)
    date = Column(Date, nullable=False)
    campaign_name = Column(String, nullable=False)
    impressions = Column(Integer, nullable=False, default=0)
    clicks = Column(Integer, nullable=False, default=0)
    spend = Column(Float, nullable=False, default=0.0)
    conversions = Column(Integer, nullable=False, default=0)

    report = relationship("Report", back_populates="metrics")
