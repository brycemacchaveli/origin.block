"""
Integration test for document management endpoints.

Simple test to verify the endpoints are properly configured and can be called.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from loan_origination.api import router


def test_document_endpoints_registered():
    """Test that document endpoints are properly registered."""
    app = FastAPI()
    app.include_router(router, prefix="/loans")
    
    # Check that the routes are registered
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    
    # Document endpoints should be present
    assert "/loans/{loan_id}/documents" in routes
    assert "/loans/{loan_id}/documents/{document_id}/status" in routes
    assert "/loans/{loan_id}/documents/{document_id}/verify" in routes


def test_document_endpoints_methods():
    """Test that document endpoints have correct HTTP methods."""
    app = FastAPI()
    app.include_router(router, prefix="/loans")
    
    # Find document routes and collect all methods
    document_routes = {}
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods') and 'documents' in route.path:
            path = route.path
            if path not in document_routes:
                document_routes[path] = set()
            document_routes[path].update(route.methods)
    
    # Check that we have the expected paths
    expected_paths = [
        "/loans/{loan_id}/documents",
        "/loans/{loan_id}/documents/{document_id}/status", 
        "/loans/{loan_id}/documents/{document_id}/verify"
    ]
    
    for path in expected_paths:
        assert path in document_routes, f"Path {path} not found in routes"
    
    # Check that we have some HTTP methods for each path
    for path, methods in document_routes.items():
        assert len(methods) > 0, f"No methods found for path {path}"


def test_document_utility_functions():
    """Test document utility functions."""
    from loan_origination.api import _calculate_file_hash, _generate_document_id
    import hashlib
    
    # Test hash calculation
    test_content = b"test document content"
    expected_hash = hashlib.sha256(test_content).hexdigest()
    actual_hash = _calculate_file_hash(test_content)
    assert actual_hash == expected_hash
    
    # Test document ID generation
    doc_id = _generate_document_id()
    assert doc_id.startswith("DOC_")
    assert len(doc_id) == 20  # DOC_ + 16 hex characters
    
    # Test uniqueness
    doc_id2 = _generate_document_id()
    assert doc_id != doc_id2


if __name__ == "__main__":
    test_document_endpoints_registered()
    test_document_endpoints_methods()
    test_document_utility_functions()
    print("All integration tests passed!")