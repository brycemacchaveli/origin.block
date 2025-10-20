package config

// Event names for cross-chaincode communication
const (
	// Customer events
	EventCustomerCreated     = "CustomerCreated"
	EventCustomerUpdated     = "CustomerUpdated"
	EventKYCVerified         = "KYCVerified"
	EventKYCFailed           = "KYCFailed"
	EventAMLCheckCompleted   = "AMLCheckCompleted"
	EventAMLFlagged          = "AMLFlagged"
	
	// Loan events
	EventLoanSubmitted       = "LoanSubmitted"
	EventLoanApproved        = "LoanApproved"
	EventLoanRejected        = "LoanRejected"
	EventLoanDisbursed       = "LoanDisbursed"
	EventDocumentUploaded    = "DocumentUploaded"
	EventDocumentVerified    = "DocumentVerified"
	
	// Compliance events
	EventComplianceCheckTriggered = "ComplianceCheckTriggered"
	EventComplianceRuleViolation  = "ComplianceRuleViolation"
	EventComplianceReportGenerated = "ComplianceReportGenerated"
	EventRegulatoryAlert          = "RegulatoryAlert"
)