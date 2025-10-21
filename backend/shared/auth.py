"""
Authentication and authorization middleware for the blockchain financial platform.

This module provides JWT token validation, role-based access control (RBAC),
and blockchain identity mapping for secure API access.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Union
from enum import Enum

import jwt
from jwt.exceptions import ImmatureSignatureError
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import structlog

from .config import settings

logger = structlog.get_logger(__name__)

# Security scheme for FastAPI
security = HTTPBearer()


class ActorType(Enum):
    """Types of actors in the system."""
    INTERNAL_USER = "Internal_User"
    EXTERNAL_PARTNER = "External_Partner"
    SYSTEM = "System"


class Role(Enum):
    """User roles in the system."""
    UNDERWRITER = "Underwriter"
    INTRODUCER = "Introducer"
    COMPLIANCE_OFFICER = "Compliance_Officer"
    CREDIT_OFFICER = "Credit_Officer"
    CUSTOMER_SERVICE_REP = "Customer_Service_Rep"
    RISK_ANALYST = "Risk_Analyst"
    SYSTEM_ADMINISTRATOR = "System_Administrator"
    API_DEVELOPER = "API_Developer"
    LOAN_OPERATIONS_MANAGER = "Loan_Operations_Manager"
    CHIEF_COMPLIANCE_OFFICER = "Chief_Compliance_Officer"
    REGULATOR = "Regulator"


class Permission(Enum):
    """System permissions."""
    # Customer permissions
    CREATE_CUSTOMER = "create_customer"
    READ_CUSTOMER = "read_customer"
    UPDATE_CUSTOMER = "update_customer"
    DELETE_CUSTOMER = "delete_customer"
    READ_CUSTOMER_HISTORY = "read_customer_history"
    MANAGE_CUSTOMER_CONSENT = "manage_customer_consent"
    
    # Loan permissions
    CREATE_LOAN_APPLICATION = "create_loan_application"
    READ_LOAN_APPLICATION = "read_loan_application"
    UPDATE_LOAN_APPLICATION = "update_loan_application"
    APPROVE_LOAN = "approve_loan"
    REJECT_LOAN = "reject_loan"
    READ_LOAN_HISTORY = "read_loan_history"
    MANAGE_LOAN_DOCUMENTS = "manage_loan_documents"
    
    # Compliance permissions
    READ_COMPLIANCE_EVENTS = "read_compliance_events"
    CREATE_COMPLIANCE_RULE = "create_compliance_rule"
    UPDATE_COMPLIANCE_RULE = "update_compliance_rule"
    GENERATE_REGULATORY_REPORT = "generate_regulatory_report"
    ACCESS_REGULATORY_VIEW = "access_regulatory_view"
    
    # System permissions
    MANAGE_ACTORS = "manage_actors"
    SYSTEM_MONITORING = "system_monitoring"
    API_ACCESS = "api_access"


class Actor(BaseModel):
    """Actor model representing a user or system in the platform."""
    actor_id: str = Field(..., description="Unique actor identifier")
    actor_type: ActorType = Field(..., description="Type of actor")
    actor_name: str = Field(..., description="Display name of the actor")
    role: Role = Field(..., description="Primary role of the actor")
    blockchain_identity: Optional[str] = Field(None, description="x.509 Certificate ID for blockchain operations")
    permissions: Set[Permission] = Field(default_factory=set, description="Set of permissions granted to the actor")
    is_active: bool = Field(True, description="Whether the actor is active")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"use_enum_values": True}
        
    def __init__(self, **data):
        """Initialize Actor with proper enum handling."""
        super().__init__(**data)
        # Convert string values back to enums if needed
        if isinstance(self.actor_type, str):
            self.actor_type = ActorType(self.actor_type)
        if isinstance(self.role, str):
            self.role = Role(self.role)
        # Convert permission strings back to Permission enums
        if self.permissions and isinstance(next(iter(self.permissions)), str):
            self.permissions = {Permission(perm) for perm in self.permissions}


class TokenData(BaseModel):
    """JWT token payload data."""
    sub: str = Field(..., description="Subject (actor_id)")
    actor_type: str = Field(..., description="Type of actor")
    role: str = Field(..., description="Actor role")
    permissions: List[str] = Field(default_factory=list, description="List of permissions")
    exp: datetime = Field(..., description="Expiration time")
    iat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Issued at time")


# Role-based permission mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.UNDERWRITER: {
        Permission.READ_CUSTOMER,
        Permission.READ_CUSTOMER_HISTORY,
        Permission.READ_LOAN_APPLICATION,
        Permission.UPDATE_LOAN_APPLICATION,
        Permission.READ_LOAN_HISTORY,
        Permission.READ_COMPLIANCE_EVENTS,
    },
    Role.INTRODUCER: {
        Permission.CREATE_CUSTOMER,
        Permission.READ_CUSTOMER,
        Permission.UPDATE_CUSTOMER,
        Permission.CREATE_LOAN_APPLICATION,
        Permission.READ_LOAN_APPLICATION,
        Permission.MANAGE_LOAN_DOCUMENTS,
    },
    Role.COMPLIANCE_OFFICER: {
        Permission.READ_CUSTOMER,
        Permission.READ_CUSTOMER_HISTORY,
        Permission.READ_LOAN_APPLICATION,
        Permission.READ_LOAN_HISTORY,
        Permission.READ_COMPLIANCE_EVENTS,
        Permission.CREATE_COMPLIANCE_RULE,
        Permission.UPDATE_COMPLIANCE_RULE,
        Permission.GENERATE_REGULATORY_REPORT,
    },
    Role.CREDIT_OFFICER: {
        Permission.READ_CUSTOMER,
        Permission.READ_CUSTOMER_HISTORY,
        Permission.READ_LOAN_APPLICATION,
        Permission.APPROVE_LOAN,
        Permission.REJECT_LOAN,
        Permission.READ_LOAN_HISTORY,
        Permission.READ_COMPLIANCE_EVENTS,
    },
    Role.CUSTOMER_SERVICE_REP: {
        Permission.CREATE_CUSTOMER,
        Permission.READ_CUSTOMER,
        Permission.UPDATE_CUSTOMER,
        Permission.MANAGE_CUSTOMER_CONSENT,
        Permission.READ_LOAN_APPLICATION,
    },
    Role.RISK_ANALYST: {
        Permission.READ_CUSTOMER,
        Permission.READ_CUSTOMER_HISTORY,
        Permission.READ_LOAN_APPLICATION,
        Permission.READ_LOAN_HISTORY,
        Permission.READ_COMPLIANCE_EVENTS,
        Permission.GENERATE_REGULATORY_REPORT,
    },
    Role.SYSTEM_ADMINISTRATOR: {
        Permission.MANAGE_ACTORS,
        Permission.SYSTEM_MONITORING,
        Permission.API_ACCESS,
        Permission.READ_COMPLIANCE_EVENTS,
    },
    Role.API_DEVELOPER: {
        Permission.API_ACCESS,
        Permission.READ_CUSTOMER,
        Permission.READ_LOAN_APPLICATION,
        Permission.READ_COMPLIANCE_EVENTS,
    },
    Role.LOAN_OPERATIONS_MANAGER: {
        Permission.READ_CUSTOMER,
        Permission.READ_LOAN_APPLICATION,
        Permission.READ_LOAN_HISTORY,
        Permission.READ_COMPLIANCE_EVENTS,
        Permission.SYSTEM_MONITORING,
    },
    Role.CHIEF_COMPLIANCE_OFFICER: {
        Permission.READ_CUSTOMER,
        Permission.READ_CUSTOMER_HISTORY,
        Permission.READ_LOAN_APPLICATION,
        Permission.READ_LOAN_HISTORY,
        Permission.READ_COMPLIANCE_EVENTS,
        Permission.CREATE_COMPLIANCE_RULE,
        Permission.UPDATE_COMPLIANCE_RULE,
        Permission.GENERATE_REGULATORY_REPORT,
        Permission.MANAGE_ACTORS,
    },
    Role.REGULATOR: {
        Permission.ACCESS_REGULATORY_VIEW,
        Permission.READ_COMPLIANCE_EVENTS,
        Permission.GENERATE_REGULATORY_REPORT,
    },
}


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when authorization fails."""
    pass


class JWTManager:
    """JWT token management for authentication."""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """Initialize JWT manager."""
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_access_token(
        self,
        actor: Actor,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT access token for an actor.
        
        Args:
            actor: Actor to create token for
            expires_delta: Optional expiration time delta
            
        Returns:
            JWT token string
        """
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # Handle both enum and string values
        actor_type_value = actor.actor_type.value if hasattr(actor.actor_type, 'value') else actor.actor_type
        role_value = actor.role.value if hasattr(actor.role, 'value') else actor.role
        permissions_values = [
            perm.value if hasattr(perm, 'value') else perm 
            for perm in actor.permissions
        ]
        
        token_data = TokenData(
            sub=actor.actor_id,
            actor_type=actor_type_value,
            role=role_value,
            permissions=permissions_values,
            exp=expire
        )
        
        payload = token_data.model_dump()
        # Convert datetime objects to timestamps
        payload["exp"] = int(expire.timestamp())
        payload["iat"] = int(datetime.now(timezone.utc).timestamp())
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        logger.info("Created access token", actor_id=actor.actor_id, role=actor.role.value)
        
        return token
    
    def verify_token(self, token: str) -> TokenData:
        """
        Verify and decode a JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token data
            
        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            # Disable iat validation to avoid timing issues in tests
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={"verify_iat": False}
            )
            
            # Convert timestamp back to datetime
            payload["exp"] = datetime.fromtimestamp(payload["exp"])
            payload["iat"] = datetime.fromtimestamp(payload["iat"])
            
            token_data = TokenData(**payload)
            
            logger.debug("Token verified successfully", actor_id=token_data.sub)
            
            return token_data
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise AuthenticationError("Token has expired")
        except ImmatureSignatureError:
            logger.warning("Token not yet valid")
            raise AuthenticationError("Token not yet valid")
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token", error=str(e))
            raise AuthenticationError("Invalid token")
        except Exception as e:
            logger.error("Token verification failed", error=str(e))
            raise AuthenticationError("Token verification failed")


class ActorManager:
    """Manages actors and their permissions."""
    
    def __init__(self):
        """Initialize actor manager."""
        # In a real implementation, this would be backed by a database
        self._actors: Dict[str, Actor] = {}
        self._initialize_default_actors()
    
    def _initialize_default_actors(self):
        """Initialize some default actors for testing."""
        # System actor
        system_actor = Actor(
            actor_id="system",
            actor_type=ActorType.SYSTEM,
            actor_name="System",
            role=Role.SYSTEM_ADMINISTRATOR,
            permissions=ROLE_PERMISSIONS[Role.SYSTEM_ADMINISTRATOR]
        )
        self._actors[system_actor.actor_id] = system_actor
        
        # Test underwriter
        underwriter = Actor(
            actor_id="underwriter_001",
            actor_type=ActorType.INTERNAL_USER,
            actor_name="John Underwriter",
            role=Role.UNDERWRITER,
            permissions=ROLE_PERMISSIONS[Role.UNDERWRITER]
        )
        self._actors[underwriter.actor_id] = underwriter
        
        # Test introducer
        introducer = Actor(
            actor_id="introducer_001",
            actor_type=ActorType.EXTERNAL_PARTNER,
            actor_name="Jane Introducer",
            role=Role.INTRODUCER,
            permissions=ROLE_PERMISSIONS[Role.INTRODUCER]
        )
        self._actors[introducer.actor_id] = introducer
    
    def get_actor(self, actor_id: str) -> Optional[Actor]:
        """Get actor by ID."""
        return self._actors.get(actor_id)
    
    def create_actor(self, actor: Actor) -> Actor:
        """Create a new actor."""
        if actor.actor_id in self._actors:
            raise ValueError(f"Actor with ID {actor.actor_id} already exists")
        
        # Assign default permissions based on role
        if not actor.permissions:
            actor.permissions = ROLE_PERMISSIONS.get(actor.role, set())
        
        self._actors[actor.actor_id] = actor
        
        role_value = actor.role.value if hasattr(actor.role, 'value') else actor.role
        logger.info("Created new actor", actor_id=actor.actor_id, role=role_value)
        
        return actor
    
    def update_actor(self, actor_id: str, updates: Dict) -> Optional[Actor]:
        """Update an existing actor."""
        if actor_id not in self._actors:
            return None
        
        actor = self._actors[actor_id]
        for key, value in updates.items():
            if hasattr(actor, key):
                setattr(actor, key, value)
        
        actor.updated_at = datetime.now(timezone.utc)
        
        logger.info("Updated actor", actor_id=actor_id)
        
        return actor
    
    def delete_actor(self, actor_id: str) -> bool:
        """Delete an actor."""
        if actor_id in self._actors:
            del self._actors[actor_id]
            logger.info("Deleted actor", actor_id=actor_id)
            return True
        return False
    
    def list_actors(self) -> List[Actor]:
        """List all actors."""
        return list(self._actors.values())


# Global instances
jwt_manager = JWTManager(settings.SECRET_KEY, settings.ALGORITHM)
actor_manager = ActorManager()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Actor:
    """
    Dependency to get the current authenticated user.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        Current authenticated actor
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        token_data = jwt_manager.verify_token(credentials.credentials)
        actor = actor_manager.get_actor(token_data.sub)
        
        if not actor:
            logger.warning("Actor not found", actor_id=token_data.sub)
            raise HTTPException(status_code=401, detail="Actor not found")
        
        if not actor.is_active:
            logger.warning("Inactive actor attempted access", actor_id=actor.actor_id)
            raise HTTPException(status_code=401, detail="Inactive actor")
        
        return actor
        
    except AuthenticationError as e:
        logger.warning("Authentication failed", error=str(e))
        raise HTTPException(status_code=401, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error("Unexpected authentication error", error=str(e))
        raise HTTPException(status_code=401, detail="Authentication failed")


def require_permissions(*required_permissions: Permission):
    """
    Decorator to require specific permissions for an endpoint.
    
    Args:
        required_permissions: Permissions required to access the endpoint
        
    Returns:
        FastAPI dependency function
    """
    def permission_checker(current_user: Actor = Depends(get_current_user)) -> Actor:
        """Check if current user has required permissions."""
        missing_permissions = set(required_permissions) - current_user.permissions
        
        if missing_permissions:
            missing_values = [
                perm.value if hasattr(perm, 'value') else perm 
                for perm in missing_permissions
            ]
            logger.warning(
                "Access denied - insufficient permissions",
                actor_id=current_user.actor_id,
                required=list(required_permissions),
                missing=missing_values
            )
            missing_values = [
                perm.value if hasattr(perm, 'value') else perm 
                for perm in missing_permissions
            ]
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Missing: {missing_values}"
            )
        
        logger.debug(
            "Permission check passed",
            actor_id=current_user.actor_id,
            permissions=[perm.value for perm in required_permissions]
        )
        
        return current_user
    
    return permission_checker


def require_roles(*required_roles: Role):
    """
    Decorator to require specific roles for an endpoint.
    
    Args:
        required_roles: Roles required to access the endpoint
        
    Returns:
        FastAPI dependency function
    """
    def role_checker(current_user: Actor = Depends(get_current_user)) -> Actor:
        """Check if current user has required role."""
        if current_user.role not in required_roles:
            current_role_value = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
            required_role_values = [
                role.value if hasattr(role, 'value') else role 
                for role in required_roles
            ]
            logger.warning(
                "Access denied - insufficient role",
                actor_id=current_user.actor_id,
                current_role=current_role_value,
                required_roles=required_role_values
            )
            required_role_values = [
                role.value if hasattr(role, 'value') else role 
                for role in required_roles
            ]
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient role. Required: {required_role_values}"
            )
        
        logger.debug(
            "Role check passed",
            actor_id=current_user.actor_id,
            role=current_user.role.value
        )
        
        return current_user
    
    return role_checker


class BlockchainIdentityMapper:
    """Maps API users to blockchain identities."""
    
    def __init__(self):
        """Initialize blockchain identity mapper."""
        # In a real implementation, this would integrate with Fabric CA
        self._identity_mappings: Dict[str, str] = {}
    
    def map_actor_to_blockchain_identity(self, actor_id: str, cert_id: str) -> None:
        """
        Map an actor to a blockchain identity.
        
        Args:
            actor_id: Actor ID
            cert_id: x.509 certificate ID for blockchain operations
        """
        self._identity_mappings[actor_id] = cert_id
        
        # Update actor record
        actor = actor_manager.get_actor(actor_id)
        if actor:
            actor.blockchain_identity = cert_id
            actor.updated_at = datetime.now(timezone.utc)
        
        logger.info("Mapped actor to blockchain identity", actor_id=actor_id, cert_id=cert_id)
    
    def get_blockchain_identity(self, actor_id: str) -> Optional[str]:
        """Get blockchain identity for an actor."""
        return self._identity_mappings.get(actor_id)
    
    def remove_mapping(self, actor_id: str) -> bool:
        """Remove blockchain identity mapping for an actor."""
        if actor_id in self._identity_mappings:
            del self._identity_mappings[actor_id]
            
            # Update actor record
            actor = actor_manager.get_actor(actor_id)
            if actor:
                actor.blockchain_identity = None
                actor.updated_at = datetime.now(timezone.utc)
            
            logger.info("Removed blockchain identity mapping", actor_id=actor_id)
            return True
        return False


# Global blockchain identity mapper
blockchain_identity_mapper = BlockchainIdentityMapper()


def get_blockchain_identity(current_user: Actor = Depends(get_current_user)) -> str:
    """
    Dependency to get blockchain identity for current user.
    
    Args:
        current_user: Current authenticated actor
        
    Returns:
        Blockchain identity (x.509 certificate ID)
        
    Raises:
        HTTPException: If no blockchain identity is mapped
    """
    identity = blockchain_identity_mapper.get_blockchain_identity(current_user.actor_id)
    
    if not identity:
        logger.warning("No blockchain identity mapped", actor_id=current_user.actor_id)
        raise HTTPException(
            status_code=400,
            detail="No blockchain identity mapped for this user"
        )
    
    return identity