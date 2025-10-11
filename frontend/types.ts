
export enum LoanStatus {
  Pending = 'Pending',
  Approved = 'Approved',
  Rejected = 'Rejected',
  UnderReview = 'Under Review',
}

export interface LoanDocument {
  id: string;
  name: string;
  hash: string;
  uploadedAt: string;
}

export interface LoanHistoryEvent {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  details: string;
}

export interface Loan {
  id: string;
  applicantName: string;
  amount: number;
  status: LoanStatus;
  submittedDate: string;
  loanType: string;
  documents: LoanDocument[];
  history: LoanHistoryEvent[];
}

export enum KycStatus {
  Verified = 'Verified',
  Pending = 'Pending',
  Failed = 'Failed',
}

export interface Customer {
  id: string;
  name: string;
  customerId: string;
  email: string;
  kycStatus: KycStatus;
  onboardedDate: string;
  associatedLoans: string[];
}

export enum ComplianceEventType {
  Violation = 'Violation',
  Success = 'Success',
  Alert = 'Alert',
}

export interface ComplianceEvent {
  id: string;
  timestamp: string;
  eventType: ComplianceEventType;
  ruleName: string;
  affectedEntityType: 'Loan' | 'Customer';
  affectedEntityId: string;
  details: string;
}
