package domain

import (
	"encoding/json"
	"fmt"

	"github.com/hyperledger/fabric-chaincode-go/shim"
)

// FabricEventEmitter implements EventEmitter using Hyperledger Fabric events
type FabricEventEmitter struct{}

// NewFabricEventEmitter creates a new Fabric-based event emitter
func NewFabricEventEmitter() *FabricEventEmitter {
	return &FabricEventEmitter{}
}

// EmitComplianceEvent emits a compliance event to the Fabric network
func (e *FabricEventEmitter) EmitComplianceEvent(stub shim.ChaincodeStubInterface, event *ComplianceEvent) error {
	// Save the event to state for persistence
	eventKey := fmt.Sprintf("compliance_event~%s", event.EventID)
	eventBytes, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal compliance event: %v", err)
	}
	
	if err := stub.PutState(eventKey, eventBytes); err != nil {
		return fmt.Errorf("failed to save compliance event: %v", err)
	}
	
	// Create index entries for efficient querying
	if err := e.createEventIndexEntries(stub, event); err != nil {
		return fmt.Errorf("failed to create event index entries: %v", err)
	}
	
	// Emit Fabric event for external listeners
	eventName := fmt.Sprintf("ComplianceEvent_%s", event.EventType)
	if err := stub.SetEvent(eventName, eventBytes); err != nil {
		return fmt.Errorf("failed to emit Fabric event: %v", err)
	}
	
	return nil
}

// EmitRuleExecutionEvent emits a rule execution event
func (e *FabricEventEmitter) EmitRuleExecutionEvent(stub shim.ChaincodeStubInterface, result *RuleExecutionResult) error {
	// Create a compliance event for the rule execution
	event := &ComplianceEvent{
		EventID:            fmt.Sprintf("rule_exec_%s", result.ExecutionID),
		Timestamp:          result.Timestamp,
		RuleID:             result.RuleID,
		EventType:          "RULE_EXECUTED",
		Severity:           PriorityMedium, // Default severity
		Details:            result.Details,
		ExecutionResult:    *result,
		ResolutionStatus:   "OPEN",
	}
	
	// Set severity based on execution result
	if !result.Success {
		event.Severity = PriorityHigh
		event.EventType = "RULE_EXECUTION_FAILED"
	} else if !result.Passed {
		event.Severity = PriorityHigh
		event.EventType = "RULE_VIOLATION_DETECTED"
		event.IsAlerted = true
	}
	
	return e.EmitComplianceEvent(stub, event)
}

// createEventIndexEntries creates composite key entries for efficient event querying
func (e *FabricEventEmitter) createEventIndexEntries(stub shim.ChaincodeStubInterface, event *ComplianceEvent) error {
	// Rule ID index
	if event.RuleID != "" {
		ruleKey, err := stub.CreateCompositeKey("event_rule", []string{event.RuleID, event.EventID})
		if err != nil {
			return fmt.Errorf("failed to create rule composite key: %v", err)
		}
		if err := stub.PutState(ruleKey, []byte{}); err != nil {
			return fmt.Errorf("failed to save rule index: %v", err)
		}
	}
	
	// Entity ID index
	if event.AffectedEntityID != "" {
		entityKey, err := stub.CreateCompositeKey("event_entity", []string{event.AffectedEntityID, event.EventID})
		if err != nil {
			return fmt.Errorf("failed to create entity composite key: %v", err)
		}
		if err := stub.PutState(entityKey, []byte{}); err != nil {
			return fmt.Errorf("failed to save entity index: %v", err)
		}
	}
	
	// Entity type index
	if event.AffectedEntityType != "" {
		entityTypeKey, err := stub.CreateCompositeKey("event_entity_type", []string{event.AffectedEntityType, event.EventID})
		if err != nil {
			return fmt.Errorf("failed to create entity type composite key: %v", err)
		}
		if err := stub.PutState(entityTypeKey, []byte{}); err != nil {
			return fmt.Errorf("failed to save entity type index: %v", err)
		}
	}
	
	// Event type index
	eventTypeKey, err := stub.CreateCompositeKey("event_type", []string{event.EventType, event.EventID})
	if err != nil {
		return fmt.Errorf("failed to create event type composite key: %v", err)
	}
	if err := stub.PutState(eventTypeKey, []byte{}); err != nil {
		return fmt.Errorf("failed to save event type index: %v", err)
	}
	
	// Severity index
	severityKey, err := stub.CreateCompositeKey("event_severity", []string{string(event.Severity), event.EventID})
	if err != nil {
		return fmt.Errorf("failed to create severity composite key: %v", err)
	}
	if err := stub.PutState(severityKey, []byte{}); err != nil {
		return fmt.Errorf("failed to save severity index: %v", err)
	}
	
	// Alert status index
	alertStatus := "false"
	if event.IsAlerted {
		alertStatus = "true"
	}
	alertKey, err := stub.CreateCompositeKey("event_alert", []string{alertStatus, event.EventID})
	if err != nil {
		return fmt.Errorf("failed to create alert composite key: %v", err)
	}
	if err := stub.PutState(alertKey, []byte{}); err != nil {
		return fmt.Errorf("failed to save alert index: %v", err)
	}
	
	// Resolution status index
	resolutionKey, err := stub.CreateCompositeKey("event_resolution", []string{event.ResolutionStatus, event.EventID})
	if err != nil {
		return fmt.Errorf("failed to create resolution composite key: %v", err)
	}
	if err := stub.PutState(resolutionKey, []byte{}); err != nil {
		return fmt.Errorf("failed to save resolution index: %v", err)
	}
	
	// Actor index
	if event.ActorID != "" {
		actorKey, err := stub.CreateCompositeKey("event_actor", []string{event.ActorID, event.EventID})
		if err != nil {
			return fmt.Errorf("failed to create actor composite key: %v", err)
		}
		if err := stub.PutState(actorKey, []byte{}); err != nil {
			return fmt.Errorf("failed to save actor index: %v", err)
		}
	}
	
	return nil
}

// GetComplianceEvent retrieves a compliance event by ID
func (e *FabricEventEmitter) GetComplianceEvent(stub shim.ChaincodeStubInterface, eventID string) (*ComplianceEvent, error) {
	eventKey := fmt.Sprintf("compliance_event~%s", eventID)
	eventBytes, err := stub.GetState(eventKey)
	if err != nil {
		return nil, fmt.Errorf("failed to get compliance event %s: %v", eventID, err)
	}
	
	if eventBytes == nil {
		return nil, fmt.Errorf("compliance event %s not found", eventID)
	}
	
	var event ComplianceEvent
	if err := json.Unmarshal(eventBytes, &event); err != nil {
		return nil, fmt.Errorf("failed to unmarshal compliance event: %v", err)
	}
	
	return &event, nil
}

// GetEventsByRule retrieves all events for a specific rule
func (e *FabricEventEmitter) GetEventsByRule(stub shim.ChaincodeStubInterface, ruleID string) ([]*ComplianceEvent, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("event_rule", []string{ruleID})
	if err != nil {
		return nil, fmt.Errorf("failed to get events by rule %s: %v", ruleID, err)
	}
	defer iterator.Close()
	
	var events []*ComplianceEvent
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate rule events: %v", err)
		}
		
		// Extract event ID from composite key
		_, compositeKeyParts, err := stub.SplitCompositeKey(response.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		
		eventID := compositeKeyParts[1]
		event, err := e.GetComplianceEvent(stub, eventID)
		if err != nil {
			continue // Skip events that can't be loaded
		}
		
		events = append(events, event)
	}
	
	return events, nil
}

// GetEventsByEntity retrieves all events for a specific entity
func (e *FabricEventEmitter) GetEventsByEntity(stub shim.ChaincodeStubInterface, entityID string) ([]*ComplianceEvent, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("event_entity", []string{entityID})
	if err != nil {
		return nil, fmt.Errorf("failed to get events by entity %s: %v", entityID, err)
	}
	defer iterator.Close()
	
	var events []*ComplianceEvent
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate entity events: %v", err)
		}
		
		// Extract event ID from composite key
		_, compositeKeyParts, err := stub.SplitCompositeKey(response.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		
		eventID := compositeKeyParts[1]
		event, err := e.GetComplianceEvent(stub, eventID)
		if err != nil {
			continue // Skip events that can't be loaded
		}
		
		events = append(events, event)
	}
	
	return events, nil
}

// GetEventsByType retrieves all events of a specific type
func (e *FabricEventEmitter) GetEventsByType(stub shim.ChaincodeStubInterface, eventType string) ([]*ComplianceEvent, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("event_type", []string{eventType})
	if err != nil {
		return nil, fmt.Errorf("failed to get events by type %s: %v", eventType, err)
	}
	defer iterator.Close()
	
	var events []*ComplianceEvent
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate type events: %v", err)
		}
		
		// Extract event ID from composite key
		_, compositeKeyParts, err := stub.SplitCompositeKey(response.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		
		eventID := compositeKeyParts[1]
		event, err := e.GetComplianceEvent(stub, eventID)
		if err != nil {
			continue // Skip events that can't be loaded
		}
		
		events = append(events, event)
	}
	
	return events, nil
}

// GetEventsBySeverity retrieves all events with a specific severity
func (e *FabricEventEmitter) GetEventsBySeverity(stub shim.ChaincodeStubInterface, severity ComplianceRulePriority) ([]*ComplianceEvent, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("event_severity", []string{string(severity)})
	if err != nil {
		return nil, fmt.Errorf("failed to get events by severity %s: %v", severity, err)
	}
	defer iterator.Close()
	
	var events []*ComplianceEvent
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate severity events: %v", err)
		}
		
		// Extract event ID from composite key
		_, compositeKeyParts, err := stub.SplitCompositeKey(response.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		
		eventID := compositeKeyParts[1]
		event, err := e.GetComplianceEvent(stub, eventID)
		if err != nil {
			continue // Skip events that can't be loaded
		}
		
		events = append(events, event)
	}
	
	return events, nil
}

// GetAlertedEvents retrieves all events that have been alerted
func (e *FabricEventEmitter) GetAlertedEvents(stub shim.ChaincodeStubInterface) ([]*ComplianceEvent, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("event_alert", []string{"true"})
	if err != nil {
		return nil, fmt.Errorf("failed to get alerted events: %v", err)
	}
	defer iterator.Close()
	
	var events []*ComplianceEvent
	
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate alerted events: %v", err)
		}
		
		// Extract event ID from composite key
		_, compositeKeyParts, err := stub.SplitCompositeKey(response.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		
		eventID := compositeKeyParts[1]
		event, err := e.GetComplianceEvent(stub, eventID)
		if err != nil {
			continue // Skip events that can't be loaded
		}
		
		events = append(events, event)
	}
	
	return events, nil
}

// AcknowledgeEvent marks an event as acknowledged
func (e *FabricEventEmitter) AcknowledgeEvent(stub shim.ChaincodeStubInterface, eventID string, acknowledgedBy string) error {
	event, err := e.GetComplianceEvent(stub, eventID)
	if err != nil {
		return fmt.Errorf("failed to get event for acknowledgment: %v", err)
	}
	
	// Update acknowledgment information
	event.AcknowledgedBy = acknowledgedBy
	now := event.Timestamp
	event.AcknowledgedDate = &now
	
	// Save updated event
	eventKey := fmt.Sprintf("compliance_event~%s", event.EventID)
	eventBytes, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal updated event: %v", err)
	}
	
	if err := stub.PutState(eventKey, eventBytes); err != nil {
		return fmt.Errorf("failed to save acknowledged event: %v", err)
	}
	
	return nil
}

// UpdateEventResolution updates the resolution status of an event
func (e *FabricEventEmitter) UpdateEventResolution(stub shim.ChaincodeStubInterface, eventID string, status string, notes string) error {
	event, err := e.GetComplianceEvent(stub, eventID)
	if err != nil {
		return fmt.Errorf("failed to get event for resolution update: %v", err)
	}
	
	// Update resolution information
	event.ResolutionStatus = status
	event.ResolutionNotes = notes
	
	// Save updated event
	eventKey := fmt.Sprintf("compliance_event~%s", event.EventID)
	eventBytes, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal updated event: %v", err)
	}
	
	if err := stub.PutState(eventKey, eventBytes); err != nil {
		return fmt.Errorf("failed to save resolved event: %v", err)
	}
	
	// Update resolution index
	resolutionKey, err := stub.CreateCompositeKey("event_resolution", []string{status, eventID})
	if err != nil {
		return fmt.Errorf("failed to create resolution composite key: %v", err)
	}
	if err := stub.PutState(resolutionKey, []byte{}); err != nil {
		return fmt.Errorf("failed to update resolution index: %v", err)
	}
	
	return nil
}