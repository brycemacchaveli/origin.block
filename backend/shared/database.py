"""
Database models and connection management for the blockchain financial platform.

This module provides SQLAlchemy ORM models for Customer, LoanApplication, Actor,
and ComplianceEvent entities, along with database session management and utilities.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from enum import Enum

from sqlalchemy import (
    create_engine, 
    Column, 
    Integer, 
    String, 
    DateTime, 
    Boolean, 
    Text, 
    Float,
    ForeignKey,
    JSON,
    Index,
    text
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.pool import StaticPool
import structlog

from .config import settings

logger = structlog.get_logger(__name__)

# SQLAlchemy base class
Base = declarative_base()


class ActorModel(Base):
    """Actor database model representing users and systems."""
    
    __tablename__ = "actors"
    
    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(String(255), unique=True, index=True, nullable=False)
    actor_type = Column(String(50), nullable=False)  # Internal_User, External_Partner, System
    actor_name = Column(String(255), nullable=False)
    role = Column(String(100), nullable=False)  # Underwriter, Introducer, etc.
    blockchain_identity = Column(String(255), nullable=True)  # x.509 Certificate ID
    permissions = Column(JSON, nullable=True)  # List of permission strings
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships - removed back_populates to avoid ambiguous foreign keys
    customers = relationship("CustomerModel", foreign_keys="CustomerModel.created_by_actor_id")
    loan_applications = relationship("LoanApplicationModel", foreign_keys="LoanApplicationModel.created_by_actor_id")
    compliance_events = relationship("ComplianceEventModel", foreign_keys="ComplianceEventModel.actor_id")
    
    # Indexes
    __table_args__ = (
        Index('idx_actor_type_role', 'actor_type', 'role'),
        Index('idx_actor_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<ActorModel(actor_id='{self.actor_id}', role='{self.role}')>"


class CustomerModel(Base):
    """Customer database model for master customer data."""
    
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(255), unique=True, index=True, nullable=False)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    date_of_birth = Column(DateTime, nullable=True)
    national_id_hash = Column(String(255), nullable=True)  # Hashed/encrypted national ID
    address = Column(Text, nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    kyc_status = Column(String(50), nullable=False, default='PENDING')  # PENDING, VERIFIED, FAILED
    aml_status = Column(String(50), nullable=False, default='PENDING')  # PENDING, CLEAR, FLAGGED
    consent_preferences = Column(JSON, nullable=True)  # Consent data
    blockchain_record_hash = Column(String(255), nullable=True)  # Hash of blockchain record
    created_by_actor_id = Column(Integer, ForeignKey('actors.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    created_by_actor = relationship("ActorModel", foreign_keys=[created_by_actor_id])
    loan_applications = relationship("LoanApplicationModel", back_populates="customer")
    customer_history = relationship("CustomerHistoryModel", back_populates="customer")
    
    # Indexes
    __table_args__ = (
        Index('idx_customer_name', 'first_name', 'last_name'),
        Index('idx_customer_kyc_aml', 'kyc_status', 'aml_status'),
        Index('idx_customer_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<CustomerModel(customer_id='{self.customer_id}', name='{self.first_name} {self.last_name}')>"


class CustomerHistoryModel(Base):
    """Customer history model for tracking changes."""
    
    __tablename__ = "customer_history"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    change_type = Column(String(50), nullable=False)  # CREATE, UPDATE, STATUS_CHANGE
    field_name = Column(String(100), nullable=True)  # Field that was changed
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by_actor_id = Column(Integer, ForeignKey('actors.id'), nullable=False)
    blockchain_transaction_id = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    customer = relationship("CustomerModel", back_populates="customer_history")
    changed_by_actor = relationship("ActorModel")
    
    # Indexes
    __table_args__ = (
        Index('idx_customer_history_customer', 'customer_id'),
        Index('idx_customer_history_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<CustomerHistoryModel(customer_id={self.customer_id}, change_type='{self.change_type}')>"


class LoanApplicationModel(Base):
    """Loan application database model."""
    
    __tablename__ = "loan_applications"
    
    id = Column(Integer, primary_key=True, index=True)
    loan_application_id = Column(String(255), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    application_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    requested_amount = Column(Float, nullable=False)
    loan_type = Column(String(100), nullable=False)  # PERSONAL, MORTGAGE, BUSINESS, etc.
    application_status = Column(String(50), nullable=False, default='SUBMITTED')  # SUBMITTED, UNDERWRITING, APPROVED, REJECTED, DISBURSED
    introducer_id = Column(String(255), nullable=True)  # External partner ID
    current_owner_actor_id = Column(Integer, ForeignKey('actors.id'), nullable=False)
    approval_amount = Column(Float, nullable=True)  # Approved amount (may differ from requested)
    rejection_reason = Column(Text, nullable=True)
    blockchain_record_hash = Column(String(255), nullable=True)  # Hash of blockchain record
    created_by_actor_id = Column(Integer, ForeignKey('actors.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    customer = relationship("CustomerModel")
    created_by_actor = relationship("ActorModel", foreign_keys=[created_by_actor_id])
    current_owner_actor = relationship("ActorModel", foreign_keys=[current_owner_actor_id])
    loan_history = relationship("LoanApplicationHistoryModel", back_populates="loan_application")
    loan_documents = relationship("LoanDocumentModel", back_populates="loan_application")
    
    # Indexes
    __table_args__ = (
        Index('idx_loan_status_date', 'application_status', 'application_date'),
        Index('idx_loan_customer', 'customer_id'),
        Index('idx_loan_amount', 'requested_amount'),
        Index('idx_loan_type', 'loan_type'),
    )
    
    def __repr__(self):
        return f"<LoanApplicationModel(loan_application_id='{self.loan_application_id}', status='{self.application_status}')>"


class LoanApplicationHistoryModel(Base):
    """Loan application history model for tracking changes."""
    
    __tablename__ = "loan_application_history"
    
    id = Column(Integer, primary_key=True, index=True)
    loan_application_id = Column(Integer, ForeignKey('loan_applications.id'), nullable=False)
    change_type = Column(String(50), nullable=False)  # STATUS_CHANGE, UPDATE, APPROVAL, REJECTION
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=True)
    field_name = Column(String(100), nullable=True)  # Field that was changed
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by_actor_id = Column(Integer, ForeignKey('actors.id'), nullable=False)
    blockchain_transaction_id = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, nullable=True)  # Additional notes about the change
    
    # Relationships
    loan_application = relationship("LoanApplicationModel", back_populates="loan_history")
    changed_by_actor = relationship("ActorModel")
    
    # Indexes
    __table_args__ = (
        Index('idx_loan_history_loan', 'loan_application_id'),
        Index('idx_loan_history_timestamp', 'timestamp'),
        Index('idx_loan_history_status', 'new_status'),
    )
    
    def __repr__(self):
        return f"<LoanApplicationHistoryModel(loan_id={self.loan_application_id}, change_type='{self.change_type}')>"


class LoanDocumentModel(Base):
    """Loan document model for document management."""
    
    __tablename__ = "loan_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    loan_application_id = Column(Integer, ForeignKey('loan_applications.id'), nullable=False)
    document_type = Column(String(100), nullable=False)  # IDENTITY, INCOME_PROOF, BANK_STATEMENT, etc.
    document_name = Column(String(255), nullable=False)
    document_hash = Column(String(255), nullable=False)  # SHA256 hash for integrity
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    storage_path = Column(String(500), nullable=True)  # Path to stored file
    verification_status = Column(String(50), nullable=False, default='PENDING')  # PENDING, VERIFIED, FAILED
    uploaded_by_actor_id = Column(Integer, ForeignKey('actors.id'), nullable=False)
    blockchain_record_hash = Column(String(255), nullable=True)  # Hash of blockchain record
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    loan_application = relationship("LoanApplicationModel", back_populates="loan_documents")
    uploaded_by_actor = relationship("ActorModel")
    
    # Indexes
    __table_args__ = (
        Index('idx_document_loan', 'loan_application_id'),
        Index('idx_document_type', 'document_type'),
        Index('idx_document_hash', 'document_hash'),
        Index('idx_document_verification', 'verification_status'),
    )
    
    def __repr__(self):
        return f"<LoanDocumentModel(loan_id={self.loan_application_id}, type='{self.document_type}')>"


class ComplianceEventModel(Base):
    """Compliance event model for regulatory tracking."""
    
    __tablename__ = "compliance_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(255), unique=True, index=True, nullable=False)
    event_type = Column(String(100), nullable=False)  # RULE_VIOLATION, AML_CHECK, KYC_VERIFICATION, etc.
    rule_id = Column(String(255), nullable=True)  # Reference to compliance rule
    affected_entity_type = Column(String(50), nullable=False)  # CUSTOMER, LOAN_APPLICATION, ACTOR
    affected_entity_id = Column(String(255), nullable=False)  # ID of affected entity
    severity = Column(String(20), nullable=False, default='INFO')  # INFO, WARNING, ERROR, CRITICAL
    description = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)  # Additional event details
    is_alerted = Column(Boolean, default=False, nullable=False)
    acknowledged_by_actor_id = Column(Integer, ForeignKey('actors.id'), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolution_status = Column(String(50), nullable=False, default='OPEN')  # OPEN, IN_PROGRESS, RESOLVED, CLOSED
    resolution_notes = Column(Text, nullable=True)
    actor_id = Column(Integer, ForeignKey('actors.id'), nullable=False)  # Actor who triggered the event
    blockchain_transaction_id = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    actor = relationship("ActorModel", foreign_keys=[actor_id])
    acknowledged_by_actor = relationship("ActorModel", foreign_keys=[acknowledged_by_actor_id])
    
    # Indexes
    __table_args__ = (
        Index('idx_compliance_event_type', 'event_type'),
        Index('idx_compliance_entity', 'affected_entity_type', 'affected_entity_id'),
        Index('idx_compliance_severity', 'severity'),
        Index('idx_compliance_timestamp', 'timestamp'),
        Index('idx_compliance_resolution', 'resolution_status'),
    )
    
    def __repr__(self):
        return f"<ComplianceEventModel(event_id='{self.event_id}', type='{self.event_type}')>"


class DatabaseManager:
    """Database connection and session management."""
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize database manager."""
        self.database_url = database_url or settings.DATABASE_URL
        self.engine = None
        self.SessionLocal = None
        self._setup_database()
    
    def _setup_database(self):
        """Setup database engine and session factory."""
        try:
            # Create engine with connection pooling
            if "sqlite" in self.database_url:
                # SQLite specific configuration
                self.engine = create_engine(
                    self.database_url,
                    poolclass=StaticPool,
                    connect_args={"check_same_thread": False},
                    echo=False  # Set to True for SQL debugging
                )
            else:
                # PostgreSQL configuration
                self.engine = create_engine(
                    self.database_url,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    echo=False  # Set to True for SQL debugging
                )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            logger.info("Database connection established", database_url=self.database_url)
            
        except Exception as e:
            logger.error("Failed to setup database", error=str(e))
            raise
    
    def create_tables(self):
        """Create all database tables."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error("Failed to create database tables", error=str(e))
            raise
    
    def drop_tables(self):
        """Drop all database tables."""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error("Failed to drop database tables", error=str(e))
            raise
    
    def get_session(self) -> Session:
        """Get a new database session."""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")
        return self.SessionLocal()
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def health_check(self) -> bool:
        """Check database connection health."""
        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False


class DatabaseUtilities:
    """Utility functions for common database operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize database utilities."""
        self.db_manager = db_manager
    
    def get_actor_by_actor_id(self, actor_id: str) -> Optional[ActorModel]:
        """Get actor by actor_id."""
        with self.db_manager.session_scope() as session:
            actor = session.query(ActorModel).filter(
                ActorModel.actor_id == actor_id
            ).first()
            if actor:
                # Load all attributes to avoid lazy loading issues
                session.refresh(actor)
                # Detach from session
                session.expunge(actor)
            return actor
    
    def get_customer_by_customer_id(self, customer_id: str) -> Optional[CustomerModel]:
        """Get customer by customer_id."""
        with self.db_manager.session_scope() as session:
            customer = session.query(CustomerModel).filter(
                CustomerModel.customer_id == customer_id
            ).first()
            if customer:
                # Load all attributes to avoid lazy loading issues
                session.refresh(customer)
                # Detach from session
                session.expunge(customer)
            return customer
    
    def get_loan_by_loan_id(self, loan_application_id: str) -> Optional[LoanApplicationModel]:
        """Get loan application by loan_application_id."""
        with self.db_manager.session_scope() as session:
            loan = session.query(LoanApplicationModel).filter(
                LoanApplicationModel.loan_application_id == loan_application_id
            ).first()
            if loan:
                # Load all attributes to avoid lazy loading issues
                session.refresh(loan)
                # Load customer relationship
                if loan.customer:
                    session.refresh(loan.customer)
                # Detach from session
                session.expunge_all()
            return loan
    
    def get_compliance_events_by_entity(
        self, 
        entity_type: str, 
        entity_id: str,
        limit: int = 100
    ) -> List[ComplianceEventModel]:
        """Get compliance events for a specific entity."""
        with self.db_manager.session_scope() as session:
            events = session.query(ComplianceEventModel).filter(
                ComplianceEventModel.affected_entity_type == entity_type,
                ComplianceEventModel.affected_entity_id == entity_id
            ).order_by(ComplianceEventModel.timestamp.desc()).limit(limit).all()
            
            # Detach all events from session
            for event in events:
                session.refresh(event)
                session.expunge(event)
            return events
    
    def create_actor(self, actor_data: Dict[str, Any]) -> ActorModel:
        """Create a new actor."""
        with self.db_manager.session_scope() as session:
            actor = ActorModel(**actor_data)
            session.add(actor)
            session.flush()  # Get the ID
            session.refresh(actor)  # Refresh to get all attributes
            # Detach from session to avoid DetachedInstanceError
            session.expunge(actor)
            return actor
    
    def create_customer(self, customer_data: Dict[str, Any]) -> CustomerModel:
        """Create a new customer."""
        with self.db_manager.session_scope() as session:
            customer = CustomerModel(**customer_data)
            session.add(customer)
            session.flush()  # Get the ID
            session.refresh(customer)  # Refresh to get all attributes
            # Detach from session to avoid DetachedInstanceError
            session.expunge(customer)
            return customer
    
    def create_loan_application(self, loan_data: Dict[str, Any]) -> LoanApplicationModel:
        """Create a new loan application."""
        with self.db_manager.session_scope() as session:
            loan = LoanApplicationModel(**loan_data)
            session.add(loan)
            session.flush()  # Get the ID
            session.refresh(loan)  # Refresh to get all attributes
            
            # Create a detached copy with all the data we need
            loan_copy = LoanApplicationModel()
            for key, value in loan.__dict__.items():
                if not key.startswith('_'):
                    setattr(loan_copy, key, value)
            
            return loan_copy
    
    def create_compliance_event(self, event_data: Dict[str, Any]) -> ComplianceEventModel:
        """Create a new compliance event."""
        with self.db_manager.session_scope() as session:
            event = ComplianceEventModel(**event_data)
            session.add(event)
            session.flush()  # Get the ID
            session.refresh(event)  # Refresh to get all attributes
            # Detach from session to avoid DetachedInstanceError
            session.expunge(event)
            return event
    
    def update_loan_status(
        self, 
        loan_application_id: str, 
        new_status: str,
        changed_by_actor_id: int,
        notes: Optional[str] = None
    ) -> bool:
        """Update loan application status and create history record."""
        with self.db_manager.session_scope() as session:
            loan = session.query(LoanApplicationModel).filter(
                LoanApplicationModel.loan_application_id == loan_application_id
            ).first()
            
            if not loan:
                return False
            
            old_status = loan.application_status
            loan.application_status = new_status
            loan.updated_at = datetime.utcnow()
            
            # Create history record
            history = LoanApplicationHistoryModel(
                loan_application_id=loan.id,
                change_type='STATUS_CHANGE',
                previous_status=old_status,
                new_status=new_status,
                changed_by_actor_id=changed_by_actor_id,
                notes=notes
            )
            session.add(history)
            
            return True
    
    def get_loan_history(self, loan_application_id: str) -> List[LoanApplicationHistoryModel]:
        """Get loan application history."""
        with self.db_manager.session_scope() as session:
            loan = session.query(LoanApplicationModel).filter(
                LoanApplicationModel.loan_application_id == loan_application_id
            ).first()
            
            if not loan:
                return []
            
            history = session.query(LoanApplicationHistoryModel).filter(
                LoanApplicationHistoryModel.loan_application_id == loan.id
            ).order_by(LoanApplicationHistoryModel.timestamp.desc()).all()
            
            # Detach all history records from session
            for record in history:
                session.refresh(record)
                session.expunge(record)
            return history
    
    def get_customer_history(self, customer_id: str) -> List[CustomerHistoryModel]:
        """Get customer history."""
        with self.db_manager.session_scope() as session:
            customer = session.query(CustomerModel).filter(
                CustomerModel.customer_id == customer_id
            ).first()
            
            if not customer:
                return []
            
            history = session.query(CustomerHistoryModel).filter(
                CustomerHistoryModel.customer_id == customer.id
            ).order_by(CustomerHistoryModel.timestamp.desc()).all()
            
            # Detach all history records from session
            for record in history:
                session.refresh(record)
                session.expunge(record)
            return history


# Global database manager instance
db_manager = DatabaseManager()
db_utils = DatabaseUtilities(db_manager)


def get_database() -> DatabaseManager:
    """Get the global database manager instance."""
    return db_manager


def get_db_session() -> Session:
    """Dependency to get database session for FastAPI."""
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def init_database():
    """Initialize database tables."""
    db_manager.create_tables()


def cleanup_database():
    """Cleanup database resources."""
    if db_manager.engine:
        db_manager.engine.dispose()