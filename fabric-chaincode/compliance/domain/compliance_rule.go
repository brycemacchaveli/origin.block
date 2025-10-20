package domain

import (
	"encoding/json"
	"fmt"
	"time"
)

// ComplianceRuleStatus represents the status of a compliance rule
type ComplianceRuleStatus string

const (
	RuleStatusDraft     ComplianceRuleStatus = "DRAFT"
	RuleStatusPending   ComplianceRuleStatus = "PENDING_APPROVAL"
	RuleStatusActive    ComplianceRuleStatus = "ACTIVE"
	RuleStatusInactive  ComplianceRuleStatus = "INACTIVE"
	RuleStatusDeprecated ComplianceRuleStatus = "DEPRECATED"
)

// ComplianceRulePriority represents the priority level of a rule
type ComplianceRulePriority string

const (
	PriorityLow      ComplianceRulePriority = "LOW"
	PriorityMedium   ComplianceRulePriority = "MEDIUM"
	PriorityHigh     ComplianceRulePriority = "HIGH"
	PriorityCritical ComplianceRulePriority = "CRITICAL"
)

// RuleExecutionMode defines how the rule should be executed
type RuleExecutionMode string

const (
	ExecutionModeSync  RuleExecutionMode = "SYNCHRONOUS"
	ExecutionModeAsync RuleExecutionMode = "ASYNCHRONOUS"
	ExecutionModeBatch RuleExecutionMode = "BATCH"
)

// ComplianceRule represents a comprehensive compliance rule with versioning and dependencies
type ComplianceRule struct {
	// Core identification
	RuleID              string                 `json:"ruleID"`
	RuleName            string                 `json:"ruleName"`
	RuleDescription     string                 `json:"ruleDescription"`
	Version             string                 `json:"version"`
	
	// Rule logic and execution
	RuleLogic           string                 `json:"ruleLogic"`
	ExecutionMode       RuleExecutionMode      `json:"executionMode"`
	Priority            ComplianceRulePriority `json:"priority"`
	
	// Domain and applicability
	AppliesToDomain     string                 `json:"appliesToDomain"`
	AppliesToEntityType string                 `json:"appliesToEntityType"`
	TriggerEvents       []string               `json:"triggerEvents"`
	
	// Dependencies and relationships
	Dependencies        []string               `json:"dependencies"`        // Rule IDs this rule depends on
	ConflictsWith       []string               `json:"conflictsWith"`       // Rule IDs that conflict with this rule
	Supersedes          []string               `json:"supersedes"`          // Rule IDs this rule replaces
	
	// Status and lifecycle
	Status              ComplianceRuleStatus   `json:"status"`
	EffectiveDate       time.Time              `json:"effectiveDate"`
	ExpirationDate      *time.Time             `json:"expirationDate,omitempty"`
	
	// Approval workflow
	CreatedBy           string                 `json:"createdBy"`
	CreationDate        time.Time              `json:"creationDate"`
	ApprovedBy          string                 `json:"approvedBy,omitempty"`
	ApprovalDate        *time.Time             `json:"approvalDate,omitempty"`
	LastModifiedBy      string                 `json:"lastModifiedBy"`
	LastModifiedDate    time.Time              `json:"lastModifiedDate"`
	
	// Testing and validation
	TestCases           []RuleTestCase         `json:"testCases"`
	ValidationResults   []ValidationResult     `json:"validationResults"`
	
	// Metadata
	Tags                []string               `json:"tags"`
	RegulatoryReference string                 `json:"regulatoryReference,omitempty"`
	BusinessJustification string               `json:"businessJustification"`
}

// RuleTestCase represents a test case for validating rule logic
type RuleTestCase struct {
	TestID          string                 `json:"testID"`
	TestName        string                 `json:"testName"`
	TestDescription string                 `json:"testDescription"`
	InputData       map[string]interface{} `json:"inputData"`
	ExpectedResult  RuleExecutionResult    `json:"expectedResult"`
	CreatedBy       string                 `json:"createdBy"`
	CreationDate    time.Time              `json:"creationDate"`
}

// ValidationResult represents the result of rule validation
type ValidationResult struct {
	ValidationID    string    `json:"validationID"`
	ValidationType  string    `json:"validationType"` // SYNTAX, LOGIC, DEPENDENCY, CONFLICT
	IsValid         bool      `json:"isValid"`
	ErrorMessages   []string  `json:"errorMessages,omitempty"`
	WarningMessages []string  `json:"warningMessages,omitempty"`
	ValidatedBy     string    `json:"validatedBy"`
	ValidationDate  time.Time `json:"validationDate"`
}

// RuleExecutionResult represents the result of executing a compliance rule
type RuleExecutionResult struct {
	RuleID          string                 `json:"ruleID"`
	ExecutionID     string                 `json:"executionID"`
	Timestamp       time.Time              `json:"timestamp"`
	Success         bool                   `json:"success"`
	Passed          bool                   `json:"passed"`
	Score           float64                `json:"score,omitempty"`
	Details         map[string]interface{} `json:"details"`
	ErrorMessage    string                 `json:"errorMessage,omitempty"`
	ExecutionTime   int64                  `json:"executionTimeMs"`
}

// ComplianceEvent represents a compliance event with enhanced tracking
type ComplianceEvent struct {
	// Core identification
	EventID             string    `json:"eventID"`
	Timestamp           time.Time `json:"timestamp"`
	
	// Rule and entity information
	RuleID              string    `json:"ruleID"`
	RuleVersion         string    `json:"ruleVersion"`
	AffectedEntityID    string    `json:"affectedEntityID"`
	AffectedEntityType  string    `json:"affectedEntityType"`
	
	// Event details
	EventType           string                 `json:"eventType"` // RULE_EXECUTED, VIOLATION_DETECTED, ALERT_GENERATED
	Severity            ComplianceRulePriority `json:"severity"`
	Details             map[string]interface{} `json:"details"`
	ExecutionResult     RuleExecutionResult    `json:"executionResult"`
	
	// Actor and workflow
	ActorID             string     `json:"actorID"`
	IsAlerted           bool       `json:"isAlerted"`
	AcknowledgedBy      string     `json:"acknowledgedBy,omitempty"`
	AcknowledgedDate    *time.Time `json:"acknowledgedDate,omitempty"`
	ResolutionStatus    string     `json:"resolutionStatus"` // OPEN, IN_PROGRESS, RESOLVED, CLOSED
	ResolutionNotes     string     `json:"resolutionNotes,omitempty"`
}

// RuleApprovalRequest represents a request for rule approval
type RuleApprovalRequest struct {
	RequestID       string    `json:"requestID"`
	RuleID          string    `json:"ruleID"`
	RequestedBy     string    `json:"requestedBy"`
	RequestDate     time.Time `json:"requestDate"`
	Justification   string    `json:"justification"`
	Status          string    `json:"status"` // PENDING, APPROVED, REJECTED
	ReviewedBy      string    `json:"reviewedBy,omitempty"`
	ReviewDate      *time.Time `json:"reviewDate,omitempty"`
	ReviewComments  string    `json:"reviewComments,omitempty"`
}

// Validate performs comprehensive validation of the ComplianceRule
func (r *ComplianceRule) Validate() []ValidationResult {
	var results []ValidationResult
	
	// Syntax validation
	syntaxResult := r.validateSyntax()
	results = append(results, syntaxResult)
	
	// Logic validation
	logicResult := r.validateLogic()
	results = append(results, logicResult)
	
	// Dependency validation
	depResult := r.validateDependencies()
	results = append(results, depResult)
	
	return results
}

// validateSyntax validates the basic syntax and structure of the rule
func (r *ComplianceRule) validateSyntax() ValidationResult {
	result := ValidationResult{
		ValidationID:   fmt.Sprintf("syntax_%s_%d", r.RuleID, time.Now().Unix()),
		ValidationType: "SYNTAX",
		IsValid:        true,
		ValidationDate: time.Now(),
	}
	
	var errors []string
	var warnings []string
	
	// Required fields validation
	if r.RuleID == "" {
		errors = append(errors, "RuleID is required")
	}
	if r.RuleName == "" {
		errors = append(errors, "RuleName is required")
	}
	if r.RuleLogic == "" {
		errors = append(errors, "RuleLogic is required")
	}
	if r.AppliesToDomain == "" {
		errors = append(errors, "AppliesToDomain is required")
	}
	
	// Status validation
	validStatuses := []ComplianceRuleStatus{RuleStatusDraft, RuleStatusPending, RuleStatusActive, RuleStatusInactive, RuleStatusDeprecated}
	statusValid := false
	for _, status := range validStatuses {
		if r.Status == status {
			statusValid = true
			break
		}
	}
	if !statusValid {
		errors = append(errors, fmt.Sprintf("Invalid status: %s", r.Status))
	}
	
	// Priority validation
	validPriorities := []ComplianceRulePriority{PriorityLow, PriorityMedium, PriorityHigh, PriorityCritical}
	priorityValid := false
	for _, priority := range validPriorities {
		if r.Priority == priority {
			priorityValid = true
			break
		}
	}
	if !priorityValid {
		errors = append(errors, fmt.Sprintf("Invalid priority: %s", r.Priority))
	}
	
	// Execution mode validation
	validModes := []RuleExecutionMode{ExecutionModeSync, ExecutionModeAsync, ExecutionModeBatch}
	modeValid := false
	for _, mode := range validModes {
		if r.ExecutionMode == mode {
			modeValid = true
			break
		}
	}
	if !modeValid {
		errors = append(errors, fmt.Sprintf("Invalid execution mode: %s", r.ExecutionMode))
	}
	
	// Date validation
	if r.ExpirationDate != nil && r.ExpirationDate.Before(r.EffectiveDate) {
		errors = append(errors, "ExpirationDate cannot be before EffectiveDate")
	}
	
	// Warning for missing test cases
	if len(r.TestCases) == 0 {
		warnings = append(warnings, "No test cases defined for this rule")
	}
	
	result.ErrorMessages = errors
	result.WarningMessages = warnings
	result.IsValid = len(errors) == 0
	
	return result
}

// validateLogic validates the rule logic syntax and structure
func (r *ComplianceRule) validateLogic() ValidationResult {
	result := ValidationResult{
		ValidationID:   fmt.Sprintf("logic_%s_%d", r.RuleID, time.Now().Unix()),
		ValidationType: "LOGIC",
		IsValid:        true,
		ValidationDate: time.Now(),
	}
	
	var errors []string
	var warnings []string
	
	// Basic logic validation (in a real implementation, this would parse and validate the rule syntax)
	if len(r.RuleLogic) < 10 {
		errors = append(errors, "Rule logic appears to be too simple")
	}
	
	if len(r.RuleLogic) > 10000 {
		warnings = append(warnings, "Rule logic is very complex, consider breaking into smaller rules")
	}
	
	// Check for basic JSON structure if rule logic is JSON
	if len(r.RuleLogic) > 0 && r.RuleLogic[0] == '{' {
		var temp map[string]interface{}
		if err := json.Unmarshal([]byte(r.RuleLogic), &temp); err != nil {
			errors = append(errors, fmt.Sprintf("Invalid JSON in rule logic: %v", err))
		}
	}
	
	result.ErrorMessages = errors
	result.WarningMessages = warnings
	result.IsValid = len(errors) == 0
	
	return result
}

// validateDependencies validates rule dependencies and conflicts
func (r *ComplianceRule) validateDependencies() ValidationResult {
	result := ValidationResult{
		ValidationID:   fmt.Sprintf("dependency_%s_%d", r.RuleID, time.Now().Unix()),
		ValidationType: "DEPENDENCY",
		IsValid:        true,
		ValidationDate: time.Now(),
	}
	
	var errors []string
	var warnings []string
	
	// Check for circular dependencies (basic check)
	for _, dep := range r.Dependencies {
		if dep == r.RuleID {
			errors = append(errors, "Rule cannot depend on itself")
		}
	}
	
	// Check for conflicts with dependencies
	for _, dep := range r.Dependencies {
		for _, conflict := range r.ConflictsWith {
			if dep == conflict {
				errors = append(errors, fmt.Sprintf("Rule depends on %s but also conflicts with it", dep))
			}
		}
	}
	
	// Check for superseding itself
	for _, superseded := range r.Supersedes {
		if superseded == r.RuleID {
			errors = append(errors, "Rule cannot supersede itself")
		}
	}
	
	result.ErrorMessages = errors
	result.WarningMessages = warnings
	result.IsValid = len(errors) == 0
	
	return result
}

// GetCompositeKey returns the composite key for the rule
func (r *ComplianceRule) GetCompositeKey() string {
	return fmt.Sprintf("rule~%s~%s", r.RuleID, r.Version)
}

// GetLatestVersionKey returns the key for tracking the latest version
func (r *ComplianceRule) GetLatestVersionKey() string {
	return fmt.Sprintf("rule_latest~%s", r.RuleID)
}

// IsActive returns true if the rule is currently active
func (r *ComplianceRule) IsActive() bool {
	now := time.Now()
	return r.Status == RuleStatusActive &&
		(r.EffectiveDate.Before(now) || r.EffectiveDate.Equal(now)) &&
		(r.ExpirationDate == nil || r.ExpirationDate.After(now))
}

// CanExecute returns true if the rule can be executed
func (r *ComplianceRule) CanExecute() bool {
	return r.IsActive() && len(r.ValidationResults) > 0 && r.allValidationsPassed()
}

// allValidationsPassed checks if all validations have passed
func (r *ComplianceRule) allValidationsPassed() bool {
	for _, validation := range r.ValidationResults {
		if !validation.IsValid {
			return false
		}
	}
	return true
}