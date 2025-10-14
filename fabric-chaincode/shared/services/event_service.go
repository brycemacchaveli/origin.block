package services

import (
	"encoding/json"
	"fmt"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/interfaces"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/utils"
)

// BaseEventService provides common event emission functionality
type BaseEventService struct{}

// NewBaseEventService creates a new base event service
func NewBaseEventService() *BaseEventService {
	return &BaseEventService{}
}

// EmitEvent emits a standardized event
func (es *BaseEventService) EmitEvent(stub shim.ChaincodeStubInterface, eventName string, payload interfaces.EventPayload) error {
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal event payload: %v", err)
	}
	
	if err := stub.SetEvent(eventName, payloadBytes); err != nil {
		return fmt.Errorf("failed to emit event %s: %v", eventName, err)
	}
	
	return nil
}

// CreateEventPayload creates a standardized event payload
func (es *BaseEventService) CreateEventPayload(eventType, entityID, entityType, actorID string, data interface{}) interfaces.EventPayload {
	return interfaces.EventPayload{
		EventType:  eventType,
		EntityID:   entityID,
		EntityType: entityType,
		ActorID:    actorID,
		Timestamp:  utils.GetCurrentTimeString(),
		Data:       data,
		Metadata:   make(map[string]string),
	}
}

// CreateEventPayloadWithMetadata creates a standardized event payload with metadata
func (es *BaseEventService) CreateEventPayloadWithMetadata(eventType, entityID, entityType, actorID string, data interface{}, metadata map[string]string) interfaces.EventPayload {
	return interfaces.EventPayload{
		EventType:  eventType,
		EntityID:   entityID,
		EntityType: entityType,
		ActorID:    actorID,
		Timestamp:  utils.GetCurrentTimeString(),
		Data:       data,
		Metadata:   metadata,
	}
}