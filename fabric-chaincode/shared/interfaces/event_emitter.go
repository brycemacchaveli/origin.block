package interfaces

import "github.com/hyperledger/fabric-chaincode-go/shim"

// EventPayload represents the structure of an event payload
type EventPayload struct {
	EventType   string      `json:"eventType"`
	EntityID    string      `json:"entityID"`
	EntityType  string      `json:"entityType"`
	ActorID     string      `json:"actorID"`
	Timestamp   string      `json:"timestamp"`
	Data        interface{} `json:"data"`
	Metadata    map[string]string `json:"metadata,omitempty"`
}

// EventEmitter defines the interface for emitting blockchain events
type EventEmitter interface {
	// Emit a single event
	EmitEvent(stub shim.ChaincodeStubInterface, eventName string, payload EventPayload) error
	
	// Emit multiple events in batch
	EmitEvents(stub shim.ChaincodeStubInterface, events map[string]EventPayload) error
	
	// Create standardized event payload
	CreateEventPayload(eventType, entityID, entityType, actorID string, data interface{}) EventPayload
}

// EventListener defines the interface for handling incoming events
type EventListener interface {
	// Handle a single event
	HandleEvent(stub shim.ChaincodeStubInterface, eventName string, payload EventPayload) error
	
	// Get list of events this listener is interested in
	GetSubscribedEvents() []string
}