"""
Blockchain event listener service for synchronizing blockchain events with database.

This service listens to events from Customer, Loan, and Compliance chaincodes
and updates the operational database accordingly.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from shared.fabric_gateway import get_fabric_gateway, FabricError
from shared.database import (
    db_manager, db_utils, 
    CustomerModel, LoanApplicationModel, ComplianceEventModel,
    CustomerHistoryModel, LoanApplicationHistoryModel, LoanDocumentModel,
    ActorModel
)
from shared.config import settings

logger = structlog.get_logger(__name__)


class EventType(Enum):
    """Supported blockchain event types."""
    # Customer events
    CUSTOMER_CREATED = "CustomerCreated"
    CUSTOMER_UPDATED = "CustomerUpdated"
    CONSENT_RECORDED = "ConsentRecorded"
    CONSENT_UPDATED = "ConsentUpdated"
    KYC_VALIDATION_COMPLETED = "KYCValidationCompleted"
    AML_CHECK_COMPLETED = "AMLCheckCompleted"
    
    # Loan events
    LOAN_APPLICATION_SUBMITTED = "LoanApplicationSubmitted"
    LOAN_APPLICATION_STATUS_UPDATED = "LoanApplicationStatusUpdated"
    LOAN_APPLICATION_APPROVED = "LoanApplicationApproved"
    LOAN_APPLICATION_REJECTED = "LoanApplicationRejected"
    LOAN_HISTORY_ACCESSED = "LoanHistoryAccessed"
    DOCUMENT_HASH_RECORDED = "DocumentHashRecorded"
    DOCUMENT_HASH_VERIFIED = "DocumentHashVerified"
    LOAN_DOCUMENTS_ACCESSED = "LoanDocumentsAccessed"
    DOCUMENT_STATUS_UPDATED = "DocumentStatusUpdated"
    
    # Compliance events
    COMPLIANCE_RULE_UPDATED = "ComplianceRuleUpdated"
    COMPLIANCE_EVENT_RECORDED = "ComplianceEventRecorded"
    SANCTION_LIST_ENTRY_ADDED = "SanctionListEntryAdded"
    SANCTION_SCREENING_COMPLETED = "SanctionScreeningCompleted"


@dataclass
class BlockchainEvent:
    """Represents a blockchain event with parsed data."""
    event_type: EventType
    chaincode_name: str
    transaction_id: str
    block_number: int
    timestamp: datetime
    payload: Dict[str, Any]
    raw_event: Dict[str, Any]


class EventParsingError(Exception):
    """Raised when event parsing fails."""
    pass


class EventProcessor:
    """Processes blockchain events and updates database."""
    
    def __init__(self):
        self.event_handlers: Dict[EventType, Callable] = {
            # Customer event handlers
            EventType.CUSTOMER_CREATED: self._handle_customer_created,
            EventType.CUSTOMER_UPDATED: self._handle_customer_updated,
            EventType.CONSENT_RECORDED: self._handle_consent_recorded,
            EventType.CONSENT_UPDATED: self._handle_consent_updated,
            EventType.KYC_VALIDATION_COMPLETED: self._handle_kyc_validation_completed,
            EventType.AML_CHECK_COMPLETED: self._handle_aml_check_completed,
            
            # Loan event handlers
            EventType.LOAN_APPLICATION_SUBMITTED: self._handle_loan_application_submitted,
            EventType.LOAN_APPLICATION_STATUS_UPDATED: self._handle_loan_application_status_updated,
            EventType.LOAN_APPLICATION_APPROVED: self._handle_loan_application_approved,
            EventType.LOAN_APPLICATION_REJECTED: self._handle_loan_application_rejected,
            EventType.DOCUMENT_HASH_RECORDED: self._handle_document_hash_recorded,
            EventType.DOCUMENT_HASH_VERIFIED: self._handle_document_hash_verified,
            EventType.DOCUMENT_STATUS_UPDATED: self._handle_document_status_updated,
            
            # Compliance event handlers
            EventType.COMPLIANCE_RULE_UPDATED: self._handle_compliance_rule_updated,
            EventType.COMPLIANCE_EVENT_RECORDED: self._handle_compliance_event_recorded,
            EventType.SANCTION_LIST_ENTRY_ADDED: self._handle_sanction_list_entry_added,
            EventType.SANCTION_SCREENING_COMPLETED: self._handle_sanction_screening_completed,
        }
    
    async def process_event(self, event: BlockchainEvent) -> bool:
        """
        Process a blockchain event and update database.
        
        Args:
            event: The blockchain event to process
            
        Returns:
            True if event was processed successfully, False otherwise
        """
        try:
            handler = self.event_handlers.get(event.event_type)
            if not handler:
                logger.warning("No handler for event type", event_type=event.event_type.value)
                return False
            
            logger.info("Processing blockchain event",
                       event_type=event.event_type.value,
                       transaction_id=event.transaction_id,
                       chaincode=event.chaincode_name)
            
            await handler(event)
            
            logger.info("Successfully processed blockchain event",
                       event_type=event.event_type.value,
                       transaction_id=event.transaction_id)
            
            return True
            
        except Exception as e:
            logger.error("Failed to process blockchain event",
                        event_type=event.event_type.value,
                        transaction_id=event.transaction_id,
                        error=str(e))
            return False
    
    # Customer event handlers
    async def _handle_customer_created(self, event: BlockchainEvent):
        """Handle customer creation event."""
        payload = event.payload
        
        # Get or create actor
        actor = await self._get_or_create_actor(payload.get('actorID'))
        
        customer_data = {
            'customer_id': payload.get('customerID'),
            'first_name': payload.get('firstName', ''),
            'last_name': payload.get('lastName', ''),
            'date_of_birth': self._parse_datetime(payload.get('dateOfBirth')),
            'national_id_hash': payload.get('nationalID'),
            'address': payload.get('address'),
            'contact_email': payload.get('contactEmail'),
            'contact_phone': payload.get('contactPhone'),
            'kyc_status': payload.get('kycStatus', 'PENDING'),
            'aml_status': payload.get('amlStatus', 'PENDING'),
            'consent_preferences': payload.get('consentPreferences'),
            'created_by_actor_id': actor.id,
            'created_at': event.timestamp
        }
        
        customer = db_utils.create_customer(customer_data)
        
        # Create history record
        # Convert datetime objects to strings for JSON serialization
        customer_data_serializable = {k: v.isoformat() if isinstance(v, datetime) else v 
                                     for k, v in customer_data.items()}
        
        history_data = {
            'customer_id': customer.id,
            'change_type': 'CREATE',
            'new_value': json.dumps(customer_data_serializable),
            'changed_by_actor_id': actor.id,
            'blockchain_transaction_id': event.transaction_id,
            'timestamp': event.timestamp
        }
        
        with db_manager.session_scope() as session:
            history = CustomerHistoryModel(**history_data)
            session.add(history)
    
    async def _handle_customer_updated(self, event: BlockchainEvent):
        """Handle customer update event."""
        payload = event.payload
        customer_id = payload.get('customerID')
        
        # Get or create actor
        actor = await self._get_or_create_actor(payload.get('actorID'))
        
        with db_manager.session_scope() as session:
            customer = session.query(CustomerModel).filter(
                CustomerModel.customer_id == customer_id
            ).first()
            
            if not customer:
                logger.warning("Customer not found for update", customer_id=customer_id)
                return
            
            # Update customer fields
            old_values = {}
            new_values = {}
            
            update_fields = ['firstName', 'lastName', 'address', 'contactEmail', 
                           'contactPhone', 'kycStatus', 'amlStatus']
            
            for field in update_fields:
                if field in payload:
                    db_field = self._camel_to_snake(field)
                    old_value = getattr(customer, db_field)
                    new_value = payload[field]
                    
                    if old_value != new_value:
                        old_values[db_field] = old_value
                        new_values[db_field] = new_value
                        setattr(customer, db_field, new_value)
            
            customer.updated_at = event.timestamp
            
            # Create history record for each changed field
            for field, old_value in old_values.items():
                history = CustomerHistoryModel(
                    customer_id=customer.id,
                    change_type='UPDATE',
                    field_name=field,
                    old_value=str(old_value) if old_value else None,
                    new_value=str(new_values[field]) if new_values[field] else None,
                    changed_by_actor_id=actor.id,
                    blockchain_transaction_id=event.transaction_id,
                    timestamp=event.timestamp
                )
                session.add(history)
    
    async def _handle_consent_recorded(self, event: BlockchainEvent):
        """Handle consent recording event."""
        await self._handle_consent_event(event, 'CONSENT_RECORDED')
    
    async def _handle_consent_updated(self, event: BlockchainEvent):
        """Handle consent update event."""
        await self._handle_consent_event(event, 'CONSENT_UPDATED')
    
    async def _handle_consent_event(self, event: BlockchainEvent, change_type: str):
        """Handle consent-related events."""
        payload = event.payload
        customer_id = payload.get('customerID')
        
        # Get or create actor
        actor = await self._get_or_create_actor(payload.get('actorID'))
        
        with db_manager.session_scope() as session:
            customer = session.query(CustomerModel).filter(
                CustomerModel.customer_id == customer_id
            ).first()
            
            if not customer:
                logger.warning("Customer not found for consent event", customer_id=customer_id)
                return
            
            # Update consent preferences
            old_consent = customer.consent_preferences
            new_consent = payload.get('consentPreferences')
            
            customer.consent_preferences = new_consent
            customer.updated_at = event.timestamp
            
            # Create history record
            history = CustomerHistoryModel(
                customer_id=customer.id,
                change_type=change_type,
                field_name='consent_preferences',
                old_value=json.dumps(old_consent) if old_consent else None,
                new_value=json.dumps(new_consent) if new_consent else None,
                changed_by_actor_id=actor.id,
                blockchain_transaction_id=event.transaction_id,
                timestamp=event.timestamp
            )
            session.add(history)
    
    async def _handle_kyc_validation_completed(self, event: BlockchainEvent):
        """Handle KYC validation completion event."""
        await self._handle_validation_event(event, 'kyc_status', 'KYC_VALIDATION')
    
    async def _handle_aml_check_completed(self, event: BlockchainEvent):
        """Handle AML check completion event."""
        await self._handle_validation_event(event, 'aml_status', 'AML_CHECK')
    
    async def _handle_validation_event(self, event: BlockchainEvent, status_field: str, change_type: str):
        """Handle validation events (KYC/AML)."""
        payload = event.payload
        customer_id = payload.get('customerID')
        
        # Get or create actor
        actor = await self._get_or_create_actor(payload.get('actorID'))
        
        with db_manager.session_scope() as session:
            customer = session.query(CustomerModel).filter(
                CustomerModel.customer_id == customer_id
            ).first()
            
            if not customer:
                logger.warning("Customer not found for validation event", customer_id=customer_id)
                return
            
            # Update status
            old_status = getattr(customer, status_field)
            new_status = payload.get('validationStatus') or payload.get('status')
            
            setattr(customer, status_field, new_status)
            customer.updated_at = event.timestamp
            
            # Create history record
            history = CustomerHistoryModel(
                customer_id=customer.id,
                change_type=change_type,
                field_name=status_field,
                old_value=old_status,
                new_value=new_status,
                changed_by_actor_id=actor.id,
                blockchain_transaction_id=event.transaction_id,
                timestamp=event.timestamp
            )
            session.add(history)
    
    # Loan event handlers
    async def _handle_loan_application_submitted(self, event: BlockchainEvent):
        """Handle loan application submission event."""
        payload = event.payload
        
        # Get or create actor
        actor = await self._get_or_create_actor(payload.get('actorID'))
        
        # Get customer
        customer = db_utils.get_customer_by_customer_id(payload.get('customerID'))
        if not customer:
            logger.warning("Customer not found for loan application", 
                          customer_id=payload.get('customerID'))
            return
        
        loan_data = {
            'loan_application_id': payload.get('loanApplicationID'),
            'customer_id': customer.id,
            'application_date': self._parse_datetime(payload.get('applicationDate')) or event.timestamp,
            'requested_amount': float(payload.get('requestedAmount', 0)),
            'loan_type': payload.get('loanType'),
            'application_status': payload.get('applicationStatus', 'SUBMITTED'),
            'introducer_id': payload.get('introducerID'),
            'current_owner_actor_id': actor.id,
            'created_by_actor_id': actor.id,
            'created_at': event.timestamp
        }
        
        loan = db_utils.create_loan_application(loan_data)
        
        # Create history record
        with db_manager.session_scope() as session:
            history = LoanApplicationHistoryModel(
                loan_application_id=loan.id,
                change_type='CREATE',
                new_status='SUBMITTED',
                changed_by_actor_id=actor.id,
                blockchain_transaction_id=event.transaction_id,
                timestamp=event.timestamp,
                notes='Loan application submitted'
            )
            session.add(history)
    
    async def _handle_loan_application_status_updated(self, event: BlockchainEvent):
        """Handle loan application status update event."""
        payload = event.payload
        loan_id = payload.get('loanApplicationID')
        
        # Get or create actor
        actor = await self._get_or_create_actor(payload.get('actorID'))
        
        with db_manager.session_scope() as session:
            loan = session.query(LoanApplicationModel).filter(
                LoanApplicationModel.loan_application_id == loan_id
            ).first()
            
            if not loan:
                logger.warning("Loan application not found for status update", loan_id=loan_id)
                return
            
            old_status = loan.application_status
            new_status = payload.get('newStatus')
            
            loan.application_status = new_status
            loan.updated_at = event.timestamp
            
            # Create history record
            history = LoanApplicationHistoryModel(
                loan_application_id=loan.id,
                change_type='STATUS_CHANGE',
                previous_status=old_status,
                new_status=new_status,
                changed_by_actor_id=actor.id,
                blockchain_transaction_id=event.transaction_id,
                timestamp=event.timestamp
            )
            session.add(history)
    
    async def _handle_loan_application_approved(self, event: BlockchainEvent):
        """Handle loan application approval event."""
        payload = event.payload
        loan_id = payload.get('loanApplicationID')
        
        # Get or create actor
        actor = await self._get_or_create_actor(payload.get('approvedBy'))
        
        with db_manager.session_scope() as session:
            loan = session.query(LoanApplicationModel).filter(
                LoanApplicationModel.loan_application_id == loan_id
            ).first()
            
            if not loan:
                logger.warning("Loan application not found for approval", loan_id=loan_id)
                return
            
            old_status = loan.application_status
            loan.application_status = 'APPROVED'
            loan.approval_amount = float(payload.get('approvedAmount', 0))
            loan.updated_at = event.timestamp
            
            # Create history record
            history = LoanApplicationHistoryModel(
                loan_application_id=loan.id,
                change_type='APPROVAL',
                previous_status=old_status,
                new_status='APPROVED',
                changed_by_actor_id=actor.id,
                blockchain_transaction_id=event.transaction_id,
                timestamp=event.timestamp,
                notes=f"Approved amount: {loan.approval_amount}"
            )
            session.add(history)
    
    async def _handle_loan_application_rejected(self, event: BlockchainEvent):
        """Handle loan application rejection event."""
        payload = event.payload
        loan_id = payload.get('loanApplicationID')
        
        # Get or create actor
        actor = await self._get_or_create_actor(payload.get('rejectedBy'))
        
        with db_manager.session_scope() as session:
            loan = session.query(LoanApplicationModel).filter(
                LoanApplicationModel.loan_application_id == loan_id
            ).first()
            
            if not loan:
                logger.warning("Loan application not found for rejection", loan_id=loan_id)
                return
            
            old_status = loan.application_status
            loan.application_status = 'REJECTED'
            loan.rejection_reason = payload.get('rejectionReason')
            loan.updated_at = event.timestamp
            
            # Create history record
            history = LoanApplicationHistoryModel(
                loan_application_id=loan.id,
                change_type='REJECTION',
                previous_status=old_status,
                new_status='REJECTED',
                changed_by_actor_id=actor.id,
                blockchain_transaction_id=event.transaction_id,
                timestamp=event.timestamp,
                notes=loan.rejection_reason
            )
            session.add(history)
    
    async def _handle_document_hash_recorded(self, event: BlockchainEvent):
        """Handle document hash recording event."""
        payload = event.payload
        
        # Get or create actor
        actor = await self._get_or_create_actor(payload.get('uploadedBy'))
        
        # Get loan application
        loan = db_utils.get_loan_by_loan_id(payload.get('loanApplicationID'))
        if not loan:
            logger.warning("Loan application not found for document", 
                          loan_id=payload.get('loanApplicationID'))
            return
        
        document_data = {
            'loan_application_id': loan.id,
            'document_type': payload.get('documentType'),
            'document_name': payload.get('documentName'),
            'document_hash': payload.get('documentHash'),
            'file_size': payload.get('fileSize'),
            'mime_type': payload.get('mimeType'),
            'verification_status': 'PENDING',
            'uploaded_by_actor_id': actor.id,
            'created_at': event.timestamp
        }
        
        db_utils.create_loan_document(document_data)
    
    async def _handle_document_hash_verified(self, event: BlockchainEvent):
        """Handle document hash verification event."""
        payload = event.payload
        document_hash = payload.get('documentHash')
        verification_status = payload.get('verificationStatus')
        
        with db_manager.session_scope() as session:
            document = session.query(LoanDocumentModel).filter(
                LoanDocumentModel.document_hash == document_hash
            ).first()
            
            if not document:
                logger.warning("Document not found for verification", document_hash=document_hash)
                return
            
            document.verification_status = verification_status
            document.updated_at = event.timestamp
    
    async def _handle_document_status_updated(self, event: BlockchainEvent):
        """Handle document status update event."""
        payload = event.payload
        document_hash = payload.get('documentHash')
        new_status = payload.get('newStatus')
        
        with db_manager.session_scope() as session:
            document = session.query(LoanDocumentModel).filter(
                LoanDocumentModel.document_hash == document_hash
            ).first()
            
            if not document:
                logger.warning("Document not found for status update", document_hash=document_hash)
                return
            
            document.verification_status = new_status
            document.updated_at = event.timestamp
    
    # Compliance event handlers
    async def _handle_compliance_rule_updated(self, event: BlockchainEvent):
        """Handle compliance rule update event."""
        # This is primarily for audit purposes - rules are managed in chaincode
        await self._create_compliance_event_record(event, 'RULE_UPDATE')
    
    async def _handle_compliance_event_recorded(self, event: BlockchainEvent):
        """Handle compliance event recording."""
        await self._create_compliance_event_record(event, 'COMPLIANCE_CHECK')
    
    async def _handle_sanction_list_entry_added(self, event: BlockchainEvent):
        """Handle sanction list entry addition."""
        await self._create_compliance_event_record(event, 'SANCTION_LIST_UPDATE')
    
    async def _handle_sanction_screening_completed(self, event: BlockchainEvent):
        """Handle sanction screening completion."""
        await self._create_compliance_event_record(event, 'SANCTION_SCREENING')
    
    async def _create_compliance_event_record(self, event: BlockchainEvent, event_type: str):
        """Create a compliance event record in the database."""
        payload = event.payload
        
        # Get or create actor
        actor = await self._get_or_create_actor(payload.get('actorID'))
        
        event_data = {
            'event_id': payload.get('eventID') or f"{event.transaction_id}_{event_type}",
            'event_type': event_type,
            'rule_id': payload.get('ruleID'),
            'affected_entity_type': payload.get('affectedEntityType', 'UNKNOWN'),
            'affected_entity_id': payload.get('affectedEntityID', ''),
            'severity': payload.get('severity', 'INFO'),
            'description': payload.get('details', event.event_type.value),
            'details': payload,
            'is_alerted': payload.get('isAlerted', False),
            'actor_id': actor.id,
            'blockchain_transaction_id': event.transaction_id,
            'timestamp': event.timestamp
        }
        
        db_utils.create_compliance_event(event_data)
    
    # Utility methods
    async def _get_or_create_actor(self, actor_id: str) -> ActorModel:
        """Get or create an actor by actor_id."""
        if not actor_id:
            # Create a system actor for events without actor info
            actor_id = "SYSTEM"
        
        actor = db_utils.get_actor_by_actor_id(actor_id)
        if not actor:
            # Create a new actor with minimal information
            actor_data = {
                'actor_id': actor_id,
                'actor_type': 'System' if actor_id == 'SYSTEM' else 'Unknown',
                'actor_name': actor_id,
                'role': 'System' if actor_id == 'SYSTEM' else 'Unknown',
                'is_active': True
            }
            actor = db_utils.create_actor(actor_data)
        
        return actor
    
    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object."""
        if not date_str:
            return None
        
        try:
            # Try different datetime formats
            formats = [
                '%Y-%m-%dT%H:%M:%S.%fZ',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            logger.warning("Could not parse datetime", date_str=date_str)
            return None
            
        except Exception as e:
            logger.error("Error parsing datetime", date_str=date_str, error=str(e))
            return None
    
    def _camel_to_snake(self, camel_str: str) -> str:
        """Convert camelCase to snake_case."""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_str)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class EventParser:
    """Parses raw blockchain events into structured BlockchainEvent objects."""
    
    def parse_event(self, raw_event: Dict[str, Any]) -> Optional[BlockchainEvent]:
        """
        Parse a raw blockchain event into a structured BlockchainEvent.
        
        Args:
            raw_event: Raw event data from Fabric
            
        Returns:
            Parsed BlockchainEvent or None if parsing fails
        """
        try:
            event_name = raw_event.get('eventName', '')
            
            # Map event name to EventType
            try:
                event_type = EventType(event_name)
            except ValueError:
                logger.warning("Unknown event type", event_name=event_name)
                return None
            
            # Parse payload
            payload_bytes = raw_event.get('payload', b'')
            if isinstance(payload_bytes, bytes):
                payload = json.loads(payload_bytes.decode('utf-8'))
            elif isinstance(payload_bytes, str):
                payload = json.loads(payload_bytes)
            else:
                payload = payload_bytes or {}
            
            # Extract metadata
            chaincode_name = raw_event.get('chaincodeId', '')
            transaction_id = raw_event.get('txId', '')
            block_number = raw_event.get('blockNumber', 0)
            
            # Parse timestamp
            timestamp_str = raw_event.get('timestamp')
            if timestamp_str:
                timestamp = self._parse_timestamp(timestamp_str)
            else:
                timestamp = datetime.utcnow()
            
            return BlockchainEvent(
                event_type=event_type,
                chaincode_name=chaincode_name,
                transaction_id=transaction_id,
                block_number=block_number,
                timestamp=timestamp,
                payload=payload,
                raw_event=raw_event
            )
            
        except Exception as e:
            logger.error("Failed to parse blockchain event", error=str(e), raw_event=raw_event)
            raise EventParsingError(f"Failed to parse event: {e}")
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime."""
        try:
            # Handle different timestamp formats
            if timestamp_str.endswith('Z'):
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                return datetime.fromisoformat(timestamp_str)
        except Exception:
            logger.warning("Could not parse timestamp, using current time", timestamp=timestamp_str)
            return datetime.utcnow()


class EventListenerService:
    """Service for listening to blockchain events and updating database."""
    
    def __init__(self):
        self.running = False
        self.event_processor = EventProcessor()
        self.event_parser = EventParser()
        self.chaincodes = ['customer', 'loan', 'compliance']
        self.event_subscriptions: Dict[str, Any] = {}
        self.processed_events: set = set()  # Track processed events to avoid duplicates
    
    async def start(self):
        """Start the event listener service."""
        self.running = True
        logger.info("Event listener service starting")
        
        try:
            # Start event subscriptions for each chaincode
            tasks = []
            for chaincode in self.chaincodes:
                task = asyncio.create_task(self._subscribe_to_chaincode_events(chaincode))
                tasks.append(task)
            
            logger.info("Event listener service started", chaincodes=self.chaincodes)
            
            # Wait for all subscription tasks
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error("Error starting event listener service", error=str(e))
            raise
    
    async def stop(self):
        """Stop the event listener service."""
        self.running = False
        logger.info("Event listener service stopping")
        
        # Cancel all subscriptions
        for subscription in self.event_subscriptions.values():
            if hasattr(subscription, 'cancel'):
                subscription.cancel()
        
        self.event_subscriptions.clear()
        logger.info("Event listener service stopped")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(FabricError)
    )
    async def _subscribe_to_chaincode_events(self, chaincode_name: str):
        """Subscribe to events from a specific chaincode."""
        logger.info("Starting event subscription", chaincode=chaincode_name)
        
        try:
            gateway = await get_fabric_gateway()
            
            # Note: This is a placeholder for actual Fabric event subscription
            # In a real implementation, you would use the Fabric SDK to:
            # 1. Create an event listener for the chaincode
            # 2. Register event handlers
            # 3. Start listening for events
            
            while self.running:
                try:
                    # Simulate event listening - in real implementation this would be
                    # replaced with actual Fabric event subscription
                    await self._simulate_event_listening(chaincode_name)
                    await asyncio.sleep(5)  # Poll interval
                    
                except Exception as e:
                    logger.error("Error in event subscription", 
                               chaincode=chaincode_name, error=str(e))
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error("Failed to subscribe to chaincode events", 
                        chaincode=chaincode_name, error=str(e))
            raise
    
    async def _simulate_event_listening(self, chaincode_name: str):
        """
        Simulate event listening for development/testing.
        
        In production, this would be replaced with actual Fabric event subscription.
        """
        # This is a placeholder that would be replaced with real event listening
        # For now, we just log that we're listening
        logger.debug("Listening for events", chaincode=chaincode_name)
    
    async def process_raw_event(self, raw_event: Dict[str, Any]) -> bool:
        """
        Process a raw blockchain event.
        
        This method can be called directly for testing or when events
        are received from external sources.
        
        Args:
            raw_event: Raw event data from blockchain
            
        Returns:
            True if event was processed successfully
        """
        try:
            # Parse the event
            event = self.event_parser.parse_event(raw_event)
            if not event:
                return False
            
            # Check for duplicates
            event_key = f"{event.transaction_id}_{event.event_type.value}"
            if event_key in self.processed_events:
                logger.debug("Skipping duplicate event", event_key=event_key)
                return True
            
            # Process the event
            success = await self.event_processor.process_event(event)
            
            if success:
                self.processed_events.add(event_key)
                # Limit the size of processed events set
                if len(self.processed_events) > 10000:
                    # Remove oldest 1000 entries
                    old_events = list(self.processed_events)[:1000]
                    for old_event in old_events:
                        self.processed_events.discard(old_event)
            
            return success
            
        except EventParsingError as e:
            logger.error("Event parsing failed", error=str(e))
            return False
        except Exception as e:
            logger.error("Unexpected error processing event", error=str(e))
            return False
    
    def get_supported_event_types(self) -> List[str]:
        """Get list of supported event types."""
        return [event_type.value for event_type in EventType]
    
    def get_subscription_status(self) -> Dict[str, bool]:
        """Get status of chaincode subscriptions."""
        return {
            chaincode: chaincode in self.event_subscriptions 
            for chaincode in self.chaincodes
        }


# Global service instance
event_listener = EventListenerService()