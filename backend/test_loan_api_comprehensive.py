#!/usr/bin/env python3
"""
Comprehensive test of the Loan Origination API endpoints.
"""

from main import app
from fastapi.testclient import TestClient
from shared.auth import jwt_manager, Actor, ActorType, Role, Permission, actor_manager

def main():
    # Create test client
    client = TestClient(app)

    # Create test actors
    introducer = Actor(
        actor_id='test_introducer',
        actor_type=ActorType.EXTERNAL_PARTNER,
        actor_name='Test Introducer',
        role=Role.INTRODUCER,
        permissions={Permission.CREATE_LOAN_APPLICATION, Permission.READ_LOAN_APPLICATION}
    )

    credit_officer = Actor(
        actor_id='test_credit_officer',
        actor_type=ActorType.INTERNAL_USER,
        actor_name='Test Credit Officer',
        role=Role.CREDIT_OFFICER,
        permissions={Permission.READ_LOAN_APPLICATION, Permission.APPROVE_LOAN, Permission.REJECT_LOAN}
    )

    # Add actors to manager
    actor_manager._actors[introducer.actor_id] = introducer
    actor_manager._actors[credit_officer.actor_id] = credit_officer

    # Create auth tokens
    introducer_token = jwt_manager.create_access_token(introducer)
    credit_officer_token = jwt_manager.create_access_token(credit_officer)

    introducer_headers = {'Authorization': f'Bearer {introducer_token}'}
    credit_officer_headers = {'Authorization': f'Bearer {credit_officer_token}'}

    print('=== COMPREHENSIVE LOAN API TEST ===\n')

    # 1. Create loan application
    print('1. Creating loan application...')
    loan_data = {
        'customer_id': 'CUST_TEST123',
        'requested_amount': 75000.0,
        'loan_type': 'PERSONAL',
        'introducer_id': 'INTRO_001'
    }

    response = client.post('/api/v1/loans/', json=loan_data, headers=introducer_headers)
    if response.status_code == 201:
        result = response.json()
        loan_id = result['loan_application_id']
        print(f'✅ Loan created: {loan_id}')
        print(f'   Amount: ${result["requested_amount"]:,.2f}')
        print(f'   Status: {result["application_status"]}')
    else:
        print(f'❌ Failed: {response.json()}')
        return

    # 2. Retrieve loan application
    print(f'\n2. Retrieving loan application {loan_id}...')
    response = client.get(f'/api/v1/loans/{loan_id}', headers=introducer_headers)
    if response.status_code == 200:
        print('✅ Loan retrieved successfully')
    else:
        print(f'❌ Failed: {response.json()}')

    # 3. Test loan approval
    print(f'\n3. Approving loan {loan_id}...')
    approval_data = {
        'approval_amount': 65000.0,
        'notes': 'Approved with reduced amount due to credit score',
        'conditions': ['Provide additional income verification']
    }

    response = client.post(f'/api/v1/loans/{loan_id}/approve', json=approval_data, headers=credit_officer_headers)
    if response.status_code == 200:
        result = response.json()
        print(f'✅ Loan approved')
        print(f'   Approved amount: ${result["approval_amount"]:,.2f}')
        print(f'   Status: {result["application_status"]}')
    else:
        print(f'❌ Failed: {response.json()}')

    # 4. Test loan rejection (create another loan first)
    print(f'\n4. Creating another loan for rejection test...')
    loan_data2 = {
        'customer_id': 'CUST_TEST123',
        'requested_amount': 100000.0,
        'loan_type': 'BUSINESS',
        'introducer_id': 'INTRO_002'
    }

    response = client.post('/api/v1/loans/', json=loan_data2, headers=introducer_headers)
    if response.status_code == 201:
        result = response.json()
        loan_id2 = result['loan_application_id']
        print(f'✅ Second loan created: {loan_id2}')
        
        # Now reject it
        print(f'\n5. Rejecting loan {loan_id2}...')
        rejection_data = {
            'rejection_reason': 'Insufficient income documentation',
            'notes': 'Unable to verify stated income'
        }

        response = client.post(f'/api/v1/loans/{loan_id2}/reject', json=rejection_data, headers=credit_officer_headers)
        if response.status_code == 200:
            result = response.json()
            print(f'✅ Loan rejected')
            print(f'   Reason: {result["rejection_reason"]}')
            print(f'   Status: {result["application_status"]}')
        else:
            print(f'❌ Failed: {response.json()}')
    else:
        print(f'❌ Failed to create second loan: {response.json()}')

    print('\n=== ALL TESTS COMPLETED ===')

if __name__ == '__main__':
    main()