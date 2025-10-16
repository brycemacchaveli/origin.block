package domain

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
)

// ApprovalWorkflowManager manages the rule approval workflow
type ApprovalWorkflowManager struct {
	ruleRepository RuleRepository
	eventEmitter   EventEmitter
}

// NewApprovalWorkflowManager creates a new approval workflow manager
func NewApprovalWorkflowManager(repository RuleRepository, emitter EventEmitter) *ApprovalWorkflowManager {
	return &ApprovalWorkflowManager{
		ruleRepository: repository,
		eventEmitter:   emitter,
	}
}

// SubmitRuleForApproval submits a rule for approval
func (w *ApprovalWorkflowManager) SubmitRuleForApproval(stub shim.ChaincodeStubInterface, ruleID string, requestedBy string, justification string) (*RuleApprovalRequest, error) {
	// Get the rule
	rule, err := w.ruleRepository.GetLatestRule(stub, ruleID)
	if err != nil {
		return nil, fmt.Errorf("failed to get rule for approval: %v", err)
	}
	
	// Check if rule is in a state that can be approved
	if rule.Status != RuleStatusDraft && rule.Status != RuleStatusPending {
		return nil, fmt.Errorf("rule %s is not in a state that can be submitted for approval (current status: %s)", ruleID, rule.Status)
	}
	
	// Validate the rule before submission
	validationResults, err := w.validateRuleForApproval(stub, rule)
	if err != nil {
		return nil, fmt.Errorf("failed to validate rule for approval: %v", err)
	}
	
	// Check if validation passed
	for _, result := range validationResults {
		if !result.IsValid {
			return nil, fmt.Errorf("rule validation failed: %v", result.ErrorMessages)
		}
	}
	
	// Create approval request
	request := &RuleApprovalRequest{
		RequestID:     fmt.Sprintf("approval_%s_%d", ruleID, time.Now().UnixNano()),
		RuleID:        ruleID,
		RequestedBy:   requestedBy,
		RequestDate:   time.Now(),
		Justification: justification,
		Status:        "PENDING",
	}
	
	// Save approval request
	if err := w.saveApprovalRequest(stub, request); err != nil {
		return nil, fmt.Errorf("failed to save approval request: %v", err)
	}
	
	// Update rule status to pending approval
	rule.Status = RuleStatusPending
	rule.LastModifiedBy = requestedBy
	rule.LastModifiedDate = time.Now()
	
	if err := w.ruleRepository.SaveRule(stub, rule); err != nil {
		return nil, fmt.Errorf("failed to update rule status: %v", err)
	}
	
	// Emit approval request event
	if w.eventEmitter != nil {
		event := &ComplianceEvent{
			EventID:            fmt.Sprintf("approval_request_%s", request.RequestID),
			Timestamp:          time.Now(),
			RuleID:             ruleID,
			EventType:          "RULE_APPROVAL_REQUESTED",
			Severity:           PriorityMedium,
			Details:            map[string]interface{}{"requestID": request.RequestID, "justification": justification},
			ActorID:            requestedBy,
			ResolutionStatus:   "OPEN",
		}
		w.eventEmitter.EmitComplianceEvent(stub, event)
	}
	
	return request, nil
}

// ApproveRule approves a rule
func (w *ApprovalWorkflowManager) ApproveRule(stub shim.ChaincodeStubInterface, requestID string, reviewedBy string, comments string) error {
	// Get approval request
	request, err := w.getApprovalRequest(stub, requestID)
	if err != nil {
		return fmt.Errorf("failed to get approval request: %v", err)
	}
	
	if request.Status != "PENDING" {
		return fmt.Errorf("approval request %s is not pending (current status: %s)", requestID, request.Status)
	}
	
	// Get the rule
	rule, err := w.ruleRepository.GetLatestRule(stub, request.RuleID)
	if err != nil {
		return fmt.Errorf("failed to get rule for approval: %v", err)
	}
	
	// Update approval request
	request.Status = "APPROVED"
	request.ReviewedBy = reviewedBy
	now := time.Now()
	request.ReviewDate = &now
	request.ReviewComments = comments
	
	if err := w.saveApprovalRequest(stub, request); err != nil {
		return fmt.Errorf("failed to update approval request: %v", err)
	}
	
	// Update rule status and approval information
	rule.Status = RuleStatusActive
	rule.ApprovedBy = reviewedBy
	rule.ApprovalDate = &now
	rule.LastModifiedBy = reviewedBy
	rule.LastModifiedDate = now
	
	// Set effective date if not already set
	if rule.EffectiveDate.IsZero() {
		rule.EffectiveDate = now
	}
	
	if err := w.ruleRepository.SaveRule(stub, rule); err != nil {
		return fmt.Errorf("failed to update approved rule: %v", err)
	}
	
	// Handle rule supersession
	if err := w.handleRuleSupersession(stub, rule); err != nil {
		return fmt.Errorf("failed to handle rule supersession: %v", err)
	}
	
	// Emit approval event
	if w.eventEmitter != nil {
		event := &ComplianceEvent{
			EventID:            fmt.Sprintf("rule_approved_%s", rule.RuleID),
			Timestamp:          now,
			RuleID:             rule.RuleID,
			EventType:          "RULE_APPROVED",
			Severity:           PriorityMedium,
			Details:            map[string]interface{}{"requestID": requestID, "comments": comments},
			ActorID:            reviewedBy,
			ResolutionStatus:   "RESOLVED",
		}
		w.eventEmitter.EmitComplianceEvent(stub, event)
	}
	
	return nil
}

// RejectRule rejects a rule approval request
func (w *ApprovalWorkflowManager) RejectRule(stub shim.ChaincodeStubInterface, requestID string, reviewedBy string, comments string) error {
	// Get approval request
	request, err := w.getApprovalRequest(stub, requestID)
	if err != nil {
		return fmt.Errorf("failed to get approval request: %v", err)
	}
	
	if request.Status != "PENDING" {
		return fmt.Errorf("approval request %s is not pending (current status: %s)", requestID, request.Status)
	}
	
	// Get the rule
	rule, err := w.ruleRepository.GetLatestRule(stub, request.RuleID)
	if err != nil {
		return fmt.Errorf("failed to get rule for rejection: %v", err)
	}
	
	// Update approval request
	request.Status = "REJECTED"
	request.ReviewedBy = reviewedBy
	now := time.Now()
	request.ReviewDate = &now
	request.ReviewComments = comments
	
	if err := w.saveApprovalRequest(stub, request); err != nil {
		return fmt.Errorf("failed to update approval request: %v", err)
	}
	
	// Update rule status back to draft
	rule.Status = RuleStatusDraft
	rule.LastModifiedBy = reviewedBy
	rule.LastModifiedDate = now
	
	if err := w.ruleRepository.SaveRule(stub, rule); err != nil {
		return fmt.Errorf("failed to update rejected rule: %v", err)
	}
	
	// Emit rejection event
	if w.eventEmitter != nil {
		event := &ComplianceEvent{
			EventID:            fmt.Sprintf("rule_rejected_%s", rule.RuleID),
			Timestamp:          now,
			RuleID:             rule.RuleID,
			EventType:          "RULE_REJECTED",
			Severity:           PriorityMedium,
			Details:            map[string]interface{}{"requestID": requestID, "comments": comments},
			ActorID:            reviewedBy,
			ResolutionStatus:   "RESOLVED",
		}
		w.eventEmitter.EmitComplianceEvent(stub, event)
	}
	
	return nil
}

// GetPendingApprovals retrieves all pending approval requests
func (w *ApprovalWorkflowManager) GetPendingApprovals(stub shim.ChaincodeStubInterface) ([]*RuleApprovalRequest, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("approval_status", []string{"PENDING"})
	if err != nil {
		return nil, fmt.Errorf("failed to get pending approvals: %v", err)
	}
	defer iterator.Close()
	
	var requests []*RuleApprovalRequest
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate pending approvals: %v", err)
		}
		
		// Extract request ID from composite key
		_, compositeKeyParts, err := stub.SplitCompositeKey(response.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		
		requestID := compositeKeyParts[1]
		request, err := w.getApprovalRequest(stub, requestID)
		if err != nil {
			continue // Skip requests that can't be loaded
		}
		
		requests = append(requests, request)
	}
	
	return requests, nil
}

// GetApprovalHistory retrieves the approval history for a rule
func (w *ApprovalWorkflowManager) GetApprovalHistory(stub shim.ChaincodeStubInterface, ruleID string) ([]*RuleApprovalRequest, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("approval_rule", []string{ruleID})
	if err != nil {
		return nil, fmt.Errorf("failed to get approval history for rule %s: %v", ruleID, err)
	}
	defer iterator.Close()
	
	var requests []*RuleApprovalRequest
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate approval history: %v", err)
		}
		
		// Extract request ID from composite key
		_, compositeKeyParts, err := stub.SplitCompositeKey(response.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		
		requestID := compositeKeyParts[1]
		request, err := w.getApprovalRequest(stub, requestID)
		if err != nil {
			continue // Skip requests that can't be loaded
		}
		
		requests = append(requests, request)
	}
	
	return requests, nil
}

// validateRuleForApproval performs comprehensive validation before approval
func (w *ApprovalWorkflowManager) validateRuleForApproval(stub shim.ChaincodeStubInterface, rule *ComplianceRule) ([]ValidationResult, error) {
	var results []ValidationResult
	
	// Basic rule validation
	basicResults := rule.Validate()
	results = append(results, basicResults...)
	
	// Dependency validation
	for _, depID := range rule.Dependencies {
		depRule, err := w.ruleRepository.GetLatestRule(stub, depID)
		if err != nil {
			result := ValidationResult{
				ValidationID:   fmt.Sprintf("dep_approval_%s_%d", rule.RuleID, time.Now().Unix()),
				ValidationType: "DEPENDENCY",
				IsValid:        false,
				ErrorMessages:  []string{fmt.Sprintf("Dependency rule %s not found", depID)},
				ValidationDate: time.Now(),
			}
			results = append(results, result)
			continue
		}
		
		if !depRule.IsActive() {
			result := ValidationResult{
				ValidationID:   fmt.Sprintf("dep_active_%s_%d", rule.RuleID, time.Now().Unix()),
				ValidationType: "DEPENDENCY",
				IsValid:        false,
				ErrorMessages:  []string{fmt.Sprintf("Dependency rule %s is not active", depID)},
				ValidationDate: time.Now(),
			}
			results = append(results, result)
		}
	}
	
	// Conflict validation
	for _, conflictID := range rule.ConflictsWith {
		conflictRule, err := w.ruleRepository.GetLatestRule(stub, conflictID)
		if err == nil && conflictRule.IsActive() {
			result := ValidationResult{
				ValidationID:   fmt.Sprintf("conflict_approval_%s_%d", rule.RuleID, time.Now().Unix()),
				ValidationType: "CONFLICT",
				IsValid:        false,
				ErrorMessages:  []string{fmt.Sprintf("Conflicting rule %s is currently active", conflictID)},
				ValidationDate: time.Now(),
			}
			results = append(results, result)
		}
	}
	
	// Test case validation
	if len(rule.TestCases) == 0 {
		result := ValidationResult{
			ValidationID:   fmt.Sprintf("test_approval_%s_%d", rule.RuleID, time.Now().Unix()),
			ValidationType: "TESTING",
			IsValid:        false,
			ErrorMessages:  []string{"Rule must have at least one test case before approval"},
			ValidationDate: time.Now(),
		}
		results = append(results, result)
	}
	
	return results, nil
}

// handleRuleSupersession handles rules that are superseded by the approved rule
func (w *ApprovalWorkflowManager) handleRuleSupersession(stub shim.ChaincodeStubInterface, rule *ComplianceRule) error {
	for _, supersededID := range rule.Supersedes {
		supersededRule, err := w.ruleRepository.GetLatestRule(stub, supersededID)
		if err != nil {
			continue // Skip rules that can't be loaded
		}
		
		// Mark superseded rule as deprecated
		supersededRule.Status = RuleStatusDeprecated
		supersededRule.LastModifiedBy = rule.ApprovedBy
		supersededRule.LastModifiedDate = time.Now()
		
		if err := w.ruleRepository.SaveRule(stub, supersededRule); err != nil {
			return fmt.Errorf("failed to deprecate superseded rule %s: %v", supersededID, err)
		}
		
		// Emit supersession event
		if w.eventEmitter != nil {
			event := &ComplianceEvent{
				EventID:            fmt.Sprintf("rule_superseded_%s", supersededID),
				Timestamp:          time.Now(),
				RuleID:             supersededID,
				EventType:          "RULE_SUPERSEDED",
				Severity:           PriorityMedium,
				Details:            map[string]interface{}{"supersededBy": rule.RuleID},
				ActorID:            rule.ApprovedBy,
				ResolutionStatus:   "RESOLVED",
			}
			w.eventEmitter.EmitComplianceEvent(stub, event)
		}
	}
	
	return nil
}

// saveApprovalRequest saves an approval request to the ledger
func (w *ApprovalWorkflowManager) saveApprovalRequest(stub shim.ChaincodeStubInterface, request *RuleApprovalRequest) error {
	requestBytes, err := json.Marshal(request)
	if err != nil {
		return fmt.Errorf("failed to marshal approval request: %v", err)
	}
	
	// Save the request
	requestKey := fmt.Sprintf("approval_request~%s", request.RequestID)
	if err := stub.PutState(requestKey, requestBytes); err != nil {
		return fmt.Errorf("failed to save approval request: %v", err)
	}
	
	// Create index entries
	if err := w.createApprovalIndexEntries(stub, request); err != nil {
		return fmt.Errorf("failed to create approval index entries: %v", err)
	}
	
	return nil
}

// getApprovalRequest retrieves an approval request by ID
func (w *ApprovalWorkflowManager) getApprovalRequest(stub shim.ChaincodeStubInterface, requestID string) (*RuleApprovalRequest, error) {
	requestKey := fmt.Sprintf("approval_request~%s", requestID)
	requestBytes, err := stub.GetState(requestKey)
	if err != nil {
		return nil, fmt.Errorf("failed to get approval request %s: %v", requestID, err)
	}
	
	if requestBytes == nil {
		return nil, fmt.Errorf("approval request %s not found", requestID)
	}
	
	var request RuleApprovalRequest
	if err := json.Unmarshal(requestBytes, &request); err != nil {
		return nil, fmt.Errorf("failed to unmarshal approval request: %v", err)
	}
	
	return &request, nil
}

// createApprovalIndexEntries creates composite key entries for efficient approval querying
func (w *ApprovalWorkflowManager) createApprovalIndexEntries(stub shim.ChaincodeStubInterface, request *RuleApprovalRequest) error {
	// Status index
	statusKey, err := stub.CreateCompositeKey("approval_status", []string{request.Status, request.RequestID})
	if err != nil {
		return fmt.Errorf("failed to create status composite key: %v", err)
	}
	if err := stub.PutState(statusKey, []byte{}); err != nil {
		return fmt.Errorf("failed to save status index: %v", err)
	}
	
	// Rule index
	ruleKey, err := stub.CreateCompositeKey("approval_rule", []string{request.RuleID, request.RequestID})
	if err != nil {
		return fmt.Errorf("failed to create rule composite key: %v", err)
	}
	if err := stub.PutState(ruleKey, []byte{}); err != nil {
		return fmt.Errorf("failed to save rule index: %v", err)
	}
	
	// Requester index
	requesterKey, err := stub.CreateCompositeKey("approval_requester", []string{request.RequestedBy, request.RequestID})
	if err != nil {
		return fmt.Errorf("failed to create requester composite key: %v", err)
	}
	if err := stub.PutState(requesterKey, []byte{}); err != nil {
		return fmt.Errorf("failed to save requester index: %v", err)
	}
	
	// Reviewer index (if reviewed)
	if request.ReviewedBy != "" {
		reviewerKey, err := stub.CreateCompositeKey("approval_reviewer", []string{request.ReviewedBy, request.RequestID})
		if err != nil {
			return fmt.Errorf("failed to create reviewer composite key: %v", err)
		}
		if err := stub.PutState(reviewerKey, []byte{}); err != nil {
			return fmt.Errorf("failed to save reviewer index: %v", err)
		}
	}
	
	return nil
}