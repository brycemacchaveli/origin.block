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

// ViolationEscalationHandler handles compliance violation escalation workflows
type ViolationEscalationHandler struct {
	persistenceService *services.PersistenceService
	eventEmitter       domain.EventEmitter
}

// NewViolationEscalationHandler creates a new violation escalation handler
func NewViolationEscalationHandler(eventEmitter domain.EventEmitter) *ViolationEscalationHandler {
	return &ViolationEscalationHandler{
		persistenceService: services.NewPersistenceService(),
		eventEmitter:       eventEmitter,
	}
}

// EscalationLevel represents the level of escalation
type EscalationLevel string

const (
	EscalationLevelL1 EscalationLevel = "L1_ANALYST"      // First level analyst
	EscalationLevelL2 EscalationLevel = "L2_SENIOR"       // Senior analyst
	EscalationLevelL3 EscalationLevel = "L3_MANAGER"      // Compliance manager
	EscalationLevelL4 EscalationLevel = "L4_DIRECTOR"     // Compliance director
	EscalationLevelL5 EscalationLevel = "L5_EXECUTIVE"    // Executive level
)

// EscalationStatus represents the status of an escalation
type EscalationStatus string

const (
	EscalationStatusOpen       EscalationStatus = "OPEN"
	EscalationStatusAssigned   EscalationStatus = "ASSIGNED"
	EscalationStatusInProgress EscalationStatus = "IN_PROGRESS"
	EscalationStatusResolved   EscalationStatus = "RESOLVED"
	EscalationStatusClosed     EscalationStatus = "CLOSED"
	EscalationStatusEscalated  EscalationStatus = "ESCALATED"
)

// EscalationPriority represents the priority of an escalation
type EscalationPriority string

const (
	EscalationPriorityLow      EscalationPriority = "LOW"
	EscalationPriorityMedium   EscalationPriority = "MEDIUM"
	EscalationPriorityHigh     EscalationPriority = "HIGH"
	EscalationPriorityCritical EscalationPriority = "CRITICAL"
)

// ComplianceViolationEscalation represents a comprehensive compliance violation escalation
type ComplianceViolationEscalation struct {
	EscalationID       string                 `json:"escalationID"`
	ViolationID        string                 `json:"violationID"`
	ComplianceEventID  string                 `json:"complianceEventID"`
	
	// Violation details
	ViolationType      string                 `json:"violationType"`
	ViolationSeverity  domain.ComplianceRulePriority `json:"violationSeverity"`
	AffectedEntityID   string                 `json:"affectedEntityID"`
	AffectedEntityType string                 `json:"affectedEntityType"`
	
	// Escalation details
	CurrentLevel       EscalationLevel        `json:"currentLevel"`
	Status             EscalationStatus       `json:"status"`
	Priority           EscalationPriority     `json:"priority"`
	
	// Assignment and ownership
	AssignedTo         string                 `json:"assignedTo,omitempty"`
	AssignedBy         string                 `json:"assignedBy,omitempty"`
	AssignmentDate     *time.Time             `json:"assignmentDate,omitempty"`
	
	// Timing and SLA
	CreatedDate        time.Time              `json:"createdDate"`
	CreatedBy          string                 `json:"createdBy"`
	DueDate            time.Time              `json:"dueDate"`
	ResolutionDate     *time.Time             `json:"resolutionDate,omitempty"`
	SLABreached        bool                   `json:"slaBreached"`
	
	// Escalation history
	EscalationHistory  []EscalationHistoryEntry `json:"escalationHistory"`
	
	// Resolution details
	ResolutionSummary  string                 `json:"resolutionSummary,omitempty"`
	ResolutionActions  []ResolutionAction     `json:"resolutionActions"`
	ResolutionNotes    string                 `json:"resolutionNotes,omitempty"`
	ResolvedBy         string                 `json:"resolvedBy,omitempty"`
	
	// Communication and notifications
	Notifications      []EscalationNotification `json:"notifications"`
	Comments           []EscalationComment    `json:"comments"`
	
	// Risk assessment
	RiskScore          float64                `json:"riskScore"`
	BusinessImpact     string                 `json:"businessImpact"`
	RegulatoryImpact   string                 `json:"regulatoryImpact"`
	
	// Metadata
	Tags               []string               `json:"tags,omitempty"`
	Metadata           map[string]interface{} `json:"metadata,omitempty"`
}

// EscalationHistoryEntry represents an entry in the escalation history
type EscalationHistoryEntry struct {
	HistoryID      string           `json:"historyID"`
	Timestamp      time.Time        `json:"timestamp"`
	Action         string           `json:"action"`
	FromLevel      EscalationLevel  `json:"fromLevel,omitempty"`
	ToLevel        EscalationLevel  `json:"toLevel,omitempty"`
	FromStatus     EscalationStatus `json:"fromStatus,omitempty"`
	ToStatus       EscalationStatus `json:"toStatus,omitempty"`
	ActorID        string           `json:"actorID"`
	Reason         string           `json:"reason,omitempty"`
	Notes          string           `json:"notes,omitempty"`
}

// ResolutionAction represents an action taken to resolve the violation
type ResolutionAction struct {
	ActionID       string    `json:"actionID"`
	ActionType     string    `json:"actionType"`
	Description    string    `json:"description"`
	TakenBy        string    `json:"takenBy"`
	TakenDate      time.Time `json:"takenDate"`
	Status         string    `json:"status"`
	Evidence       string    `json:"evidence,omitempty"`
	FollowUpNeeded bool      `json:"followUpNeeded"`
	FollowUpDate   *time.Time `json:"followUpDate,omitempty"`
}

// EscalationNotification represents a notification sent during escalation
type EscalationNotification struct {
	NotificationID   string    `json:"notificationID"`
	NotificationType string    `json:"notificationType"`
	Recipient        string    `json:"recipient"`
	Channel          string    `json:"channel"` // EMAIL, SMS, SYSTEM
	SentDate         time.Time `json:"sentDate"`
	Status           string    `json:"status"`
	Message          string    `json:"message"`
}

// EscalationComment represents a comment on an escalation
type EscalationComment struct {
	CommentID   string    `json:"commentID"`
	AuthorID    string    `json:"authorID"`
	Timestamp   time.Time `json:"timestamp"`
	Comment     string    `json:"comment"`
	IsInternal  bool      `json:"isInternal"`
	Attachments []string  `json:"attachments,omitempty"`
}

// EscalationRequest represents a request to create an escalation
type EscalationRequest struct {
	ViolationID        string                        `json:"violationID"`
	ComplianceEventID  string                        `json:"complianceEventID"`
	ViolationType      string                        `json:"violationType"`
	ViolationSeverity  domain.ComplianceRulePriority `json:"violationSeverity"`
	AffectedEntityID   string                        `json:"affectedEntityID"`
	AffectedEntityType string                        `json:"affectedEntityType"`
	Priority           EscalationPriority            `json:"priority"`
	BusinessImpact     string                        `json:"businessImpact"`
	RegulatoryImpact   string                        `json:"regulatoryImpact"`
	InitialNotes       string                        `json:"initialNotes,omitempty"`
	CreatedBy          string                        `json:"createdBy"`
	Tags               []string                      `json:"tags,omitempty"`
	Metadata           map[string]interface{}        `json:"metadata,omitempty"`
}

// CreateEscalation creates a new compliance violation escalation
func (h *ViolationEscalationHandler) CreateEscalation(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req EscalationRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse escalation request: %v", err)
	}

	// Validate request
	if err := h.validateEscalationRequest(&req); err != nil {
		return nil, fmt.Errorf("invalid escalation request: %v", err)
	}

	// Generate escalation ID
	escalationID := utils.GenerateID(config.EscalationPrefix)

	// Determine initial escalation level and SLA
	initialLevel := h.determineInitialEscalationLevel(req.ViolationSeverity, req.Priority)
	dueDate := h.calculateSLADueDate(initialLevel, req.Priority)

	// Calculate risk score
	riskScore := h.calculateRiskScore(req.ViolationSeverity, req.Priority, req.BusinessImpact, req.RegulatoryImpact)

	// Create escalation
	escalation := &ComplianceViolationEscalation{
		EscalationID:       escalationID,
		ViolationID:        req.ViolationID,
		ComplianceEventID:  req.ComplianceEventID,
		ViolationType:      req.ViolationType,
		ViolationSeverity:  req.ViolationSeverity,
		AffectedEntityID:   req.AffectedEntityID,
		AffectedEntityType: req.AffectedEntityType,
		CurrentLevel:       initialLevel,
		Status:             EscalationStatusOpen,
		Priority:           req.Priority,
		CreatedDate:        time.Now(),
		CreatedBy:          req.CreatedBy,
		DueDate:            dueDate,
		SLABreached:        false,
		EscalationHistory:  []EscalationHistoryEntry{},
		ResolutionActions:  []ResolutionAction{},
		Notifications:      []EscalationNotification{},
		Comments:           []EscalationComment{},
		RiskScore:          riskScore,
		BusinessImpact:     req.BusinessImpact,
		RegulatoryImpact:   req.RegulatoryImpact,
		Tags:               req.Tags,
		Metadata:           req.Metadata,
	}

	// Add initial history entry
	initialHistory := EscalationHistoryEntry{
		HistoryID: utils.GenerateID("HIST"),
		Timestamp: time.Now(),
		Action:    "ESCALATION_CREATED",
		ToLevel:   initialLevel,
		ToStatus:  EscalationStatusOpen,
		ActorID:   req.CreatedBy,
		Reason:    "Initial escalation creation",
		Notes:     req.InitialNotes,
	}
	escalation.EscalationHistory = append(escalation.EscalationHistory, initialHistory)

	// Add initial comment if provided
	if req.InitialNotes != "" {
		initialComment := EscalationComment{
			CommentID:  utils.GenerateID("COMMENT"),
			AuthorID:   req.CreatedBy,
			Timestamp:  time.Now(),
			Comment:    req.InitialNotes,
			IsInternal: true,
		}
		escalation.Comments = append(escalation.Comments, initialComment)
	}

	// Store escalation
	escalationKey := fmt.Sprintf("ESCALATION_%s", escalationID)
	if err := h.persistenceService.Put(stub, escalationKey, escalation); err != nil {
		return nil, fmt.Errorf("failed to store escalation: %v", err)
	}

	// Create indexes
	if err := h.createEscalationIndexes(stub, escalation); err != nil {
		return nil, fmt.Errorf("failed to create indexes: %v", err)
	}

	// Send initial notifications
	if err := h.sendEscalationNotifications(stub, escalation, "ESCALATION_CREATED"); err != nil {
		return nil, fmt.Errorf("failed to send notifications: %v", err)
	}

	// Record compliance event
	if err := h.recordEscalationEvent(stub, escalation, "ESCALATION_CREATED", req.CreatedBy); err != nil {
		return nil, fmt.Errorf("failed to record event: %v", err)
	}

	return json.Marshal(escalation)
}

// AssignEscalation assigns an escalation to a specific person
func (h *ViolationEscalationHandler) AssignEscalation(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req struct {
		EscalationID string `json:"escalationID"`
		AssignedTo   string `json:"assignedTo"`
		AssignedBy   string `json:"assignedBy"`
		Notes        string `json:"notes,omitempty"`
	}

	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse assignment request: %v", err)
	}

	// Get existing escalation
	escalationKey := fmt.Sprintf("ESCALATION_%s", req.EscalationID)
	var escalation ComplianceViolationEscalation
	if err := h.persistenceService.Get(stub, escalationKey, &escalation); err != nil {
		return nil, fmt.Errorf("escalation not found: %v", err)
	}

	// Validate assignment
	if escalation.Status == EscalationStatusClosed || escalation.Status == EscalationStatusResolved {
		return nil, fmt.Errorf("cannot assign closed or resolved escalation")
	}

	// Update escalation
	now := time.Now()
	previousAssignee := escalation.AssignedTo
	escalation.AssignedTo = req.AssignedTo
	escalation.AssignedBy = req.AssignedBy
	escalation.AssignmentDate = &now
	escalation.Status = EscalationStatusAssigned

	// Add history entry
	historyEntry := EscalationHistoryEntry{
		HistoryID:  utils.GenerateID("HIST"),
		Timestamp:  now,
		Action:     "ESCALATION_ASSIGNED",
		FromStatus: escalation.Status,
		ToStatus:   EscalationStatusAssigned,
		ActorID:    req.AssignedBy,
		Reason:     fmt.Sprintf("Assigned to %s", req.AssignedTo),
		Notes:      req.Notes,
	}
	escalation.EscalationHistory = append(escalation.EscalationHistory, historyEntry)

	// Store updated escalation
	if err := h.persistenceService.Put(stub, escalationKey, &escalation); err != nil {
		return nil, fmt.Errorf("failed to update escalation: %v", err)
	}

	// Send assignment notifications
	if err := h.sendAssignmentNotifications(stub, &escalation, previousAssignee); err != nil {
		return nil, fmt.Errorf("failed to send notifications: %v", err)
	}

	// Record compliance event
	if err := h.recordEscalationEvent(stub, &escalation, "ESCALATION_ASSIGNED", req.AssignedBy); err != nil {
		return nil, fmt.Errorf("failed to record event: %v", err)
	}

	return json.Marshal(&escalation)
}

// EscalateToNextLevel escalates the violation to the next level
func (h *ViolationEscalationHandler) EscalateToNextLevel(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req struct {
		EscalationID string `json:"escalationID"`
		Reason       string `json:"reason"`
		Notes        string `json:"notes,omitempty"`
		EscalatedBy  string `json:"escalatedBy"`
	}

	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse escalation request: %v", err)
	}

	// Get existing escalation
	escalationKey := fmt.Sprintf("ESCALATION_%s", req.EscalationID)
	var escalation ComplianceViolationEscalation
	if err := h.persistenceService.Get(stub, escalationKey, &escalation); err != nil {
		return nil, fmt.Errorf("escalation not found: %v", err)
	}

	// Validate escalation
	if escalation.Status == EscalationStatusClosed || escalation.Status == EscalationStatusResolved {
		return nil, fmt.Errorf("cannot escalate closed or resolved escalation")
	}

	// Determine next level
	nextLevel, err := h.getNextEscalationLevel(escalation.CurrentLevel)
	if err != nil {
		return nil, fmt.Errorf("cannot escalate further: %v", err)
	}

	// Update escalation
	now := time.Now()
	previousLevel := escalation.CurrentLevel
	escalation.CurrentLevel = nextLevel
	escalation.Status = EscalationStatusEscalated
	escalation.AssignedTo = "" // Clear assignment for reassignment at new level
	escalation.AssignmentDate = nil
	
	// Update due date based on new level
	escalation.DueDate = h.calculateSLADueDate(nextLevel, escalation.Priority)

	// Add history entry
	historyEntry := EscalationHistoryEntry{
		HistoryID:  utils.GenerateID("HIST"),
		Timestamp:  now,
		Action:     "ESCALATION_LEVEL_INCREASED",
		FromLevel:  previousLevel,
		ToLevel:    nextLevel,
		FromStatus: escalation.Status,
		ToStatus:   EscalationStatusEscalated,
		ActorID:    req.EscalatedBy,
		Reason:     req.Reason,
		Notes:      req.Notes,
	}
	escalation.EscalationHistory = append(escalation.EscalationHistory, historyEntry)

	// Store updated escalation
	if err := h.persistenceService.Put(stub, escalationKey, &escalation); err != nil {
		return nil, fmt.Errorf("failed to update escalation: %v", err)
	}

	// Send escalation notifications
	if err := h.sendEscalationNotifications(stub, &escalation, "ESCALATION_LEVEL_INCREASED"); err != nil {
		return nil, fmt.Errorf("failed to send notifications: %v", err)
	}

	// Record compliance event
	if err := h.recordEscalationEvent(stub, &escalation, "ESCALATION_LEVEL_INCREASED", req.EscalatedBy); err != nil {
		return nil, fmt.Errorf("failed to record event: %v", err)
	}

	return json.Marshal(&escalation)
}

// ResolveEscalation resolves an escalation with resolution details
func (h *ViolationEscalationHandler) ResolveEscalation(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req struct {
		EscalationID      string             `json:"escalationID"`
		ResolutionSummary string             `json:"resolutionSummary"`
		ResolutionActions []ResolutionAction `json:"resolutionActions"`
		ResolutionNotes   string             `json:"resolutionNotes,omitempty"`
		ResolvedBy        string             `json:"resolvedBy"`
	}

	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse resolution request: %v", err)
	}

	// Get existing escalation
	escalationKey := fmt.Sprintf("ESCALATION_%s", req.EscalationID)
	var escalation ComplianceViolationEscalation
	if err := h.persistenceService.Get(stub, escalationKey, &escalation); err != nil {
		return nil, fmt.Errorf("escalation not found: %v", err)
	}

	// Validate resolution
	if escalation.Status == EscalationStatusClosed || escalation.Status == EscalationStatusResolved {
		return nil, fmt.Errorf("escalation is already resolved or closed")
	}

	// Update escalation
	now := time.Now()
	escalation.Status = EscalationStatusResolved
	escalation.ResolutionDate = &now
	escalation.ResolutionSummary = req.ResolutionSummary
	escalation.ResolutionActions = req.ResolutionActions
	escalation.ResolutionNotes = req.ResolutionNotes
	escalation.ResolvedBy = req.ResolvedBy

	// Add resolution action IDs if not provided
	for i := range escalation.ResolutionActions {
		if escalation.ResolutionActions[i].ActionID == "" {
			escalation.ResolutionActions[i].ActionID = utils.GenerateID("ACTION")
		}
		if escalation.ResolutionActions[i].TakenDate.IsZero() {
			escalation.ResolutionActions[i].TakenDate = now
		}
		if escalation.ResolutionActions[i].Status == "" {
			escalation.ResolutionActions[i].Status = "COMPLETED"
		}
	}

	// Add history entry
	historyEntry := EscalationHistoryEntry{
		HistoryID:  utils.GenerateID("HIST"),
		Timestamp:  now,
		Action:     "ESCALATION_RESOLVED",
		FromStatus: escalation.Status,
		ToStatus:   EscalationStatusResolved,
		ActorID:    req.ResolvedBy,
		Reason:     "Escalation resolved",
		Notes:      req.ResolutionSummary,
	}
	escalation.EscalationHistory = append(escalation.EscalationHistory, historyEntry)

	// Store updated escalation
	if err := h.persistenceService.Put(stub, escalationKey, &escalation); err != nil {
		return nil, fmt.Errorf("failed to update escalation: %v", err)
	}

	// Send resolution notifications
	if err := h.sendResolutionNotifications(stub, &escalation); err != nil {
		return nil, fmt.Errorf("failed to send notifications: %v", err)
	}

	// Record compliance event
	if err := h.recordEscalationEvent(stub, &escalation, "ESCALATION_RESOLVED", req.ResolvedBy); err != nil {
		return nil, fmt.Errorf("failed to record event: %v", err)
	}

	return json.Marshal(&escalation)
}

// AddComment adds a comment to an escalation
func (h *ViolationEscalationHandler) AddComment(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req struct {
		EscalationID string   `json:"escalationID"`
		Comment      string   `json:"comment"`
		AuthorID     string   `json:"authorID"`
		IsInternal   bool     `json:"isInternal"`
		Attachments  []string `json:"attachments,omitempty"`
	}

	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse comment request: %v", err)
	}

	// Get existing escalation
	escalationKey := fmt.Sprintf("ESCALATION_%s", req.EscalationID)
	var escalation ComplianceViolationEscalation
	if err := h.persistenceService.Get(stub, escalationKey, &escalation); err != nil {
		return nil, fmt.Errorf("escalation not found: %v", err)
	}

	// Create comment
	comment := EscalationComment{
		CommentID:   utils.GenerateID("COMMENT"),
		AuthorID:    req.AuthorID,
		Timestamp:   time.Now(),
		Comment:     req.Comment,
		IsInternal:  req.IsInternal,
		Attachments: req.Attachments,
	}

	// Add comment to escalation
	escalation.Comments = append(escalation.Comments, comment)

	// Store updated escalation
	if err := h.persistenceService.Put(stub, escalationKey, &escalation); err != nil {
		return nil, fmt.Errorf("failed to update escalation: %v", err)
	}

	// Send comment notifications if not internal
	if !req.IsInternal {
		if err := h.sendCommentNotifications(stub, &escalation, &comment); err != nil {
			return nil, fmt.Errorf("failed to send notifications: %v", err)
		}
	}

	return json.Marshal(&comment)
}

// Helper methods

func (h *ViolationEscalationHandler) validateEscalationRequest(req *EscalationRequest) error {
	if req.ViolationID == "" {
		return fmt.Errorf("violationID is required")
	}
	if req.ComplianceEventID == "" {
		return fmt.Errorf("complianceEventID is required")
	}
	if req.ViolationType == "" {
		return fmt.Errorf("violationType is required")
	}
	if req.AffectedEntityID == "" {
		return fmt.Errorf("affectedEntityID is required")
	}
	if req.AffectedEntityType == "" {
		return fmt.Errorf("affectedEntityType is required")
	}
	if req.CreatedBy == "" {
		return fmt.Errorf("createdBy is required")
	}

	// Validate priority
	validPriorities := []EscalationPriority{
		EscalationPriorityLow, EscalationPriorityMedium, EscalationPriorityHigh, EscalationPriorityCritical,
	}
	validPriority := false
	for _, priority := range validPriorities {
		if req.Priority == priority {
			validPriority = true
			break
		}
	}
	if !validPriority {
		return fmt.Errorf("invalid priority: %s", req.Priority)
	}

	return nil
}

func (h *ViolationEscalationHandler) determineInitialEscalationLevel(severity domain.ComplianceRulePriority, priority EscalationPriority) EscalationLevel {
	// Determine initial level based on severity and priority
	if severity == domain.PriorityCritical || priority == EscalationPriorityCritical {
		return EscalationLevelL3 // Start at manager level for critical issues
	} else if severity == domain.PriorityHigh || priority == EscalationPriorityHigh {
		return EscalationLevelL2 // Start at senior level for high priority
	}
	return EscalationLevelL1 // Start at analyst level for medium/low priority
}

func (h *ViolationEscalationHandler) calculateSLADueDate(level EscalationLevel, priority EscalationPriority) time.Time {
	now := time.Now()
	
	// Base SLA hours by level
	baseSLA := map[EscalationLevel]int{
		EscalationLevelL1: 24,  // 24 hours
		EscalationLevelL2: 48,  // 48 hours
		EscalationLevelL3: 72,  // 72 hours
		EscalationLevelL4: 120, // 5 days
		EscalationLevelL5: 240, // 10 days
	}
	
	// Priority multipliers
	priorityMultiplier := map[EscalationPriority]float64{
		EscalationPriorityCritical: 0.5, // Half the time for critical
		EscalationPriorityHigh:     0.75,
		EscalationPriorityMedium:   1.0,
		EscalationPriorityLow:      1.5,
	}
	
	baseHours := baseSLA[level]
	multiplier := priorityMultiplier[priority]
	finalHours := int(float64(baseHours) * multiplier)
	
	return now.Add(time.Duration(finalHours) * time.Hour)
}

func (h *ViolationEscalationHandler) calculateRiskScore(severity domain.ComplianceRulePriority, priority EscalationPriority, businessImpact, regulatoryImpact string) float64 {
	score := 0.0
	
	// Severity weight (40%)
	severityScore := map[domain.ComplianceRulePriority]float64{
		domain.PriorityCritical: 1.0,
		domain.PriorityHigh:     0.75,
		domain.PriorityMedium:   0.5,
		domain.PriorityLow:      0.25,
	}
	score += severityScore[severity] * 0.4
	
	// Priority weight (30%)
	priorityScore := map[EscalationPriority]float64{
		EscalationPriorityCritical: 1.0,
		EscalationPriorityHigh:     0.75,
		EscalationPriorityMedium:   0.5,
		EscalationPriorityLow:      0.25,
	}
	score += priorityScore[priority] * 0.3
	
	// Business impact weight (15%)
	businessScore := 0.5 // Default medium impact
	if strings.Contains(strings.ToUpper(businessImpact), "HIGH") || strings.Contains(strings.ToUpper(businessImpact), "CRITICAL") {
		businessScore = 1.0
	} else if strings.Contains(strings.ToUpper(businessImpact), "LOW") {
		businessScore = 0.25
	}
	score += businessScore * 0.15
	
	// Regulatory impact weight (15%)
	regulatoryScore := 0.5 // Default medium impact
	if strings.Contains(strings.ToUpper(regulatoryImpact), "HIGH") || strings.Contains(strings.ToUpper(regulatoryImpact), "CRITICAL") {
		regulatoryScore = 1.0
	} else if strings.Contains(strings.ToUpper(regulatoryImpact), "LOW") {
		regulatoryScore = 0.25
	}
	score += regulatoryScore * 0.15
	
	return score
}

func (h *ViolationEscalationHandler) getNextEscalationLevel(currentLevel EscalationLevel) (EscalationLevel, error) {
	levelOrder := []EscalationLevel{
		EscalationLevelL1,
		EscalationLevelL2,
		EscalationLevelL3,
		EscalationLevelL4,
		EscalationLevelL5,
	}
	
	for i, level := range levelOrder {
		if level == currentLevel {
			if i+1 < len(levelOrder) {
				return levelOrder[i+1], nil
			}
			return "", fmt.Errorf("already at highest escalation level")
		}
	}
	
	return "", fmt.Errorf("invalid current level: %s", currentLevel)
}

func (h *ViolationEscalationHandler) createEscalationIndexes(stub shim.ChaincodeStubInterface, escalation *ComplianceViolationEscalation) error {
	// Create index by status
	statusKey, err := stub.CreateCompositeKey("ESCALATION_BY_STATUS", []string{string(escalation.Status), escalation.EscalationID})
	if err != nil {
		return fmt.Errorf("failed to create status index key: %v", err)
	}
	if err := stub.PutState(statusKey, []byte(escalation.EscalationID)); err != nil {
		return fmt.Errorf("failed to create status index: %v", err)
	}

	// Create index by level
	levelKey, err := stub.CreateCompositeKey("ESCALATION_BY_LEVEL", []string{string(escalation.CurrentLevel), escalation.EscalationID})
	if err != nil {
		return fmt.Errorf("failed to create level index key: %v", err)
	}
	if err := stub.PutState(levelKey, []byte(escalation.EscalationID)); err != nil {
		return fmt.Errorf("failed to create level index: %v", err)
	}

	// Create index by assignee
	if escalation.AssignedTo != "" {
		assigneeKey, err := stub.CreateCompositeKey("ESCALATION_BY_ASSIGNEE", []string{escalation.AssignedTo, escalation.EscalationID})
		if err != nil {
			return fmt.Errorf("failed to create assignee index key: %v", err)
		}
		if err := stub.PutState(assigneeKey, []byte(escalation.EscalationID)); err != nil {
			return fmt.Errorf("failed to create assignee index: %v", err)
		}
	}

	// Create index by affected entity
	entityKey, err := stub.CreateCompositeKey("ESCALATION_BY_ENTITY", []string{escalation.AffectedEntityID, escalation.EscalationID})
	if err != nil {
		return fmt.Errorf("failed to create entity index key: %v", err)
	}
	if err := stub.PutState(entityKey, []byte(escalation.EscalationID)); err != nil {
		return fmt.Errorf("failed to create entity index: %v", err)
	}

	return nil
}

// Notification methods (simplified implementations)

func (h *ViolationEscalationHandler) sendEscalationNotifications(stub shim.ChaincodeStubInterface, escalation *ComplianceViolationEscalation, notificationType string) error {
	// In a real implementation, this would send actual notifications
	// For now, we'll just record the notification in the escalation
	
	notification := EscalationNotification{
		NotificationID:   utils.GenerateID("NOTIF"),
		NotificationType: notificationType,
		Recipient:        h.getNotificationRecipient(escalation.CurrentLevel),
		Channel:          "EMAIL",
		SentDate:         time.Now(),
		Status:           "SENT",
		Message:          fmt.Sprintf("Escalation %s: %s", escalation.EscalationID, notificationType),
	}
	
	escalation.Notifications = append(escalation.Notifications, notification)
	return nil
}

func (h *ViolationEscalationHandler) sendAssignmentNotifications(stub shim.ChaincodeStubInterface, escalation *ComplianceViolationEscalation, previousAssignee string) error {
	// Send notification to new assignee
	if escalation.AssignedTo != "" {
		notification := EscalationNotification{
			NotificationID:   utils.GenerateID("NOTIF"),
			NotificationType: "ESCALATION_ASSIGNED",
			Recipient:        escalation.AssignedTo,
			Channel:          "EMAIL",
			SentDate:         time.Now(),
			Status:           "SENT",
			Message:          fmt.Sprintf("You have been assigned escalation %s", escalation.EscalationID),
		}
		escalation.Notifications = append(escalation.Notifications, notification)
	}
	
	// Send notification to previous assignee if different
	if previousAssignee != "" && previousAssignee != escalation.AssignedTo {
		notification := EscalationNotification{
			NotificationID:   utils.GenerateID("NOTIF"),
			NotificationType: "ESCALATION_REASSIGNED",
			Recipient:        previousAssignee,
			Channel:          "EMAIL",
			SentDate:         time.Now(),
			Status:           "SENT",
			Message:          fmt.Sprintf("Escalation %s has been reassigned", escalation.EscalationID),
		}
		escalation.Notifications = append(escalation.Notifications, notification)
	}
	
	return nil
}

func (h *ViolationEscalationHandler) sendResolutionNotifications(stub shim.ChaincodeStubInterface, escalation *ComplianceViolationEscalation) error {
	// Send notification to creator and assignee
	recipients := []string{escalation.CreatedBy}
	if escalation.AssignedTo != "" && escalation.AssignedTo != escalation.CreatedBy {
		recipients = append(recipients, escalation.AssignedTo)
	}
	
	for _, recipient := range recipients {
		notification := EscalationNotification{
			NotificationID:   utils.GenerateID("NOTIF"),
			NotificationType: "ESCALATION_RESOLVED",
			Recipient:        recipient,
			Channel:          "EMAIL",
			SentDate:         time.Now(),
			Status:           "SENT",
			Message:          fmt.Sprintf("Escalation %s has been resolved", escalation.EscalationID),
		}
		escalation.Notifications = append(escalation.Notifications, notification)
	}
	
	return nil
}

func (h *ViolationEscalationHandler) sendCommentNotifications(stub shim.ChaincodeStubInterface, escalation *ComplianceViolationEscalation, comment *EscalationComment) error {
	// Send notification to assignee if different from comment author
	if escalation.AssignedTo != "" && escalation.AssignedTo != comment.AuthorID {
		notification := EscalationNotification{
			NotificationID:   utils.GenerateID("NOTIF"),
			NotificationType: "ESCALATION_COMMENT_ADDED",
			Recipient:        escalation.AssignedTo,
			Channel:          "EMAIL",
			SentDate:         time.Now(),
			Status:           "SENT",
			Message:          fmt.Sprintf("New comment added to escalation %s", escalation.EscalationID),
		}
		escalation.Notifications = append(escalation.Notifications, notification)
	}
	
	return nil
}

func (h *ViolationEscalationHandler) getNotificationRecipient(level EscalationLevel) string {
	// In a real implementation, this would look up the appropriate recipient
	// based on the escalation level and organizational structure
	recipients := map[EscalationLevel]string{
		EscalationLevelL1: "compliance-analysts@company.com",
		EscalationLevelL2: "senior-compliance@company.com",
		EscalationLevelL3: "compliance-manager@company.com",
		EscalationLevelL4: "compliance-director@company.com",
		EscalationLevelL5: "executive-team@company.com",
	}
	
	return recipients[level]
}

func (h *ViolationEscalationHandler) recordEscalationEvent(stub shim.ChaincodeStubInterface, escalation *ComplianceViolationEscalation, eventType, actorID string) error {
	if h.eventEmitter == nil {
		return nil // No event emitter configured
	}

	eventID := utils.GenerateID(config.ComplianceEventPrefix)
	
	event := &domain.ComplianceEvent{
		EventID:            eventID,
		Timestamp:          time.Now(),
		RuleID:             "ESCALATION_MANAGEMENT_RULE",
		RuleVersion:        "1.0",
		AffectedEntityID:   escalation.AffectedEntityID,
		AffectedEntityType: escalation.AffectedEntityType,
		EventType:          eventType,
		Severity:           h.mapPriorityToSeverity(escalation.Priority),
		Details: map[string]interface{}{
			"escalationID":    escalation.EscalationID,
			"violationID":     escalation.ViolationID,
			"currentLevel":    escalation.CurrentLevel,
			"status":          escalation.Status,
			"priority":        escalation.Priority,
			"riskScore":       escalation.RiskScore,
		},
		ActorID:          actorID,
		IsAlerted:        escalation.Priority == EscalationPriorityCritical,
		ResolutionStatus: string(escalation.Status),
	}
	
	return h.eventEmitter.EmitComplianceEvent(stub, event)
}

func (h *ViolationEscalationHandler) mapPriorityToSeverity(priority EscalationPriority) domain.ComplianceRulePriority {
	switch priority {
	case EscalationPriorityCritical:
		return domain.PriorityCritical
	case EscalationPriorityHigh:
		return domain.PriorityHigh
	case EscalationPriorityMedium:
		return domain.PriorityMedium
	default:
		return domain.PriorityLow
	}
}

// Query methods

// GetEscalation retrieves an escalation by ID
func (h *ViolationEscalationHandler) GetEscalation(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	escalationID := args[0]
	escalationKey := fmt.Sprintf("ESCALATION_%s", escalationID)

	var escalation ComplianceViolationEscalation
	if err := h.persistenceService.Get(stub, escalationKey, &escalation); err != nil {
		return nil, fmt.Errorf("escalation not found: %v", err)
	}

	return json.Marshal(&escalation)
}

// GetEscalationsByStatus retrieves escalations by status
func (h *ViolationEscalationHandler) GetEscalationsByStatus(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	status := args[0]
	
	iterator, err := stub.GetStateByPartialCompositeKey("ESCALATION_BY_STATUS", []string{status})
	if err != nil {
		return nil, fmt.Errorf("failed to get escalations by status: %v", err)
	}
	defer iterator.Close()

	var escalations []ComplianceViolationEscalation

	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate escalations: %v", err)
		}

		escalationID := string(response.Value)
		escalationKey := fmt.Sprintf("ESCALATION_%s", escalationID)
		
		var escalation ComplianceViolationEscalation
		if err := h.persistenceService.Get(stub, escalationKey, &escalation); err != nil {
			continue // Skip if escalation not found
		}

		escalations = append(escalations, escalation)
	}

	return json.Marshal(escalations)
}

// GetEscalationsByAssignee retrieves escalations assigned to a specific person
func (h *ViolationEscalationHandler) GetEscalationsByAssignee(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	assignee := args[0]
	
	iterator, err := stub.GetStateByPartialCompositeKey("ESCALATION_BY_ASSIGNEE", []string{assignee})
	if err != nil {
		return nil, fmt.Errorf("failed to get escalations by assignee: %v", err)
	}
	defer iterator.Close()

	var escalations []ComplianceViolationEscalation

	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate escalations: %v", err)
		}

		escalationID := string(response.Value)
		escalationKey := fmt.Sprintf("ESCALATION_%s", escalationID)
		
		var escalation ComplianceViolationEscalation
		if err := h.persistenceService.Get(stub, escalationKey, &escalation); err != nil {
			continue // Skip if escalation not found
		}

		escalations = append(escalations, escalation)
	}

	return json.Marshal(escalations)
}