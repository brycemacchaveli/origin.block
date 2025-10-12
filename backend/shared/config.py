"""
Application configuration settings
"""
from typing import List
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Blockchain Financial Platform"
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    # Database
    DATABASE_URL: str = "sqlite:///./blockchain_finance.db"
    
    # Blockchain
    FABRIC_GATEWAY_ENDPOINT: str = "localhost:7051"
    FABRIC_MSP_ID: str = "Org1MSP"
    FABRIC_CHANNEL_NAME: str = "mychannel"
    FABRIC_PEER_ENDPOINT: str = "localhost:7051"
    FABRIC_CA_ENDPOINT: str = "localhost:7054"
    FABRIC_ADMIN_CERT_PATH: str = "./crypto/admin.pem"
    FABRIC_ADMIN_KEY_PATH: str = "./crypto/admin-key.pem"
    FABRIC_CA_CERT_PATH: str = "./crypto/ca.pem"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Logging
    LOG_LEVEL: str = "INFO"


settings = Settings()