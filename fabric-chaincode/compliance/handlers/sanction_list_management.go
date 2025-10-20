package handlers

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/compliance/domain"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/config"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/services"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/utils"
)

// SanctionListManager handles comprehensive sanction list management
type SanctionListManager struct {
	persistenceService *services.PersistenceService
	eventEmitter       domain.EventEmitter
}

// NewSanctionListManager creates a new sanction list manager
func NewSanctionListManager(eventEmitter domain.EventEmitter) *SanctionListManager {
	return &SanctionListManager{
		persistenceService: services.NewPersistenceService(),
		eventEmitter:       eventEmitter,
	}
}

// SanctionListDefinition represents a comprehensive sanction list definition
type SanctionListDefinition struct {
	ListID          string                 `json:"listID"`
	ListName        string                 `json:"listName"`
	Source          string                 `json:"source"`
	SourceURL       string                 `json:"sourceURL,omitempty"`
	Description     string                 `json:"description"`
	ListType        SanctionListType       `json:"listType"`
	Jurisdiction    string                 `json:"jurisdiction"`
	IsActive        bool                   `json:"isActive"`
	AutoUpdate      bool                   `json:"autoUpdate"`
	UpdateFrequency string                 `json:"updateFrequency"` // DAILY, WEEKLY, MONTHLY
	LastUpdated     time.Time              `json:"lastUpdated"`
	NextUpdate      time.Time              `json:"nextUpdate"`
	EntryCount      int                    `json:"entryCount"`
	Version         string                 `json:"version"`
	Checksum        string                 `json:"checksum"`
	CreatedBy       string                 `json:"createdBy"`
	CreatedDate     time.Time              `json:"createdDate"`
	LastModifiedBy  string                 `json:"lastModifiedBy"`
	LastModifiedDate time.Time             `json:"lastModifiedDate"`
	Metadata        map[string]interface{} `json:"metadata,omitempty"`
}

// SanctionListType represents the type of sanction list
type SanctionListType string

const (
	SanctionListTypeSDN        SanctionListType = "SDN"         // Specially Designated Nationals
	SanctionListTypeSSI        SanctionListType = "SSI"         // Sectoral Sanctions Identifications
	SanctionListTypeFSE        SanctionListType = "FSE"         // Foreign Sanctions Evaders
	SanctionListTypeNS_MBS     SanctionListType = "NS_MBS"      // Non-SDN Menu-Based Sanctions
	SanctionListTypeUN         SanctionListType = "UN"          // UN Security Council
	SanctionListTypeEU         SanctionListType = "EU"          // European Union
	SanctionListTypeHMT        SanctionListType = "HMT"         // HM Treasury (UK)
	SanctionListTypeDFAT       SanctionListType = "DFAT"        // Australian DFAT
	SanctionListTypeCustom     SanctionListType = "CUSTOM"      // Custom internal lists
)

// ComprehensiveSanctionEntry represents a detailed sanction list entry
type ComprehensiveSanctionEntry struct {
	EntryID         string                 `json:"entryID"`
	ListID          string                 `json:"listID"`
	PrimaryName     string                 `json:"primaryName"`
	Aliases         []string               `json:"aliases"`
	EntityType      SanctionEntityType     `json:"entityType"`
	
	// Personal information (for individuals)
	FirstName       string                 `json:"firstName,omitempty"`
	MiddleName      string                 `json:"middleName,omitempty"`
	LastName        string                 `json:"lastName,omitempty"`
	DateOfBirth     *time.Time             `json:"dateOfBirth,omitempty"`
	PlaceOfBirth    string                 `json:"placeOfBirth,omitempty"`
	Nationality     []string               `json:"nationality,omitempty"`
	Gender          string                 `json:"gender,omitempty"`
	
	// Organization information (for entities)
	OrganizationType string                `json:"organizationType,omitempty"`
	
	// Common information
	Addresses       []SanctionAddress      `json:"addresses"`
	IdentificationDocs []IdentificationDoc `json:"identificationDocs"`
	
	// Sanction details
	SanctionType    string                 `json:"sanctionType"`
	SanctionReason  string                 `json:"sanctionReason"`
	SanctionDate    time.Time              `json:"sanctionDate"`
	ExpiryDate      *time.Time             `json:"expiryDate,omitempty"`
	
	// Administrative
	IsActive        bool                   `json:"isActive"`
	LastUpdated     time.Time              `json:"lastUpdated"`
	Version         string                 `json:"version"`
	SourceReference string                 `json:"sourceReference"`
	
	// Risk scoring
	RiskScore       float64                `json:"riskScore"`
	RiskCategory    string                 `json:"riskCategory"`
	
	// Additional metadata
	Programs        []string               `json:"programs,omitempty"`
	Remarks         string                 `json:"remarks,omitempty"`
	Metadata        map[string]interface{} `json:"metadata,omitempty"`
}

// SanctionEntityType represents the type of sanctioned entity
type SanctionEntityType string

const (
	EntityTypeIndividual   SanctionEntityType = "INDIVIDUAL"
	EntityTypeOrganization SanctionEntityType = "ORGANIZATION"
	EntityTypeVessel       SanctionEntityType = "VESSEL"
	EntityTypeAircraft     SanctionEntityType = "AIRCRAFT"
)

// SanctionAddress represents an address associated with a sanction entry
type SanctionAddress struct {
	AddressID   string `json:"addressID"`
	AddressType string `json:"addressType"` // PRIMARY, SECONDARY, BUSINESS, RESIDENCE
	Street      string `json:"street"`
	City        string `json:"city"`
	State       string `json:"state,omitempty"`
	PostalCode  string `json:"postalCode,omitempty"`
	Country     string `json:"country"`
	IsActive    bool   `json:"isActive"`
}

// IdentificationDoc represents identification documents
type IdentificationDoc struct {
	DocID       string `json:"docID"`
	DocType     string `json:"docType"` // PASSPORT, NATIONAL_ID, DRIVER_LICENSE, etc.
	DocNumber   string `json:"docNumber"`
	IssuingCountry string `json:"issuingCountry"`
	IssueDate   *time.Time `json:"issueDate,omitempty"`
	ExpiryDate  *time.Time `json:"expiryDate,omitempty"`
	IsActive    bool   `json:"isActive"`
}

// SanctionListUpdateRequest represents a request to update sanction lists
type SanctionListUpdateRequest struct {
	ListID      string                        `json:"listID"`
	UpdateType  SanctionUpdateType            `json:"updateType"`
	Entries     []ComprehensiveSanctionEntry  `json:"entries,omitempty"`
	Version     string                        `json:"version"`
	Checksum    string                        `json:"checksum"`
	UpdatedBy   string                        `json:"updatedBy"`
	UpdateNotes string                        `json:"updateNotes,omitempty"`
}

// SanctionUpdateType represents the type of sanction list update
type SanctionUpdateType string

const (
	UpdateTypeFull        SanctionUpdateType = "FULL_REPLACE"
	UpdateTypeIncremental SanctionUpdateType = "INCREMENTAL"
	UpdateTypeAdditions   SanctionUpdateType = "ADDITIONS_ONLY"
	UpdateTypeRemovals    SanctionUpdateType = "REMOVALS_ONLY"
)

// CreateSanctionList creates a new sanction list definition
func (m *SanctionListManager) CreateSanctionList(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var listDef SanctionListDefinition
	if err := json.Unmarshal([]byte(args[0]), &listDef); err != nil {
		return nil, fmt.Errorf("failed to parse sanction list definition: %v", err)
	}

	// Validate list definition
	if err := m.validateSanctionListDefinition(&listDef); err != nil {
		return nil, fmt.Errorf("invalid sanction list definition: %v", err)
	}

	// Generate list ID if not provided
	if listDef.ListID == "" {
		listDef.ListID = utils.GenerateID(config.SanctionListPrefix)
	}

	// Set timestamps
	now := time.Now()
	listDef.CreatedDate = now
	listDef.LastModifiedDate = now
	listDef.LastUpdated = now
	listDef.NextUpdate = m.calculateNextUpdate(listDef.UpdateFrequency, now)

	// Store sanction list definition
	listKey := fmt.Sprintf("SANCTION_LIST_%s", listDef.ListID)
	if err := m.persistenceService.Put(stub, listKey, &listDef); err != nil {
		return nil, fmt.Errorf("failed to store sanction list definition: %v", err)
	}

	// Create indexes
	if err := m.createSanctionListIndexes(stub, &listDef); err != nil {
		return nil, fmt.Errorf("failed to create indexes: %v", err)
	}

	// Record compliance event
	if err := m.recordSanctionListEvent(stub, "SANCTION_LIST_CREATED", &listDef, listDef.CreatedBy); err != nil {
		return nil, fmt.Errorf("failed to record event: %v", err)
	}

	return json.Marshal(&listDef)
}

// UpdateSanctionList updates an existing sanction list with new entries
func (m *SanctionListManager) UpdateSanctionList(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var updateReq SanctionListUpdateRequest
	if err := json.Unmarshal([]byte(args[0]), &updateReq); err != nil {
		return nil, fmt.Errorf("failed to parse sanction list update request: %v", err)
	}

	// Get existing list definition
	listKey := fmt.Sprintf("SANCTION_LIST_%s", updateReq.ListID)
	var listDef SanctionListDefinition
	if err := m.persistenceService.Get(stub, listKey, &listDef); err != nil {
		return nil, fmt.Errorf("sanction list not found: %v", err)
	}

	// Validate update request
	if err := m.validateSanctionListUpdate(&updateReq, &listDef); err != nil {
		return nil, fmt.Errorf("invalid update request: %v", err)
	}

	// Process update based on type
	updateResult, err := m.processSanctionListUpdate(stub, &updateReq, &listDef)
	if err != nil {
		return nil, fmt.Errorf("failed to process update: %v", err)
	}

	// Update list definition
	listDef.Version = updateReq.Version
	listDef.Checksum = updateReq.Checksum
	listDef.LastUpdated = time.Now()
	listDef.LastModifiedBy = updateReq.UpdatedBy
	listDef.LastModifiedDate = time.Now()
	listDef.NextUpdate = m.calculateNextUpdate(listDef.UpdateFrequency, time.Now())
	listDef.EntryCount = updateResult.TotalEntries

	// Store updated list definition
	if err := m.persistenceService.Put(stub, listKey, &listDef); err != nil {
		return nil, fmt.Errorf("failed to update sanction list definition: %v", err)
	}

	// Record compliance event
	if err := m.recordSanctionListEvent(stub, "SANCTION_LIST_UPDATED", &listDef, updateReq.UpdatedBy); err != nil {
		return nil, fmt.Errorf("failed to record event: %v", err)
	}

	return json.Marshal(updateResult)
}

// SanctionListUpdateResult represents the result of a sanction list update
type SanctionListUpdateResult struct {
	ListID         string    `json:"listID"`
	UpdateType     SanctionUpdateType `json:"updateType"`
	TotalEntries   int       `json:"totalEntries"`
	AddedEntries   int       `json:"addedEntries"`
	UpdatedEntries int       `json:"updatedEntries"`
	RemovedEntries int       `json:"removedEntries"`
	UpdateDate     time.Time `json:"updateDate"`
	ProcessingTime int64     `json:"processingTimeMs"`
	Errors         []string  `json:"errors,omitempty"`
}

// processSanctionListUpdate processes the sanction list update
func (m *SanctionListManager) processSanctionListUpdate(stub shim.ChaincodeStubInterface, updateReq *SanctionListUpdateRequest, listDef *SanctionListDefinition) (*SanctionListUpdateResult, error) {
	startTime := time.Now()
	
	result := &SanctionListUpdateResult{
		ListID:     updateReq.ListID,
		UpdateType: updateReq.UpdateType,
		UpdateDate: time.Now(),
		Errors:     []string{},
	}

	switch updateReq.UpdateType {
	case UpdateTypeFull:
		return m.processFullReplaceUpdate(stub, updateReq, result)
	case UpdateTypeIncremental:
		return m.processIncrementalUpdate(stub, updateReq, result)
	case UpdateTypeAdditions:
		return m.processAdditionsOnlyUpdate(stub, updateReq, result)
	case UpdateTypeRemovals:
		return m.processRemovalsOnlyUpdate(stub, updateReq, result)
	default:
		return nil, fmt.Errorf("unsupported update type: %s", updateReq.UpdateType)
	}

	result.ProcessingTime = time.Since(startTime).Milliseconds()
	return result, nil
}

// processFullReplaceUpdate replaces all entries in the sanction list
func (m *SanctionListManager) processFullReplaceUpdate(stub shim.ChaincodeStubInterface, updateReq *SanctionListUpdateRequest, result *SanctionListUpdateResult) (*SanctionListUpdateResult, error) {
	// Remove all existing entries
	if err := m.removeAllSanctionEntries(stub, updateReq.ListID); err != nil {
		return nil, fmt.Errorf("failed to remove existing entries: %v", err)
	}

	// Add all new entries
	addedCount := 0
	for _, entry := range updateReq.Entries {
		if err := m.addSanctionEntry(stub, &entry); err != nil {
			result.Errors = append(result.Errors, fmt.Sprintf("Failed to add entry %s: %v", entry.EntryID, err))
			continue
		}
		addedCount++
	}

	result.TotalEntries = addedCount
	result.AddedEntries = addedCount
	result.RemovedEntries = 0 // We don't track the count of removed entries in full replace

	return result, nil
}

// processIncrementalUpdate processes incremental updates (adds, updates, removes)
func (m *SanctionListManager) processIncrementalUpdate(stub shim.ChaincodeStubInterface, updateReq *SanctionListUpdateRequest, result *SanctionListUpdateResult) (*SanctionListUpdateResult, error) {
	addedCount := 0
	updatedCount := 0

	for _, entry := range updateReq.Entries {
		// Check if entry exists
		entryKey := fmt.Sprintf("SANCTION_ENTRY_%s_%s", updateReq.ListID, entry.EntryID)
		existingEntryBytes, err := stub.GetState(entryKey)
		
		if err != nil {
			result.Errors = append(result.Errors, fmt.Sprintf("Error checking entry %s: %v", entry.EntryID, err))
			continue
		}

		if existingEntryBytes == nil {
			// New entry - add it
			if err := m.addSanctionEntry(stub, &entry); err != nil {
				result.Errors = append(result.Errors, fmt.Sprintf("Failed to add entry %s: %v", entry.EntryID, err))
				continue
			}
			addedCount++
		} else {
			// Existing entry - update it
			if err := m.updateSanctionEntry(stub, &entry); err != nil {
				result.Errors = append(result.Errors, fmt.Sprintf("Failed to update entry %s: %v", entry.EntryID, err))
				continue
			}
			updatedCount++
		}
	}

	// Get total count
	totalCount, err := m.getSanctionEntryCount(stub, updateReq.ListID)
	if err != nil {
		return nil, fmt.Errorf("failed to get total entry count: %v", err)
	}

	result.TotalEntries = totalCount
	result.AddedEntries = addedCount
	result.UpdatedEntries = updatedCount

	return result, nil
}

// processAdditionsOnlyUpdate processes additions-only updates
func (m *SanctionListManager) processAdditionsOnlyUpdate(stub shim.ChaincodeStubInterface, updateReq *SanctionListUpdateRequest, result *SanctionListUpdateResult) (*SanctionListUpdateResult, error) {
	addedCount := 0

	for _, entry := range updateReq.Entries {
		// Check if entry already exists
		entryKey := fmt.Sprintf("SANCTION_ENTRY_%s_%s", updateReq.ListID, entry.EntryID)
		existingEntryBytes, err := stub.GetState(entryKey)
		
		if err != nil {
			result.Errors = append(result.Errors, fmt.Sprintf("Error checking entry %s: %v", entry.EntryID, err))
			continue
		}

		if existingEntryBytes != nil {
			result.Errors = append(result.Errors, fmt.Sprintf("Entry %s already exists, skipping", entry.EntryID))
			continue
		}

		// Add new entry
		if err := m.addSanctionEntry(stub, &entry); err != nil {
			result.Errors = append(result.Errors, fmt.Sprintf("Failed to add entry %s: %v", entry.EntryID, err))
			continue
		}
		addedCount++
	}

	// Get total count
	totalCount, err := m.getSanctionEntryCount(stub, updateReq.ListID)
	if err != nil {
		return nil, fmt.Errorf("failed to get total entry count: %v", err)
	}

	result.TotalEntries = totalCount
	result.AddedEntries = addedCount

	return result, nil
}

// processRemovalsOnlyUpdate processes removals-only updates
func (m *SanctionListManager) processRemovalsOnlyUpdate(stub shim.ChaincodeStubInterface, updateReq *SanctionListUpdateRequest, result *SanctionListUpdateResult) (*SanctionListUpdateResult, error) {
	removedCount := 0

	for _, entry := range updateReq.Entries {
		if err := m.removeSanctionEntry(stub, updateReq.ListID, entry.EntryID); err != nil {
			result.Errors = append(result.Errors, fmt.Sprintf("Failed to remove entry %s: %v", entry.EntryID, err))
			continue
		}
		removedCount++
	}

	// Get total count
	totalCount, err := m.getSanctionEntryCount(stub, updateReq.ListID)
	if err != nil {
		return nil, fmt.Errorf("failed to get total entry count: %v", err)
	}

	result.TotalEntries = totalCount
	result.RemovedEntries = removedCount

	return result, nil
}

// Helper methods for sanction entry management

func (m *SanctionListManager) addSanctionEntry(stub shim.ChaincodeStubInterface, entry *ComprehensiveSanctionEntry) error {
	// Set timestamps
	entry.LastUpdated = time.Now()
	entry.IsActive = true

	// Store entry
	entryKey := fmt.Sprintf("SANCTION_ENTRY_%s_%s", entry.ListID, entry.EntryID)
	if err := m.persistenceService.Put(stub, entryKey, entry); err != nil {
		return fmt.Errorf("failed to store sanction entry: %v", err)
	}

	// Create search indexes
	if err := m.createSanctionEntryIndexes(stub, entry); err != nil {
		return fmt.Errorf("failed to create entry indexes: %v", err)
	}

	return nil
}

func (m *SanctionListManager) updateSanctionEntry(stub shim.ChaincodeStubInterface, entry *ComprehensiveSanctionEntry) error {
	// Update timestamp
	entry.LastUpdated = time.Now()

	// Store updated entry
	entryKey := fmt.Sprintf("SANCTION_ENTRY_%s_%s", entry.ListID, entry.EntryID)
	if err := m.persistenceService.Put(stub, entryKey, entry); err != nil {
		return fmt.Errorf("failed to update sanction entry: %v", err)
	}

	// Update search indexes
	if err := m.updateSanctionEntryIndexes(stub, entry); err != nil {
		return fmt.Errorf("failed to update entry indexes: %v", err)
	}

	return nil
}

func (m *SanctionListManager) removeSanctionEntry(stub shim.ChaincodeStubInterface, listID, entryID string) error {
	entryKey := fmt.Sprintf("SANCTION_ENTRY_%s_%s", listID, entryID)
	
	// Get entry before deletion for index cleanup
	var entry ComprehensiveSanctionEntry
	if err := m.persistenceService.Get(stub, entryKey, &entry); err != nil {
		return fmt.Errorf("sanction entry not found: %v", err)
	}

	// Remove entry
	if err := stub.DelState(entryKey); err != nil {
		return fmt.Errorf("failed to delete sanction entry: %v", err)
	}

	// Remove indexes
	if err := m.removeSanctionEntryIndexes(stub, &entry); err != nil {
		return fmt.Errorf("failed to remove entry indexes: %v", err)
	}

	return nil
}

func (m *SanctionListManager) removeAllSanctionEntries(stub shim.ChaincodeStubInterface, listID string) error {
	// Get all entries for the list
	iterator, err := stub.GetStateByPartialCompositeKey("SANCTION_ENTRY", []string{listID})
	if err != nil {
		return fmt.Errorf("failed to get sanction entries: %v", err)
	}
	defer iterator.Close()

	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return fmt.Errorf("failed to iterate sanction entries: %v", err)
		}

		// Delete entry
		if err := stub.DelState(response.Key); err != nil {
			return fmt.Errorf("failed to delete entry %s: %v", response.Key, err)
		}
	}

	return nil
}

func (m *SanctionListManager) getSanctionEntryCount(stub shim.ChaincodeStubInterface, listID string) (int, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("SANCTION_ENTRY", []string{listID})
	if err != nil {
		return 0, fmt.Errorf("failed to get sanction entries: %v", err)
	}
	defer iterator.Close()

	count := 0
	for iterator.HasNext() {
		_, err := iterator.Next()
		if err != nil {
			return 0, fmt.Errorf("failed to iterate sanction entries: %v", err)
		}
		count++
	}

	return count, nil
}

// Index management methods

func (m *SanctionListManager) createSanctionListIndexes(stub shim.ChaincodeStubInterface, listDef *SanctionListDefinition) error {
	// Create index by source
	sourceKey, err := stub.CreateCompositeKey("SANCTION_LIST_BY_SOURCE", []string{listDef.Source, listDef.ListID})
	if err != nil {
		return fmt.Errorf("failed to create source index key: %v", err)
	}
	if err := stub.PutState(sourceKey, []byte(listDef.ListID)); err != nil {
		return fmt.Errorf("failed to create source index: %v", err)
	}

	// Create index by type
	typeKey, err := stub.CreateCompositeKey("SANCTION_LIST_BY_TYPE", []string{string(listDef.ListType), listDef.ListID})
	if err != nil {
		return fmt.Errorf("failed to create type index key: %v", err)
	}
	if err := stub.PutState(typeKey, []byte(listDef.ListID)); err != nil {
		return fmt.Errorf("failed to create type index: %v", err)
	}

	// Create index by jurisdiction
	jurisdictionKey, err := stub.CreateCompositeKey("SANCTION_LIST_BY_JURISDICTION", []string{listDef.Jurisdiction, listDef.ListID})
	if err != nil {
		return fmt.Errorf("failed to create jurisdiction index key: %v", err)
	}
	if err := stub.PutState(jurisdictionKey, []byte(listDef.ListID)); err != nil {
		return fmt.Errorf("failed to create jurisdiction index: %v", err)
	}

	return nil
}

func (m *SanctionListManager) createSanctionEntryIndexes(stub shim.ChaincodeStubInterface, entry *ComprehensiveSanctionEntry) error {
	// Create index by primary name
	nameKey, err := stub.CreateCompositeKey("SANCTION_ENTRY_BY_NAME", []string{strings.ToUpper(entry.PrimaryName), entry.ListID, entry.EntryID})
	if err != nil {
		return fmt.Errorf("failed to create name index key: %v", err)
	}
	if err := stub.PutState(nameKey, []byte(entry.EntryID)); err != nil {
		return fmt.Errorf("failed to create name index: %v", err)
	}

	// Create indexes for aliases
	for _, alias := range entry.Aliases {
		aliasKey, err := stub.CreateCompositeKey("SANCTION_ENTRY_BY_ALIAS", []string{strings.ToUpper(alias), entry.ListID, entry.EntryID})
		if err != nil {
			continue // Skip if key creation fails
		}
		stub.PutState(aliasKey, []byte(entry.EntryID))
	}

	// Create index by entity type
	entityTypeKey, err := stub.CreateCompositeKey("SANCTION_ENTRY_BY_ENTITY_TYPE", []string{string(entry.EntityType), entry.ListID, entry.EntryID})
	if err != nil {
		return fmt.Errorf("failed to create entity type index key: %v", err)
	}
	if err := stub.PutState(entityTypeKey, []byte(entry.EntryID)); err != nil {
		return fmt.Errorf("failed to create entity type index: %v", err)
	}

	return nil
}

func (m *SanctionListManager) updateSanctionEntryIndexes(stub shim.ChaincodeStubInterface, entry *ComprehensiveSanctionEntry) error {
	// For simplicity, remove old indexes and create new ones
	// In a production system, you might want to be more selective
	if err := m.removeSanctionEntryIndexes(stub, entry); err != nil {
		return err
	}
	return m.createSanctionEntryIndexes(stub, entry)
}

func (m *SanctionListManager) removeSanctionEntryIndexes(stub shim.ChaincodeStubInterface, entry *ComprehensiveSanctionEntry) error {
	// Remove name index
	nameKey, err := stub.CreateCompositeKey("SANCTION_ENTRY_BY_NAME", []string{strings.ToUpper(entry.PrimaryName), entry.ListID, entry.EntryID})
	if err == nil {
		stub.DelState(nameKey)
	}

	// Remove alias indexes
	for _, alias := range entry.Aliases {
		aliasKey, err := stub.CreateCompositeKey("SANCTION_ENTRY_BY_ALIAS", []string{strings.ToUpper(alias), entry.ListID, entry.EntryID})
		if err == nil {
			stub.DelState(aliasKey)
		}
	}

	// Remove entity type index
	entityTypeKey, err := stub.CreateCompositeKey("SANCTION_ENTRY_BY_ENTITY_TYPE", []string{string(entry.EntityType), entry.ListID, entry.EntryID})
	if err == nil {
		stub.DelState(entityTypeKey)
	}

	return nil
}

// Validation methods

func (m *SanctionListManager) validateSanctionListDefinition(listDef *SanctionListDefinition) error {
	if listDef.ListName == "" {
		return fmt.Errorf("list name is required")
	}

	if listDef.Source == "" {
		return fmt.Errorf("source is required")
	}

	if listDef.Jurisdiction == "" {
		return fmt.Errorf("jurisdiction is required")
	}

	if listDef.CreatedBy == "" {
		return fmt.Errorf("createdBy is required")
	}

	// Validate list type
	validTypes := []SanctionListType{
		SanctionListTypeSDN, SanctionListTypeSSI, SanctionListTypeFSE,
		SanctionListTypeNS_MBS, SanctionListTypeUN, SanctionListTypeEU,
		SanctionListTypeHMT, SanctionListTypeDFAT, SanctionListTypeCustom,
	}

	validType := false
	for _, validListType := range validTypes {
		if listDef.ListType == validListType {
			validType = true
			break
		}
	}

	if !validType {
		return fmt.Errorf("invalid list type: %s", listDef.ListType)
	}

	return nil
}

func (m *SanctionListManager) validateSanctionListUpdate(updateReq *SanctionListUpdateRequest, listDef *SanctionListDefinition) error {
	if updateReq.ListID == "" {
		return fmt.Errorf("listID is required")
	}

	if updateReq.UpdatedBy == "" {
		return fmt.Errorf("updatedBy is required")
	}

	if updateReq.Version == "" {
		return fmt.Errorf("version is required")
	}

	// Validate update type
	validUpdateTypes := []SanctionUpdateType{
		UpdateTypeFull, UpdateTypeIncremental, UpdateTypeAdditions, UpdateTypeRemovals,
	}

	validUpdateType := false
	for _, validType := range validUpdateTypes {
		if updateReq.UpdateType == validType {
			validUpdateType = true
			break
		}
	}

	if !validUpdateType {
		return fmt.Errorf("invalid update type: %s", updateReq.UpdateType)
	}

	// Validate entries if provided
	for i, entry := range updateReq.Entries {
		if err := m.validateSanctionEntry(&entry); err != nil {
			return fmt.Errorf("invalid entry at index %d: %v", i, err)
		}
	}

	return nil
}

func (m *SanctionListManager) validateSanctionEntry(entry *ComprehensiveSanctionEntry) error {
	if entry.EntryID == "" {
		return fmt.Errorf("entryID is required")
	}

	if entry.PrimaryName == "" {
		return fmt.Errorf("primaryName is required")
	}

	if entry.EntityType == "" {
		return fmt.Errorf("entityType is required")
	}

	// Validate entity type
	validEntityTypes := []SanctionEntityType{
		EntityTypeIndividual, EntityTypeOrganization, EntityTypeVessel, EntityTypeAircraft,
	}

	validEntityType := false
	for _, validType := range validEntityTypes {
		if entry.EntityType == validType {
			validEntityType = true
			break
		}
	}

	if !validEntityType {
		return fmt.Errorf("invalid entity type: %s", entry.EntityType)
	}

	return nil
}

// Utility methods

func (m *SanctionListManager) calculateNextUpdate(frequency string, lastUpdate time.Time) time.Time {
	switch strings.ToUpper(frequency) {
	case "DAILY":
		return lastUpdate.AddDate(0, 0, 1)
	case "WEEKLY":
		return lastUpdate.AddDate(0, 0, 7)
	case "MONTHLY":
		return lastUpdate.AddDate(0, 1, 0)
	default:
		return lastUpdate.AddDate(0, 1, 0) // Default to monthly
	}
}

func (m *SanctionListManager) recordSanctionListEvent(stub shim.ChaincodeStubInterface, eventType string, listDef *SanctionListDefinition, actorID string) error {
	if m.eventEmitter == nil {
		return nil // No event emitter configured
	}

	eventID := utils.GenerateID(config.ComplianceEventPrefix)
	
	event := &domain.ComplianceEvent{
		EventID:            eventID,
		Timestamp:          time.Now(),
		RuleID:             "SANCTION_LIST_MANAGEMENT_RULE",
		RuleVersion:        "1.0",
		AffectedEntityID:   listDef.ListID,
		AffectedEntityType: "SanctionList",
		EventType:          eventType,
		Severity:           domain.PriorityMedium,
		Details: map[string]interface{}{
			"listID":      listDef.ListID,
			"listName":    listDef.ListName,
			"source":      listDef.Source,
			"listType":    listDef.ListType,
			"entryCount":  listDef.EntryCount,
		},
		ActorID:          actorID,
		IsAlerted:        false,
		ResolutionStatus: "CLOSED",
	}
	
	return m.eventEmitter.EmitComplianceEvent(stub, event)
}

// Query methods

// GetSanctionList retrieves a sanction list definition
func (m *SanctionListManager) GetSanctionList(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	listID := args[0]
	listKey := fmt.Sprintf("SANCTION_LIST_%s", listID)

	var listDef SanctionListDefinition
	if err := m.persistenceService.Get(stub, listKey, &listDef); err != nil {
		return nil, fmt.Errorf("sanction list not found: %v", err)
	}

	return json.Marshal(&listDef)
}

// GetActiveSanctionLists retrieves all active sanction lists
func (m *SanctionListManager) GetActiveSanctionLists(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	iterator, err := stub.GetStateByPartialCompositeKey("SANCTION_LIST", []string{})
	if err != nil {
		return nil, fmt.Errorf("failed to get sanction lists: %v", err)
	}
	defer iterator.Close()

	var activeLists []SanctionListDefinition

	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate sanction lists: %v", err)
		}

		var listDef SanctionListDefinition
		if err := json.Unmarshal(response.Value, &listDef); err != nil {
			continue // Skip invalid entries
		}

		if listDef.IsActive {
			activeLists = append(activeLists, listDef)
		}
	}

	return json.Marshal(activeLists)
}

// SearchSanctionEntries searches for sanction entries by name
func (m *SanctionListManager) SearchSanctionEntries(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var searchReq struct {
		SearchTerm string `json:"searchTerm"`
		ListID     string `json:"listID,omitempty"`
		EntityType string `json:"entityType,omitempty"`
		Limit      int    `json:"limit,omitempty"`
	}

	if err := json.Unmarshal([]byte(args[0]), &searchReq); err != nil {
		return nil, fmt.Errorf("failed to parse search request: %v", err)
	}

	if searchReq.Limit == 0 {
		searchReq.Limit = 100 // Default limit
	}

	// Search by name (simplified implementation)
	searchTerm := strings.ToUpper(searchReq.SearchTerm)
	
	iterator, err := stub.GetStateByPartialCompositeKey("SANCTION_ENTRY_BY_NAME", []string{searchTerm})
	if err != nil {
		return nil, fmt.Errorf("failed to search sanction entries: %v", err)
	}
	defer iterator.Close()

	var results []ComprehensiveSanctionEntry
	count := 0

	for iterator.HasNext() && count < searchReq.Limit {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate search results: %v", err)
		}

		entryID := string(response.Value)
		
		// Extract listID from composite key
		_, keyParts, err := stub.SplitCompositeKey(response.Key)
		if err != nil || len(keyParts) < 2 {
			continue
		}
		
		listID := keyParts[1]
		
		// Filter by listID if specified
		if searchReq.ListID != "" && listID != searchReq.ListID {
			continue
		}

		// Get full entry
		entryKey := fmt.Sprintf("SANCTION_ENTRY_%s_%s", listID, entryID)
		var entry ComprehensiveSanctionEntry
		if err := m.persistenceService.Get(stub, entryKey, &entry); err != nil {
			continue // Skip if entry not found
		}

		// Filter by entity type if specified
		if searchReq.EntityType != "" && string(entry.EntityType) != searchReq.EntityType {
			continue
		}

		results = append(results, entry)
		count++
	}

	return json.Marshal(results)
}