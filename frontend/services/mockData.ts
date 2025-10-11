
import { Loan, LoanStatus, Customer, KycStatus, ComplianceEvent, ComplianceEventType } from '../types';

export const mockLoans: Loan[] = [
  {
    id: 'LOAN-001',
    applicantName: 'Alice Johnson',
    amount: 150000,
    status: LoanStatus.Approved,
    submittedDate: '2023-10-15',
    loanType: 'Mortgage',
    documents: [
      { id: 'DOC-1', name: 'Identity Verification', hash: '0xabc...', uploadedAt: '2023-10-15' },
      { id: 'DOC-2', name: 'Proof of Income', hash: '0xdef...', uploadedAt: '2023-10-16' },
    ],
    history: [
      { id: 'HIST-1', timestamp: '2023-10-15 09:00', actor: 'Introducer', action: 'Application Submitted', details: 'Initial submission.' },
      { id: 'HIST-2', timestamp: '2023-10-16 14:30', actor: 'Underwriter', action: 'Status Update', details: 'Changed status to Under Review.' },
      { id: 'HIST-3', timestamp: '2023-10-18 11:00', actor: 'Credit Officer', action: 'Status Update', details: 'Changed status to Approved.' },
    ],
  },
  {
    id: 'LOAN-002',
    applicantName: 'Bob Williams',
    amount: 25000,
    status: LoanStatus.UnderReview,
    submittedDate: '2023-11-01',
    loanType: 'Personal Loan',
    documents: [
        { id: 'DOC-3', name: 'ID Scan', hash: '0xghi...', uploadedAt: '2023-11-01' },
    ],
    history: [
        { id: 'HIST-4', timestamp: '2023-11-01 10:00', actor: 'Introducer', action: 'Application Submitted', details: 'Initial submission.' },
    ],
  },
  {
    id: 'LOAN-003',
    applicantName: 'Charlie Brown',
    amount: 5000,
    status: LoanStatus.Rejected,
    submittedDate: '2023-11-05',
    loanType: 'Auto Loan',
    documents: [],
    history: [
        { id: 'HIST-5', timestamp: '2023-11-05 12:00', actor: 'Introducer', action: 'Application Submitted', details: 'Initial submission.' },
        { id: 'HIST-6', timestamp: '2023-11-06 16:00', actor: 'Underwriter', action: 'Status Update', details: 'Changed status to Rejected due to insufficient credit score.' },
    ],
  },
];

export const mockCustomers: Customer[] = [
  { id: 'CUST-101', customerId: 'USR-8A7B', name: 'Alice Johnson', email: 'alice.j@example.com', kycStatus: KycStatus.Verified, onboardedDate: '2023-09-20', associatedLoans: ['LOAN-001'] },
  { id: 'CUST-102', customerId: 'USR-9C4D', name: 'Bob Williams', email: 'bob.w@example.com', kycStatus: KycStatus.Pending, onboardedDate: '2023-10-28', associatedLoans: ['LOAN-002'] },
  { id: 'CUST-103', customerId: 'USR-1E2F', name: 'Charlie Brown', email: 'charlie.b@example.com', kycStatus: KycStatus.Failed, onboardedDate: '2023-11-04', associatedLoans: ['LOAN-003'] },
];

export const mockComplianceEvents: ComplianceEvent[] = [
  { id: 'CE-001', timestamp: '2023-11-10 10:05:14', eventType: ComplianceEventType.Alert, ruleName: 'AML-LargeTransaction', affectedEntityType: 'Loan', affectedEntityId: 'LOAN-001', details: 'Transaction amount exceeds $100,000 threshold.' },
  { id: 'CE-002', timestamp: '2023-11-10 09:45:30', eventType: ComplianceEventType.Success, ruleName: 'KYC-Verification', affectedEntityType: 'Customer', affectedEntityId: 'CUST-101', details: 'KYC documents successfully verified.' },
  { id: 'CE-003', timestamp: '2023-11-09 15:20:00', eventType: ComplianceEventType.Violation, ruleName: 'Data-Consent-Check', affectedEntityType: 'Customer', affectedEntityId: 'CUST-103', details: 'Action attempted without required customer consent.' },
  { id: 'CE-004', timestamp: '2023-11-08 11:00:00', eventType: ComplianceEventType.Alert, ruleName: 'KYC-Pending-Review', affectedEntityType: 'Customer', affectedEntityId: 'CUST-102', details: 'Customer KYC status has been pending for over 10 days.' },
];
