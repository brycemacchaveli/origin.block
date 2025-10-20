package config

// Entity prefixes for consistent key generation
const (
	// Customer domain prefixes
	CustomerPrefix    = "CUST"
	KYCRecordPrefix   = "KYC"
	AMLCheckPrefix    = "AML"
	
	// Loan domain prefixes
	LoanApplicationPrefix = "LOAN"
	LoanDocumentPrefix    = "DOC"
	LoanHistoryPrefix     = "LHIST"
	
	// Compliance domain prefixes
	ComplianceCasePrefix = "COMP"
	ComplianceRulePrefix = "RULE"
	ComplianceReportPrefix = "REPORT"
	
	// Shared prefixes
	ActorPrefix   = "ACTOR"
	HistoryPrefix = "HIST"
	EventPrefix   = "EVENT"
)