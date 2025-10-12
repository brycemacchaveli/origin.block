"""
Hyperledger Fabric Gateway SDK wrapper for blockchain operations.

This module provides a high-level interface for interacting with Hyperledger Fabric
chaincode, including connection management, transaction invocation, and query operations.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import settings

logger = structlog.get_logger(__name__)


class FabricError(Exception):
    """Base exception for Fabric-related errors."""
    pass


class ConnectionError(FabricError):
    """Raised when connection to Fabric network fails."""
    pass


class TransactionError(FabricError):
    """Raised when transaction execution fails."""
    pass


class QueryError(FabricError):
    """Raised when query execution fails."""
    pass


class ChaincodeType(Enum):
    """Supported chaincode types."""
    CUSTOMER = "customer"
    LOAN = "loan"
    COMPLIANCE = "compliance"


@dataclass
class FabricConfig:
    """Configuration for Fabric Gateway connection."""
    gateway_endpoint: str
    msp_id: str
    channel_name: str
    peer_endpoint: str
    ca_endpoint: str
    admin_cert_path: str
    admin_key_path: str
    ca_cert_path: str
    
    @classmethod
    def from_settings(cls) -> "FabricConfig":
        """Create FabricConfig from application settings."""
        return cls(
            gateway_endpoint=settings.FABRIC_GATEWAY_ENDPOINT,
            msp_id=settings.FABRIC_MSP_ID,
            channel_name=settings.FABRIC_CHANNEL_NAME,
            peer_endpoint=getattr(settings, 'FABRIC_PEER_ENDPOINT', 'localhost:7051'),
            ca_endpoint=getattr(settings, 'FABRIC_CA_ENDPOINT', 'localhost:7054'),
            admin_cert_path=getattr(settings, 'FABRIC_ADMIN_CERT_PATH', './crypto/admin.pem'),
            admin_key_path=getattr(settings, 'FABRIC_ADMIN_KEY_PATH', './crypto/admin-key.pem'),
            ca_cert_path=getattr(settings, 'FABRIC_CA_CERT_PATH', './crypto/ca.pem'),
        )


class FabricGateway:
    """
    High-level wrapper for Hyperledger Fabric Gateway operations.
    
    Provides connection management, transaction invocation, and query capabilities
    with built-in error handling, retry logic, and connection pooling.
    """
    
    def __init__(self, config: Optional[FabricConfig] = None):
        """Initialize Fabric Gateway with configuration."""
        self.config = config or FabricConfig.from_settings()
        self._connection_pool: Dict[str, Any] = {}
        self._is_connected = False
        
    async def connect(self) -> None:
        """
        Establish connection to Fabric network.
        
        Raises:
            ConnectionError: If connection fails
        """
        try:
            logger.info("Connecting to Fabric network", 
                       endpoint=self.config.gateway_endpoint,
                       msp_id=self.config.msp_id)
            
            # Note: This is a placeholder for actual Fabric SDK connection
            # In a real implementation, you would use the Fabric Python SDK
            # to establish the connection here
            
            self._is_connected = True
            logger.info("Successfully connected to Fabric network")
            
        except Exception as e:
            logger.error("Failed to connect to Fabric network", error=str(e))
            raise ConnectionError(f"Failed to connect to Fabric network: {e}")
    
    async def disconnect(self) -> None:
        """Disconnect from Fabric network and cleanup resources."""
        try:
            logger.info("Disconnecting from Fabric network")
            
            # Cleanup connection pool
            self._connection_pool.clear()
            self._is_connected = False
            
            logger.info("Successfully disconnected from Fabric network")
            
        except Exception as e:
            logger.error("Error during disconnect", error=str(e))
    
    def _ensure_connected(self) -> None:
        """Ensure connection is established."""
        if not self._is_connected:
            raise ConnectionError("Not connected to Fabric network. Call connect() first.")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TransactionError))
    )
    async def invoke_chaincode(
        self,
        chaincode_name: str,
        function_name: str,
        args: List[str],
        transient_data: Optional[Dict[str, bytes]] = None
    ) -> Dict[str, Any]:
        """
        Invoke a chaincode function that modifies the ledger.
        
        Args:
            chaincode_name: Name of the chaincode to invoke
            function_name: Function name to call
            args: List of string arguments for the function
            transient_data: Optional transient data for the transaction
            
        Returns:
            Transaction result as dictionary
            
        Raises:
            TransactionError: If transaction fails
            ConnectionError: If connection is lost
        """
        self._ensure_connected()
        
        try:
            logger.info("Invoking chaincode function",
                       chaincode=chaincode_name,
                       function=function_name,
                       args_count=len(args))
            
            # Note: This is a placeholder for actual chaincode invocation
            # In a real implementation, you would use the Fabric SDK to:
            # 1. Create a transaction proposal
            # 2. Send to endorsing peers
            # 3. Collect endorsements
            # 4. Submit to orderer
            # 5. Wait for commit
            
            # Simulate successful transaction
            result = {
                "transaction_id": f"tx_{chaincode_name}_{function_name}",
                "status": "SUCCESS",
                "payload": {},
                "timestamp": "2024-01-01T00:00:00Z"
            }
            
            logger.info("Chaincode invocation successful",
                       transaction_id=result["transaction_id"])
            
            return result
            
        except Exception as e:
            logger.error("Chaincode invocation failed",
                        chaincode=chaincode_name,
                        function=function_name,
                        error=str(e))
            raise TransactionError(f"Failed to invoke {chaincode_name}.{function_name}: {e}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((ConnectionError, QueryError))
    )
    async def query_chaincode(
        self,
        chaincode_name: str,
        function_name: str,
        args: List[str]
    ) -> Dict[str, Any]:
        """
        Query a chaincode function that reads from the ledger.
        
        Args:
            chaincode_name: Name of the chaincode to query
            function_name: Function name to call
            args: List of string arguments for the function
            
        Returns:
            Query result as dictionary
            
        Raises:
            QueryError: If query fails
            ConnectionError: If connection is lost
        """
        self._ensure_connected()
        
        try:
            logger.info("Querying chaincode function",
                       chaincode=chaincode_name,
                       function=function_name,
                       args_count=len(args))
            
            # Note: This is a placeholder for actual chaincode query
            # In a real implementation, you would use the Fabric SDK to:
            # 1. Create a query proposal
            # 2. Send to a peer
            # 3. Return the result
            
            # Simulate successful query
            result = {
                "status": "SUCCESS",
                "payload": {},
                "timestamp": "2024-01-01T00:00:00Z"
            }
            
            logger.info("Chaincode query successful")
            
            return result
            
        except Exception as e:
            logger.error("Chaincode query failed",
                        chaincode=chaincode_name,
                        function=function_name,
                        error=str(e))
            raise QueryError(f"Failed to query {chaincode_name}.{function_name}: {e}")
    
    async def get_transaction_by_id(self, transaction_id: str) -> Dict[str, Any]:
        """
        Retrieve transaction details by transaction ID.
        
        Args:
            transaction_id: The transaction ID to retrieve
            
        Returns:
            Transaction details as dictionary
            
        Raises:
            QueryError: If transaction retrieval fails
        """
        self._ensure_connected()
        
        try:
            logger.info("Retrieving transaction", transaction_id=transaction_id)
            
            # Note: Placeholder for actual transaction retrieval
            result = {
                "transaction_id": transaction_id,
                "status": "VALID",
                "timestamp": "2024-01-01T00:00:00Z",
                "creator_msp_id": self.config.msp_id,
                "chaincode_name": "unknown",
                "function_name": "unknown",
                "args": []
            }
            
            return result
            
        except Exception as e:
            logger.error("Failed to retrieve transaction",
                        transaction_id=transaction_id,
                        error=str(e))
            raise QueryError(f"Failed to retrieve transaction {transaction_id}: {e}")
    
    async def get_block_by_number(self, block_number: int) -> Dict[str, Any]:
        """
        Retrieve block details by block number.
        
        Args:
            block_number: The block number to retrieve
            
        Returns:
            Block details as dictionary
            
        Raises:
            QueryError: If block retrieval fails
        """
        self._ensure_connected()
        
        try:
            logger.info("Retrieving block", block_number=block_number)
            
            # Note: Placeholder for actual block retrieval
            result = {
                "block_number": block_number,
                "previous_hash": "0x...",
                "data_hash": "0x...",
                "transactions": [],
                "timestamp": "2024-01-01T00:00:00Z"
            }
            
            return result
            
        except Exception as e:
            logger.error("Failed to retrieve block",
                        block_number=block_number,
                        error=str(e))
            raise QueryError(f"Failed to retrieve block {block_number}: {e}")


class ChaincodeClient:
    """
    High-level client for specific chaincode operations.
    
    Provides domain-specific methods for interacting with Customer, Loan,
    and Compliance chaincodes.
    """
    
    def __init__(self, gateway: FabricGateway, chaincode_type: ChaincodeType):
        """Initialize chaincode client."""
        self.gateway = gateway
        self.chaincode_type = chaincode_type
        self.chaincode_name = chaincode_type.value
    
    async def create_entity(self, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new entity in the chaincode.
        
        Args:
            entity_data: Entity data to create
            
        Returns:
            Creation result
        """
        args = [json.dumps(entity_data)]
        return await self.gateway.invoke_chaincode(
            self.chaincode_name,
            "CreateEntity",
            args
        )
    
    async def update_entity(self, entity_id: str, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing entity in the chaincode.
        
        Args:
            entity_id: ID of entity to update
            entity_data: Updated entity data
            
        Returns:
            Update result
        """
        args = [entity_id, json.dumps(entity_data)]
        return await self.gateway.invoke_chaincode(
            self.chaincode_name,
            "UpdateEntity",
            args
        )
    
    async def get_entity(self, entity_id: str) -> Dict[str, Any]:
        """
        Retrieve an entity by ID.
        
        Args:
            entity_id: ID of entity to retrieve
            
        Returns:
            Entity data
        """
        args = [entity_id]
        result = await self.gateway.query_chaincode(
            self.chaincode_name,
            "GetEntity",
            args
        )
        return result
    
    async def get_entity_history(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve entity history by ID.
        
        Args:
            entity_id: ID of entity to get history for
            
        Returns:
            List of historical records
        """
        args = [entity_id]
        result = await self.gateway.query_chaincode(
            self.chaincode_name,
            "GetEntityHistory",
            args
        )
        # Ensure we return a list even if payload is empty or not a list
        payload = result.get("payload", [])
        return payload if isinstance(payload, list) else []


# Connection pool management
_gateway_pool: Dict[str, FabricGateway] = {}


async def get_fabric_gateway(config: Optional[FabricConfig] = None) -> FabricGateway:
    """
    Get or create a Fabric Gateway connection.
    
    Args:
        config: Optional configuration, uses default if not provided
        
    Returns:
        Connected FabricGateway instance
    """
    config = config or FabricConfig.from_settings()
    pool_key = f"{config.gateway_endpoint}_{config.msp_id}"
    
    if pool_key not in _gateway_pool:
        gateway = FabricGateway(config)
        await gateway.connect()
        _gateway_pool[pool_key] = gateway
    
    return _gateway_pool[pool_key]


@asynccontextmanager
async def fabric_gateway_context(config: Optional[FabricConfig] = None):
    """
    Context manager for Fabric Gateway operations.
    
    Usage:
        async with fabric_gateway_context() as gateway:
            result = await gateway.query_chaincode("customer", "GetCustomer", ["123"])
    """
    gateway = await get_fabric_gateway(config)
    try:
        yield gateway
    finally:
        # Connection is managed by the pool, so we don't disconnect here
        pass


async def cleanup_gateway_pool():
    """Cleanup all gateway connections in the pool."""
    for gateway in _gateway_pool.values():
        await gateway.disconnect()
    _gateway_pool.clear()