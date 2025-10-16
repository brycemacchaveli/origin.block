package domain

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/hyperledger/fabric-chaincode-go/shim"
)

// FabricRuleRepository implements RuleRepository using Hyperledger Fabric state database
type FabricRuleRepository struct{}

// NewFabricRuleRepository creates a new Fabric-based rule repository
func NewFabricRuleRepository() *FabricRuleRepository {
	return &FabricRuleRepository{}
}

// GetRule retrieves a specific version of a rule
func (r *FabricRuleRepository) GetRule(stub shim.ChaincodeStubInterface, ruleID string, version string) (*ComplianceRule, error) {
	key := fmt.Sprintf("rule~%s~%s", ruleID, version)
	
	ruleBytes, err := stub.GetState(key)
	if err != nil {
		return nil, fmt.Errorf("failed to get rule %s version %s: %v", ruleID, version, err)
	}
	
	if ruleBytes == nil {
		return nil, fmt.Errorf("rule %s version %s not found", ruleID, version)
	}
	
	var rule ComplianceRule
	if err := json.Unmarshal(ruleBytes, &rule); err != nil {
		return nil, fmt.Errorf("failed to unmarshal rule %s version %s: %v", ruleID, version, err)
	}
	
	return &rule, nil
}

// GetLatestRule retrieves the latest version of a rule
func (r *FabricRuleRepository) GetLatestRule(stub shim.ChaincodeStubInterface, ruleID string) (*ComplianceRule, error) {
	// First, get the latest version info
	latestKey := fmt.Sprintf("rule_latest~%s", ruleID)
	versionBytes, err := stub.GetState(latestKey)
	if err != nil {
		return nil, fmt.Errorf("failed to get latest version for rule %s: %v", ruleID, err)
	}
	
	if versionBytes == nil {
		return nil, fmt.Errorf("rule %s not found", ruleID)
	}
	
	version := string(versionBytes)
	return r.GetRule(stub, ruleID, version)
}

// GetActiveRules retrieves all currently active rules
func (r *FabricRuleRepository) GetActiveRules(stub shim.ChaincodeStubInterface) ([]*ComplianceRule, error) {
	// Use composite key query to get all rules
	iterator, err := stub.GetStateByPartialCompositeKey("rule", []string{})
	if err != nil {
		return nil, fmt.Errorf("failed to get active rules: %v", err)
	}
	defer iterator.Close()
	
	var activeRules []*ComplianceRule
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate rules: %v", err)
		}
		
		var rule ComplianceRule
		if err := json.Unmarshal(response.Value, &rule); err != nil {
			continue // Skip malformed rules
		}
		
		if rule.IsActive() {
			activeRules = append(activeRules, &rule)
		}
	}
	
	return activeRules, nil
}

// GetRulesByDomain retrieves all rules applicable to a specific domain
func (r *FabricRuleRepository) GetRulesByDomain(stub shim.ChaincodeStubInterface, domain string) ([]*ComplianceRule, error) {
	// Use composite key query
	iterator, err := stub.GetStateByPartialCompositeKey("rule_domain", []string{domain})
	if err != nil {
		return nil, fmt.Errorf("failed to get rules by domain %s: %v", domain, err)
	}
	defer iterator.Close()
	
	var rules []*ComplianceRule
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate domain rules: %v", err)
		}
		
		// Extract rule ID from composite key
		_, compositeKeyParts, err := stub.SplitCompositeKey(response.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		
		ruleID := compositeKeyParts[1]
		rule, err := r.GetLatestRule(stub, ruleID)
		if err != nil {
			continue // Skip rules that can't be loaded
		}
		
		if rule.IsActive() {
			rules = append(rules, rule)
		}
	}
	
	return rules, nil
}

// GetRulesByEntityType retrieves all rules applicable to a specific entity type
func (r *FabricRuleRepository) GetRulesByEntityType(stub shim.ChaincodeStubInterface, entityType string) ([]*ComplianceRule, error) {
	// Use composite key query
	iterator, err := stub.GetStateByPartialCompositeKey("rule_entity", []string{entityType})
	if err != nil {
		return nil, fmt.Errorf("failed to get rules by entity type %s: %v", entityType, err)
	}
	defer iterator.Close()
	
	var rules []*ComplianceRule
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate entity rules: %v", err)
		}
		
		// Extract rule ID from composite key
		_, compositeKeyParts, err := stub.SplitCompositeKey(response.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		
		ruleID := compositeKeyParts[1]
		rule, err := r.GetLatestRule(stub, ruleID)
		if err != nil {
			continue // Skip rules that can't be loaded
		}
		
		if rule.IsActive() {
			rules = append(rules, rule)
		}
	}
	
	return rules, nil
}

// GetRulesByEvent retrieves all rules triggered by a specific event
func (r *FabricRuleRepository) GetRulesByEvent(stub shim.ChaincodeStubInterface, eventType string) ([]*ComplianceRule, error) {
	// Use composite key query
	iterator, err := stub.GetStateByPartialCompositeKey("rule_event", []string{eventType})
	if err != nil {
		return nil, fmt.Errorf("failed to get rules by event %s: %v", eventType, err)
	}
	defer iterator.Close()
	
	var rules []*ComplianceRule
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate event rules: %v", err)
		}
		
		// Extract rule ID from composite key
		_, compositeKeyParts, err := stub.SplitCompositeKey(response.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		
		ruleID := compositeKeyParts[1]
		rule, err := r.GetLatestRule(stub, ruleID)
		if err != nil {
			continue // Skip rules that can't be loaded
		}
		
		if rule.IsActive() {
			rules = append(rules, rule)
		}
	}
	
	return rules, nil
}

// SaveRule saves a new rule or updates an existing rule
func (r *FabricRuleRepository) SaveRule(stub shim.ChaincodeStubInterface, rule *ComplianceRule) error {
	// Validate rule before saving
	validationResults := rule.Validate()
	for _, result := range validationResults {
		if !result.IsValid {
			return fmt.Errorf("rule validation failed: %v", result.ErrorMessages)
		}
	}
	
	// Save the rule with version
	if err := r.SaveRuleVersion(stub, rule); err != nil {
		return err
	}
	
	// Update latest version pointer
	latestKey := rule.GetLatestVersionKey()
	if err := stub.PutState(latestKey, []byte(rule.Version)); err != nil {
		return fmt.Errorf("failed to update latest version pointer: %v", err)
	}
	
	// Create index entries for efficient querying
	if err := r.createIndexEntries(stub, rule); err != nil {
		return fmt.Errorf("failed to create index entries: %v", err)
	}
	
	return nil
}

// SaveRuleVersion saves a specific version of a rule
func (r *FabricRuleRepository) SaveRuleVersion(stub shim.ChaincodeStubInterface, rule *ComplianceRule) error {
	ruleBytes, err := json.Marshal(rule)
	if err != nil {
		return fmt.Errorf("failed to marshal rule: %v", err)
	}
	
	key := rule.GetCompositeKey()
	if err := stub.PutState(key, ruleBytes); err != nil {
		return fmt.Errorf("failed to save rule version: %v", err)
	}
	
	return nil
}

// createIndexEntries creates composite key entries for efficient querying
func (r *FabricRuleRepository) createIndexEntries(stub shim.ChaincodeStubInterface, rule *ComplianceRule) error {
	// Domain index
	if rule.AppliesToDomain != "" {
		domainKey, err := stub.CreateCompositeKey("rule_domain", []string{rule.AppliesToDomain, rule.RuleID})
		if err != nil {
			return fmt.Errorf("failed to create domain composite key: %v", err)
		}
		if err := stub.PutState(domainKey, []byte{}); err != nil {
			return fmt.Errorf("failed to save domain index: %v", err)
		}
	}
	
	// Entity type index
	if rule.AppliesToEntityType != "" {
		entityKey, err := stub.CreateCompositeKey("rule_entity", []string{rule.AppliesToEntityType, rule.RuleID})
		if err != nil {
			return fmt.Errorf("failed to create entity composite key: %v", err)
		}
		if err := stub.PutState(entityKey, []byte{}); err != nil {
			return fmt.Errorf("failed to save entity index: %v", err)
		}
	}
	
	// Event trigger index
	for _, event := range rule.TriggerEvents {
		eventKey, err := stub.CreateCompositeKey("rule_event", []string{event, rule.RuleID})
		if err != nil {
			return fmt.Errorf("failed to create event composite key: %v", err)
		}
		if err := stub.PutState(eventKey, []byte{}); err != nil {
			return fmt.Errorf("failed to save event index: %v", err)
		}
	}
	
	// Status index
	statusKey, err := stub.CreateCompositeKey("rule_status", []string{string(rule.Status), rule.RuleID})
	if err != nil {
		return fmt.Errorf("failed to create status composite key: %v", err)
	}
	if err := stub.PutState(statusKey, []byte{}); err != nil {
		return fmt.Errorf("failed to save status index: %v", err)
	}
	
	// Priority index
	priorityKey, err := stub.CreateCompositeKey("rule_priority", []string{string(rule.Priority), rule.RuleID})
	if err != nil {
		return fmt.Errorf("failed to create priority composite key: %v", err)
	}
	if err := stub.PutState(priorityKey, []byte{}); err != nil {
		return fmt.Errorf("failed to save priority index: %v", err)
	}
	
	return nil
}

// GetRulesByStatus retrieves all rules with a specific status
func (r *FabricRuleRepository) GetRulesByStatus(stub shim.ChaincodeStubInterface, status ComplianceRuleStatus) ([]*ComplianceRule, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("rule_status", []string{string(status)})
	if err != nil {
		return nil, fmt.Errorf("failed to get rules by status %s: %v", status, err)
	}
	defer iterator.Close()
	
	var rules []*ComplianceRule
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate status rules: %v", err)
		}
		
		// Extract rule ID from composite key
		_, compositeKeyParts, err := stub.SplitCompositeKey(response.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		
		ruleID := compositeKeyParts[1]
		rule, err := r.GetLatestRule(stub, ruleID)
		if err != nil {
			continue // Skip rules that can't be loaded
		}
		
		rules = append(rules, rule)
	}
	
	return rules, nil
}

// GetRulesByPriority retrieves all rules with a specific priority
func (r *FabricRuleRepository) GetRulesByPriority(stub shim.ChaincodeStubInterface, priority ComplianceRulePriority) ([]*ComplianceRule, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("rule_priority", []string{string(priority)})
	if err != nil {
		return nil, fmt.Errorf("failed to get rules by priority %s: %v", priority, err)
	}
	defer iterator.Close()
	
	var rules []*ComplianceRule
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate priority rules: %v", err)
		}
		
		// Extract rule ID from composite key
		_, compositeKeyParts, err := stub.SplitCompositeKey(response.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		
		ruleID := compositeKeyParts[1]
		rule, err := r.GetLatestRule(stub, ruleID)
		if err != nil {
			continue // Skip rules that can't be loaded
		}
		
		rules = append(rules, rule)
	}
	
	return rules, nil
}

// GetRuleHistory retrieves the version history of a rule
func (r *FabricRuleRepository) GetRuleHistory(stub shim.ChaincodeStubInterface, ruleID string) ([]*ComplianceRule, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("rule", []string{ruleID})
	if err != nil {
		return nil, fmt.Errorf("failed to get rule history for %s: %v", ruleID, err)
	}
	defer iterator.Close()
	
	var versions []*ComplianceRule
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate rule versions: %v", err)
		}
		
		var rule ComplianceRule
		if err := json.Unmarshal(response.Value, &rule); err != nil {
			continue // Skip malformed rules
		}
		
		versions = append(versions, &rule)
	}
	
	return versions, nil
}

// DeleteRule marks a rule as deprecated (soft delete)
func (r *FabricRuleRepository) DeleteRule(stub shim.ChaincodeStubInterface, ruleID string) error {
	rule, err := r.GetLatestRule(stub, ruleID)
	if err != nil {
		return fmt.Errorf("failed to get rule for deletion: %v", err)
	}
	
	// Mark as deprecated instead of hard delete
	rule.Status = RuleStatusDeprecated
	rule.LastModifiedDate = rule.LastModifiedDate
	
	return r.SaveRule(stub, rule)
}

// SearchRules performs a text search across rule names and descriptions
func (r *FabricRuleRepository) SearchRules(stub shim.ChaincodeStubInterface, searchTerm string) ([]*ComplianceRule, error) {
	// Get all active rules and filter by search term
	activeRules, err := r.GetActiveRules(stub)
	if err != nil {
		return nil, err
	}
	
	var matchingRules []*ComplianceRule
	searchTerm = strings.ToLower(searchTerm)
	
	for _, rule := range activeRules {
		if strings.Contains(strings.ToLower(rule.RuleName), searchTerm) ||
			strings.Contains(strings.ToLower(rule.RuleDescription), searchTerm) ||
			strings.Contains(strings.ToLower(rule.BusinessJustification), searchTerm) {
			matchingRules = append(matchingRules, rule)
		}
	}
	
	return matchingRules, nil
}