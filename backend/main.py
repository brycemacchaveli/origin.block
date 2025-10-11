"""
Main FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from customer_mastery.api import router as customer_router
from loan_origination.api import router as loan_router
from compliance_reporting.api import router as compliance_router
from shared.config import settings

app = FastAPI(
    title="Blockchain Financial Platform API",
    description="API services for blockchain-based financial operations",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(customer_router, prefix="/api/v1/customers", tags=["customers"])
app.include_router(loan_router, prefix="/api/v1/loans", tags=["loans"])
app.include_router(compliance_router, prefix="/api/v1/compliance", tags=["compliance"])

@app.get("/")
async def root():
    return {"message": "Blockchain Financial Platform API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)