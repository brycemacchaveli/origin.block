package services

import (
	"fmt"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/customer/domain"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/config"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/services"
)

// EventService handles event emission for customer operations
type EventService struct {
	*services.BaseEventService
}

// NewEventService creates a new event service
func NewEventService() *EventService {
	return &EventService{
		BaseEventService: services.NewBaseEventService(),
	}
}

// EmitCustomerCreated emits a customer created event
func (es *EventService) EmitCustomerCreated(stub shim.ChaincodeStubInterface, customer *domain.Customer, actorID string) error {
	metadata := map[string]string{
		"status": string(customer.Status),
		"email":  customer.Email,
	}
	
	payload := es.CreateEventPayloadWithMetadata(
		config.EventCustomerCreated,
		customer.CustomerID,
		"Customer",
		actorID,
		customer,
		metadata,
	)
	
	return es.EmitEvent(stub, config.EventCustomerCreated, payload)
}

// EmitCustomerUpdated emits a customer updated event
func (es *EventService) EmitCustomerUpdated(stub shim.ChaincodeStubInterface, customer *domain.Customer, actorID string) error {
	metadata := map[string]string{
		"status": string(customer.Status),
		"email":  customer.Email,
	}
	
	payload := es.CreateEventPayloadWithMetadata(
		config.EventCustomerUpdated,
		customer.CustomerID,
		"Customer",
		actorID,
		customer,
		metadata,
	)
	
	return es.EmitEvent(stub, config.EventCustomerUpdated, payload)
}

// EmitKYCInitiated emits a KYC initiated event
func (es *EventService) EmitKYCInitiated(stub shim.ChaincodeStubInterface, kycRecord *domain.KYCRecord, actorID string) error {
	metadata := map[string]string{
		"customerID": kycRecord.CustomerID,
		"status":     string(kycRecord.Status),
	}
	
	payload := es.CreateEventPayloadWithMetadata(
		"KYCInitiated",
		kycRecord.KYCID,
		"KYCRecord",
		actorID,
		kycRecord,
		metadata,
	)
	
	return es.EmitEvent(stub, "KYCInitiated", payload)
}

// EmitKYCVerified emits a KYC verified event
func (es *EventService) EmitKYCVerified(stub shim.ChaincodeStubInterface, kycRecord *domain.KYCRecord, actorID string) error {
	metadata := map[string]string{
		"customerID": kycRecord.CustomerID,
		"status":     string(kycRecord.Status),
	}
	
	payload := es.CreateEventPayloadWithMetadata(
		config.EventKYCVerified,
		kycRecord.KYCID,
		"KYCRecord",
		actorID,
		kycRecord,
		metadata,
	)
	
	return es.EmitEvent(stub, config.EventKYCVerified, payload)
}

// EmitKYCFailed emits a KYC failed event
func (es *EventService) EmitKYCFailed(stub shim.ChaincodeStubInterface, kycRecord *domain.KYCRecord, actorID string) error {
	metadata := map[string]string{
		"customerID": kycRecord.CustomerID,
		"status":     string(kycRecord.Status),
	}
	
	payload := es.CreateEventPayloadWithMetadata(
		config.EventKYCFailed,
		kycRecord.KYCID,
		"KYCRecord",
		actorID,
		kycRecord,
		metadata,
	)
	
	return es.EmitEvent(stub, config.EventKYCFailed, payload)
}

// EmitAMLCheckInitiated emits an AML check initiated event
func (es *EventService) EmitAMLCheckInitiated(stub shim.ChaincodeStubInterface, amlRecord *domain.AMLRecord, actorID string) error {
	metadata := map[string]string{
		"customerID": amlRecord.CustomerID,
		"status":     string(amlRecord.Status),
	}
	
	payload := es.CreateEventPayloadWithMetadata(
		"AMLCheckInitiated",
		amlRecord.AMLID,
		"AMLRecord",
		actorID,
		amlRecord,
		metadata,
	)
	
	return es.EmitEvent(stub, "AMLCheckInitiated", payload)
}

// EmitAMLCheckCompleted emits an AML check completed event
func (es *EventService) EmitAMLCheckCompleted(stub shim.ChaincodeStubInterface, amlRecord *domain.AMLRecord, actorID string) error {
	metadata := map[string]string{
		"customerID": amlRecord.CustomerID,
		"status":     string(amlRecord.Status),
		"riskScore":  fmt.Sprintf("%.2f", amlRecord.RiskScore),
	}
	
	payload := es.CreateEventPayloadWithMetadata(
		config.EventAMLCheckCompleted,
		amlRecord.AMLID,
		"AMLRecord",
		actorID,
		amlRecord,
		metadata,
	)
	
	return es.EmitEvent(stub, config.EventAMLCheckCompleted, payload)
}

// EmitAMLFlagged emits an AML flagged event
func (es *EventService) EmitAMLFlagged(stub shim.ChaincodeStubInterface, amlRecord *domain.AMLRecord, actorID string) error {
	metadata := map[string]string{
		"customerID": amlRecord.CustomerID,
		"status":     string(amlRecord.Status),
		"riskScore":  fmt.Sprintf("%.2f", amlRecord.RiskScore),
		"flagCount":  fmt.Sprintf("%d", len(amlRecord.Flags)),
	}
	
	payload := es.CreateEventPayloadWithMetadata(
		config.EventAMLFlagged,
		amlRecord.AMLID,
		"AMLRecord",
		actorID,
		amlRecord,
		metadata,
	)
	
	return es.EmitEvent(stub, config.EventAMLFlagged, payload)
}

