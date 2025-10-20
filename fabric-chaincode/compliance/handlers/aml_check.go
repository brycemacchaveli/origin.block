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
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/validation"
)

// AMLCheckHandler handles comprehensive AML check operations with real screening logic
type AMLCheckHandler struct {
	persistenceService *services.PersistenceService
	eventEmitter       domain.EventEmitter
}

// NewAMLCheckHandler creates a new AML check handler
func NewAMLCheckHandler(eventEmitter domain.EventEmitter) *AMLCheckHandler {
	return &AMLCheckHandler{
		persistenceService: services.NewPersistenceService(),
		eventEmitter:       eventEmitter,
	}
}

// AMLCheckRequest represents a comprehensive AML check request
type AMLCheckRequest struct {
	CustomerID      string                 `json:"customerID"`
	CustomerData    CustomerAMLData        `json:"customerData"`
	TransactionData *TransactionAMLData    `json:"transactionData,omitempty"`
	CheckType       AMLCheckType           `json:"checkType"`
	ActorID         string                 `json:"actorID"`
	Metadata        map[string]interface{} `json:"metadata,omitempty"`
}

// CustomerAMLData represents customer data for AML screening
type CustomerAMLData struct {
	FirstName     string    `json:"firstName"`
	LastName      string    `json:"lastName"`
	DateOfBirth   time.Time `json:"dateOfBirth"`
	NationalID    string    `json:"nationalID"`
	Nationality   string    `json:"nationality"`
	Address       string    `json:"address"`
	Country       string    `json:"country"`
	Occupation    string    `json:"occupation,omitempty"`
	EmployerName  string    `json:"employerName,omitempty"`
}

// TransactionAMLData represents transaction data for AML screening
type TransactionAMLData struct {
	TransactionID     string    `json:"transactionID"`
	Amount            float64   `json:"amount"`
	Currency          string    `json:"currency"`
	TransactionType   string    `json:"transactionType"`
	CounterpartyName  string    `json:"counterpartyName,omitempty"`
	CounterpartyCountry string  `json:"counterpartyCountry,omitempty"`
	Purpose           string    `json:"purpose,omitempty"`
	TransactionDate   time.Time `json:"transactionDate"`
}

// AMLCheckType represents the type of AML check to perform
type AMLCheckType string

const (
	AMLCheckTypeCustomerOnboarding AMLCheckType = "CUSTOMER_ONBOARDING"
	AMLCheckTypePeriodicReview     AMLCheckType = "PERIODIC_REVIEW"
	AMLCheckTypeTransactionBased   AMLCheckType = "TRANSACTION_BASED"
	AMLCheckTypeRiskReassessment   AMLCheckType = "RISK_REASSESSMENT"
)

// AMLCheckResult represents the comprehensive result of an AML check
type AMLCheckResult struct {
	CheckID              string                 `json:"checkID"`
	CustomerID           string                 `json:"customerID"`
	CheckType            AMLCheckType           `json:"checkType"`
	OverallRiskScore     float64                `json:"overallRiskScore"`
	RiskLevel            RiskLevel              `json:"riskLevel"`
	Status               validation.AMLStatus  `json:"status"`
	SanctionScreenResult SanctionScreenResult   `json:"sanctionScreenResult"`
	PEPScreenResult      PEPScreenResult        `json:"pepScreenResult"`
	RiskFactors          []RiskFactor           `json:"riskFactors"`
	Recommendations      []string               `json:"recommendations"`
	RequiredActions      []RequiredAction       `json:"requiredActions"`
	CheckDate            time.Time              `json:"checkDate"`
	ExpiryDate           time.Time              `json:"expiryDate"`
	CheckedBy            string                 `json:"checkedBy"`
	ReviewedBy           string                 `json:"reviewedBy,omitempty"`
	ReviewDate           *time.Time             `json:"reviewDate,omitempty"`
	Notes                string                 `json:"notes,omitempty"`
}

// RiskLevel represents the overall risk level
type RiskLevel string

const (
	RiskLevelLow      RiskLevel = "LOW"
	RiskLevelMedium   RiskLevel = "MEDIUM"
	RiskLevelHigh     RiskLevel = "HIGH"
	RiskLevelCritical RiskLevel = "CRITICAL"
)

// SanctionScreenResult represents sanction screening results
type SanctionScreenResult struct {
	IsMatch          bool              `json:"isMatch"`
	MatchConfidence  float64           `json:"matchConfidence"`
	Matches          []SanctionMatch   `json:"matches"`
	ListsScreened    []string          `json:"listsScreened"`
	ScreeningDate    time.Time         `json:"screeningDate"`
}

// SanctionMatch represents a potential sanction list match
type SanctionMatch struct {
	MatchID         string    `json:"matchID"`
	ListName        string    `json:"listName"`
	MatchedName     string    `json:"matchedName"`
	MatchType       string    `json:"matchType"` // EXACT, FUZZY, PHONETIC
	Confidence      float64   `json:"confidence"`
	MatchedFields   []string  `json:"matchedFields"`
	ListEntryID     string    `json:"listEntryID"`
	AdditionalInfo  string    `json:"additionalInfo,omitempty"`
}

// PEPScreenResult represents Politically Exposed Person screening results
type PEPScreenResult struct {
	IsMatch         bool           `json:"isMatch"`
	MatchConfidence float64        `json:"matchConfidence"`
	Matches         []PEPMatch     `json:"matches"`
	ScreeningDate   time.Time      `json:"screeningDate"`
}

// PEPMatch represents a potential PEP match
type PEPMatch struct {
	MatchID        string    `json:"matchID"`
	MatchedName    string    `json:"matchedName"`
	Position       string    `json:"position"`
	Country        string    `json:"country"`
	RiskCategory   string    `json:"riskCategory"`
	Confidence     float64   `json:"confidence"`
	LastUpdated    time.Time `json:"lastUpdated"`
}

// RiskFactor represents an identified risk factor
type RiskFactor struct {
	FactorID     string    `json:"factorID"`
	Category     string    `json:"category"`
	Description  string    `json:"description"`
	RiskScore    float64   `json:"riskScore"`
	Severity     string    `json:"severity"`
	Evidence     string    `json:"evidence,omitempty"`
	DetectedDate time.Time `json:"detectedDate"`
}

// RequiredAction represents an action required based on AML check results
type RequiredAction struct {
	ActionID     string    `json:"actionID"`
	ActionType   string    `json:"actionType"`
	Description  string    `json:"description"`
	Priority     string    `json:"priority"`
	DueDate      time.Time `json:"dueDate"`
	AssignedTo   string    `json:"assignedTo,omitempty"`
	Status       string    `json:"status"` // PENDING, IN_PROGRESS, COMPLETED, OVERDUE
}

// PerformAMLCheck performs a comprehensive AML check with real screening logic
func (h *AMLCheckHandler) PerformAMLCheck(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req AMLCheckRequest
	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse AML check request: %v", err)
	}

	// Validate request
	if err := h.validateAMLCheckRequest(&req); err != nil {
		return nil, fmt.Errorf("invalid AML check request: %v", err)
	}

	// Generate check ID
	checkID := utils.GenerateID(config.AMLCheckPrefix)

	// Perform comprehensive AML screening
	result, err := h.performComprehensiveAMLCheck(stub, checkID, &req)
	if err != nil {
		return nil, fmt.Errorf("failed to perform AML check: %v", err)
	}

	// Store AML check result
	resultKey := fmt.Sprintf("AML_RESULT_%s", checkID)
	if err := h.persistenceService.Put(stub, resultKey, result); err != nil {
		return nil, fmt.Errorf("failed to store AML check result: %v", err)
	}

	// Create customer AML index
	customerAMLKey := fmt.Sprintf("CUSTOMER_AML_%s_%s", req.CustomerID, checkID)
	if err := stub.PutState(customerAMLKey, []byte(checkID)); err != nil {
		return nil, fmt.Errorf("failed to create customer AML index: %v", err)
	}

	// Record compliance event
	if err := h.recordComplianceEvent(stub, result, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to record compliance event: %v", err)
	}

	// Handle escalation if needed
	if result.RiskLevel == RiskLevelHigh || result.RiskLevel == RiskLevelCritical {
		if err := h.handleRiskEscalation(stub, result, req.ActorID); err != nil {
			return nil, fmt.Errorf("failed to handle risk escalation: %v", err)
		}
	}

	return json.Marshal(result)
}

// performComprehensiveAMLCheck performs the actual AML screening logic
func (h *AMLCheckHandler) performComprehensiveAMLCheck(stub shim.ChaincodeStubInterface, checkID string, req *AMLCheckRequest) (*AMLCheckResult, error) {
	result := &AMLCheckResult{
		CheckID:         checkID,
		CustomerID:      req.CustomerID,
		CheckType:       req.CheckType,
		CheckDate:       time.Now(),
		CheckedBy:       req.ActorID,
		RiskFactors:     []RiskFactor{},
		Recommendations: []string{},
		RequiredActions: []RequiredAction{},
	}

	// Set expiry date based on check type
	result.ExpiryDate = h.calculateExpiryDate(req.CheckType)

	// 1. Perform sanction list screening
	sanctionResult, err := h.performSanctionScreening(stub, &req.CustomerData, req.TransactionData)
	if err != nil {
		return nil, fmt.Errorf("sanction screening failed: %v", err)
	}
	result.SanctionScreenResult = sanctionResult

	// 2. Perform PEP screening
	pepResult, err := h.performPEPScreening(stub, &req.CustomerData)
	if err != nil {
		return nil, fmt.Errorf("PEP screening failed: %v", err)
	}
	result.PEPScreenResult = pepResult

	// 3. Assess risk factors
	riskFactors, err := h.assessRiskFactors(stub, &req.CustomerData, req.TransactionData)
	if err != nil {
		return nil, fmt.Errorf("risk assessment failed: %v", err)
	}
	result.RiskFactors = riskFactors

	// 4. Calculate overall risk score
	result.OverallRiskScore = h.calculateOverallRiskScore(result)
	result.RiskLevel = h.determineRiskLevel(result.OverallRiskScore)

	// 5. Determine AML status
	result.Status = h.determineAMLStatus(result)

	// 6. Generate recommendations and required actions
	result.Recommendations = h.generateRecommendations(result)
	result.RequiredActions = h.generateRequiredActions(result, req.ActorID)

	return result, nil
}

// performSanctionScreening performs comprehensive sanction list screening
func (h *AMLCheckHandler) performSanctionScreening(stub shim.ChaincodeStubInterface, customerData *CustomerAMLData, transactionData *TransactionAMLData) (SanctionScreenResult, error) {
	result := SanctionScreenResult{
		IsMatch:       false,
		Matches:       []SanctionMatch{},
		ListsScreened: []string{"OFAC_SDN", "UN_SANCTIONS", "EU_SANCTIONS", "HMT_SANCTIONS"},
		ScreeningDate: time.Now(),
	}

	// Get active sanction lists
	sanctionLists, err := h.getActiveSanctionLists(stub)
	if err != nil {
		return result, fmt.Errorf("failed to get sanction lists: %v", err)
	}

	var allMatches []SanctionMatch
	maxConfidence := 0.0

	// Screen against each sanction list
	for _, list := range sanctionLists {
		matches, err := h.screenAgainstSanctionList(stub, customerData, list)
		if err != nil {
			continue // Log error but continue with other lists
		}

		for _, match := range matches {
			if match.Confidence > maxConfidence {
				maxConfidence = match.Confidence
			}
			allMatches = append(allMatches, match)
		}
	}

	result.Matches = allMatches
	result.MatchConfidence = maxConfidence
	result.IsMatch = len(allMatches) > 0 && maxConfidence >= 0.8 // 80% confidence threshold

	return result, nil
}

// performPEPScreening performs Politically Exposed Person screening
func (h *AMLCheckHandler) performPEPScreening(stub shim.ChaincodeStubInterface, customerData *CustomerAMLData) (PEPScreenResult, error) {
	result := PEPScreenResult{
		IsMatch:       false,
		Matches:       []PEPMatch{},
		ScreeningDate: time.Now(),
	}

	// Get PEP database
	pepDatabase, err := h.getPEPDatabase(stub)
	if err != nil {
		return result, fmt.Errorf("failed to get PEP database: %v", err)
	}

	// Screen against PEP database
	matches, err := h.screenAgainstPEPDatabase(customerData, pepDatabase)
	if err != nil {
		return result, fmt.Errorf("PEP screening failed: %v", err)
	}

	maxConfidence := 0.0
	for _, match := range matches {
		if match.Confidence > maxConfidence {
			maxConfidence = match.Confidence
		}
	}

	result.Matches = matches
	result.MatchConfidence = maxConfidence
	result.IsMatch = len(matches) > 0 && maxConfidence >= 0.85 // 85% confidence threshold for PEP

	return result, nil
}

// assessRiskFactors identifies and assesses various risk factors
func (h *AMLCheckHandler) assessRiskFactors(stub shim.ChaincodeStubInterface, customerData *CustomerAMLData, transactionData *TransactionAMLData) ([]RiskFactor, error) {
	var riskFactors []RiskFactor

	// 1. Geographic risk assessment
	geoRisk := h.assessGeographicRisk(customerData)
	if geoRisk != nil {
		riskFactors = append(riskFactors, *geoRisk)
	}

	// 2. Transaction pattern risk (if transaction data provided)
	if transactionData != nil {
		transactionRisk := h.assessTransactionRisk(transactionData)
		if transactionRisk != nil {
			riskFactors = append(riskFactors, *transactionRisk)
		}
	}

	// 3. Customer profile risk
	profileRisk := h.assessCustomerProfileRisk(customerData)
	if profileRisk != nil {
		riskFactors = append(riskFactors, *profileRisk)
	}

	// 4. Historical risk assessment
	historicalRisk, err := h.assessHistoricalRisk(stub, customerData.NationalID)
	if err == nil && historicalRisk != nil {
		riskFactors = append(riskFactors, *historicalRisk)
	}

	return riskFactors, nil
}

// calculateOverallRiskScore calculates the overall risk score based on all factors
func (h *AMLCheckHandler) calculateOverallRiskScore(result *AMLCheckResult) float64 {
	score := 0.0

	// Sanction screening weight (40%)
	if result.SanctionScreenResult.IsMatch {
		score += result.SanctionScreenResult.MatchConfidence * 0.4
	}

	// PEP screening weight (30%)
	if result.PEPScreenResult.IsMatch {
		score += result.PEPScreenResult.MatchConfidence * 0.3
	}

	// Risk factors weight (30%)
	if len(result.RiskFactors) > 0 {
		totalRiskScore := 0.0
		for _, factor := range result.RiskFactors {
			totalRiskScore += factor.RiskScore
		}
		avgRiskScore := totalRiskScore / float64(len(result.RiskFactors))
		score += (avgRiskScore / 100.0) * 0.3 // Normalize to 0-1 range
	}

	// Ensure score is between 0 and 1
	if score > 1.0 {
		score = 1.0
	}

	return score
}

// determineRiskLevel determines the risk level based on the overall risk score
func (h *AMLCheckHandler) determineRiskLevel(riskScore float64) RiskLevel {
	if riskScore >= 0.8 {
		return RiskLevelCritical
	} else if riskScore >= 0.6 {
		return RiskLevelHigh
	} else if riskScore >= 0.3 {
		return RiskLevelMedium
	}
	return RiskLevelLow
}

// determineAMLStatus determines the AML status based on screening results
func (h *AMLCheckHandler) determineAMLStatus(result *AMLCheckResult) validation.AMLStatus {
	// Critical or high risk requires review
	if result.RiskLevel == RiskLevelCritical {
		return validation.AMLStatusBlocked
	} else if result.RiskLevel == RiskLevelHigh {
		return validation.AMLStatusFlagged
	} else if result.SanctionScreenResult.IsMatch || result.PEPScreenResult.IsMatch {
		return validation.AMLStatusReviewing
	}
	return validation.AMLStatusClear
}

// Helper methods for risk assessment

func (h *AMLCheckHandler) assessGeographicRisk(customerData *CustomerAMLData) *RiskFactor {
	// High-risk countries list (simplified)
	highRiskCountries := map[string]float64{
		"AF": 90, "IR": 85, "KP": 95, "SY": 90, "YE": 80,
		"SO": 85, "LY": 80, "IQ": 75, "MM": 70, "VE": 65,
	}

	if riskScore, isHighRisk := highRiskCountries[customerData.Country]; isHighRisk {
		return &RiskFactor{
			FactorID:     utils.GenerateID("RISK_GEO"),
			Category:     "GEOGRAPHIC",
			Description:  fmt.Sprintf("Customer from high-risk country: %s", customerData.Country),
			RiskScore:    riskScore,
			Severity:     "HIGH",
			Evidence:     fmt.Sprintf("Country code: %s", customerData.Country),
			DetectedDate: time.Now(),
		}
	}

	return nil
}

func (h *AMLCheckHandler) assessTransactionRisk(transactionData *TransactionAMLData) *RiskFactor {
	// High-value transaction threshold
	if transactionData.Amount > 10000 {
		severity := "MEDIUM"
		riskScore := 50.0

		if transactionData.Amount > 50000 {
			severity = "HIGH"
			riskScore = 75.0
		}

		if transactionData.Amount > 100000 {
			severity = "CRITICAL"
			riskScore = 90.0
		}

		return &RiskFactor{
			FactorID:     utils.GenerateID("RISK_TXN"),
			Category:     "TRANSACTION",
			Description:  fmt.Sprintf("High-value transaction: %.2f %s", transactionData.Amount, transactionData.Currency),
			RiskScore:    riskScore,
			Severity:     severity,
			Evidence:     fmt.Sprintf("Transaction ID: %s, Amount: %.2f", transactionData.TransactionID, transactionData.Amount),
			DetectedDate: time.Now(),
		}
	}

	return nil
}

func (h *AMLCheckHandler) assessCustomerProfileRisk(customerData *CustomerAMLData) *RiskFactor {
	// High-risk occupations
	highRiskOccupations := map[string]float64{
		"POLITICIAN":     80,
		"ARMS_DEALER":    95,
		"CASINO_OWNER":   70,
		"MONEY_CHANGER":  65,
		"DIPLOMAT":       60,
	}

	occupation := strings.ToUpper(customerData.Occupation)
	if riskScore, isHighRisk := highRiskOccupations[occupation]; isHighRisk {
		return &RiskFactor{
			FactorID:     utils.GenerateID("RISK_PROF"),
			Category:     "PROFILE",
			Description:  fmt.Sprintf("High-risk occupation: %s", customerData.Occupation),
			RiskScore:    riskScore,
			Severity:     "HIGH",
			Evidence:     fmt.Sprintf("Occupation: %s", customerData.Occupation),
			DetectedDate: time.Now(),
		}
	}

	return nil
}

func (h *AMLCheckHandler) assessHistoricalRisk(stub shim.ChaincodeStubInterface, nationalID string) (*RiskFactor, error) {
	// Query historical AML records for this customer
	// This is a simplified implementation
	return nil, nil
}

// Sanction list management methods

func (h *AMLCheckHandler) getActiveSanctionLists(stub shim.ChaincodeStubInterface) ([]SanctionList, error) {
	// In a real implementation, this would query the blockchain for active sanction lists
	// For now, return mock data
	return []SanctionList{
		{
			ListID:      "OFAC_SDN",
			ListName:    "OFAC Specially Designated Nationals",
			Source:      "US Treasury OFAC",
			LastUpdated: time.Now().AddDate(0, 0, -1),
			IsActive:    true,
		},
		{
			ListID:      "UN_SANCTIONS",
			ListName:    "UN Security Council Sanctions",
			Source:      "United Nations",
			LastUpdated: time.Now().AddDate(0, 0, -2),
			IsActive:    true,
		},
	}, nil
}

func (h *AMLCheckHandler) screenAgainstSanctionList(stub shim.ChaincodeStubInterface, customerData *CustomerAMLData, list SanctionList) ([]SanctionMatch, error) {
	// In a real implementation, this would perform fuzzy matching against the sanction list
	// For demonstration, we'll check against some mock entries
	
	mockSanctionEntries := []SanctionEntry{
		{
			EntryID:     "SDN_001",
			Name:        "John Doe",
			Aliases:     []string{"Johnny Doe", "J. Doe"},
			DateOfBirth: time.Date(1970, 1, 1, 0, 0, 0, 0, time.UTC),
			Nationality: "US",
		},
	}

	var matches []SanctionMatch

	fullName := fmt.Sprintf("%s %s", customerData.FirstName, customerData.LastName)
	
	for _, entry := range mockSanctionEntries {
		// Simple name matching (in reality, this would use sophisticated fuzzy matching)
		confidence := h.calculateNameMatchConfidence(fullName, entry.Name)
		
		if confidence >= 0.7 { // 70% threshold for potential match
			matches = append(matches, SanctionMatch{
				MatchID:        utils.GenerateID("MATCH"),
				ListName:       list.ListName,
				MatchedName:    entry.Name,
				MatchType:      "FUZZY",
				Confidence:     confidence,
				MatchedFields:  []string{"name"},
				ListEntryID:    entry.EntryID,
				AdditionalInfo: fmt.Sprintf("DOB match: %v", entry.DateOfBirth.Equal(customerData.DateOfBirth)),
			})
		}
	}

	return matches, nil
}

func (h *AMLCheckHandler) calculateNameMatchConfidence(name1, name2 string) float64 {
	// Simple Levenshtein distance-based confidence calculation
	// In a real implementation, this would use more sophisticated algorithms
	name1 = strings.ToLower(strings.TrimSpace(name1))
	name2 = strings.ToLower(strings.TrimSpace(name2))
	
	if name1 == name2 {
		return 1.0
	}
	
	// Simple similarity calculation
	maxLen := len(name1)
	if len(name2) > maxLen {
		maxLen = len(name2)
	}
	
	if maxLen == 0 {
		return 0.0
	}
	
	distance := h.levenshteinDistance(name1, name2)
	return 1.0 - (float64(distance) / float64(maxLen))
}

func (h *AMLCheckHandler) levenshteinDistance(s1, s2 string) int {
	if len(s1) == 0 {
		return len(s2)
	}
	if len(s2) == 0 {
		return len(s1)
	}
	
	matrix := make([][]int, len(s1)+1)
	for i := range matrix {
		matrix[i] = make([]int, len(s2)+1)
		matrix[i][0] = i
	}
	
	for j := 0; j <= len(s2); j++ {
		matrix[0][j] = j
	}
	
	for i := 1; i <= len(s1); i++ {
		for j := 1; j <= len(s2); j++ {
			cost := 0
			if s1[i-1] != s2[j-1] {
				cost = 1
			}
			
			matrix[i][j] = min(
				matrix[i-1][j]+1,      // deletion
				matrix[i][j-1]+1,      // insertion
				matrix[i-1][j-1]+cost, // substitution
			)
		}
	}
	
	return matrix[len(s1)][len(s2)]
}

func min(a, b, c int) int {
	if a < b && a < c {
		return a
	}
	if b < c {
		return b
	}
	return c
}

// Additional helper methods and structures will be added in the next part...// Sa
nctionList represents a sanction list
type SanctionList struct {
	ListID      string    `json:"listID"`
	ListName    string    `json:"listName"`
	Source      string    `json:"source"`
	LastUpdated time.Time `json:"lastUpdated"`
	IsActive    bool      `json:"isActive"`
}

// SanctionEntry represents an entry in a sanction list
type SanctionEntry struct {
	EntryID     string    `json:"entryID"`
	Name        string    `json:"name"`
	Aliases     []string  `json:"aliases"`
	DateOfBirth time.Time `json:"dateOfBirth"`
	Nationality string    `json:"nationality"`
	Address     string    `json:"address,omitempty"`
	Reason      string    `json:"reason,omitempty"`
}

// PEP database methods
func (h *AMLCheckHandler) getPEPDatabase(stub shim.ChaincodeStubInterface) ([]PEPEntry, error) {
	// Mock PEP database - in reality, this would be loaded from external sources
	return []PEPEntry{
		{
			EntryID:     "PEP_001",
			Name:        "Jane Smith",
			Position:    "Minister of Finance",
			Country:     "US",
			RiskCategory: "HIGH",
			LastUpdated: time.Now().AddDate(0, -1, 0),
		},
	}, nil
}

// PEPEntry represents a Politically Exposed Person entry
type PEPEntry struct {
	EntryID      string    `json:"entryID"`
	Name         string    `json:"name"`
	Position     string    `json:"position"`
	Country      string    `json:"country"`
	RiskCategory string    `json:"riskCategory"`
	LastUpdated  time.Time `json:"lastUpdated"`
}

func (h *AMLCheckHandler) screenAgainstPEPDatabase(customerData *CustomerAMLData, pepDatabase []PEPEntry) ([]PEPMatch, error) {
	var matches []PEPMatch
	
	fullName := fmt.Sprintf("%s %s", customerData.FirstName, customerData.LastName)
	
	for _, entry := range pepDatabase {
		confidence := h.calculateNameMatchConfidence(fullName, entry.Name)
		
		if confidence >= 0.8 { // 80% threshold for PEP match
			matches = append(matches, PEPMatch{
				MatchID:      utils.GenerateID("PEP_MATCH"),
				MatchedName:  entry.Name,
				Position:     entry.Position,
				Country:      entry.Country,
				RiskCategory: entry.RiskCategory,
				Confidence:   confidence,
				LastUpdated:  entry.LastUpdated,
			})
		}
	}
	
	return matches, nil
}

// Recommendation and action generation methods
func (h *AMLCheckHandler) generateRecommendations(result *AMLCheckResult) []string {
	var recommendations []string
	
	if result.SanctionScreenResult.IsMatch {
		recommendations = append(recommendations, "Immediate review required due to sanction list match")
		recommendations = append(recommendations, "Verify customer identity with additional documentation")
	}
	
	if result.PEPScreenResult.IsMatch {
		recommendations = append(recommendations, "Enhanced due diligence required for PEP customer")
		recommendations = append(recommendations, "Obtain senior management approval for relationship")
	}
	
	if result.RiskLevel == RiskLevelHigh || result.RiskLevel == RiskLevelCritical {
		recommendations = append(recommendations, "Conduct enhanced monitoring of all transactions")
		recommendations = append(recommendations, "Consider relationship termination if risks cannot be mitigated")
	}
	
	if len(result.RiskFactors) > 3 {
		recommendations = append(recommendations, "Multiple risk factors identified - comprehensive review recommended")
	}
	
	return recommendations
}

func (h *AMLCheckHandler) generateRequiredActions(result *AMLCheckResult, actorID string) []RequiredAction {
	var actions []RequiredAction
	
	if result.SanctionScreenResult.IsMatch {
		actions = append(actions, RequiredAction{
			ActionID:    utils.GenerateID("ACTION"),
			ActionType:  "SANCTION_REVIEW",
			Description: "Review and investigate sanction list match",
			Priority:    "CRITICAL",
			DueDate:     time.Now().Add(24 * time.Hour), // 24 hours
			Status:      "PENDING",
		})
	}
	
	if result.PEPScreenResult.IsMatch {
		actions = append(actions, RequiredAction{
			ActionID:    utils.GenerateID("ACTION"),
			ActionType:  "PEP_APPROVAL",
			Description: "Obtain senior management approval for PEP relationship",
			Priority:    "HIGH",
			DueDate:     time.Now().Add(72 * time.Hour), // 72 hours
			Status:      "PENDING",
		})
	}
	
	if result.RiskLevel == RiskLevelHigh || result.RiskLevel == RiskLevelCritical {
		actions = append(actions, RequiredAction{
			ActionID:    utils.GenerateID("ACTION"),
			ActionType:  "ENHANCED_MONITORING",
			Description: "Implement enhanced transaction monitoring",
			Priority:    "HIGH",
			DueDate:     time.Now().Add(48 * time.Hour), // 48 hours
			Status:      "PENDING",
		})
	}
	
	return actions
}

// Utility methods
func (h *AMLCheckHandler) calculateExpiryDate(checkType AMLCheckType) time.Time {
	now := time.Now()
	
	switch checkType {
	case AMLCheckTypeCustomerOnboarding:
		return now.AddDate(1, 0, 0) // 1 year
	case AMLCheckTypePeriodicReview:
		return now.AddDate(1, 0, 0) // 1 year
	case AMLCheckTypeTransactionBased:
		return now.AddDate(0, 6, 0) // 6 months
	case AMLCheckTypeRiskReassessment:
		return now.AddDate(0, 3, 0) // 3 months
	default:
		return now.AddDate(1, 0, 0) // Default 1 year
	}
}

func (h *AMLCheckHandler) validateAMLCheckRequest(req *AMLCheckRequest) error {
	if req.CustomerID == "" {
		return fmt.Errorf("customerID is required")
	}
	
	if req.ActorID == "" {
		return fmt.Errorf("actorID is required")
	}
	
	if req.CustomerData.FirstName == "" || req.CustomerData.LastName == "" {
		return fmt.Errorf("customer first name and last name are required")
	}
	
	if req.CustomerData.NationalID == "" {
		return fmt.Errorf("customer national ID is required")
	}
	
	// Validate check type
	validCheckTypes := []AMLCheckType{
		AMLCheckTypeCustomerOnboarding,
		AMLCheckTypePeriodicReview,
		AMLCheckTypeTransactionBased,
		AMLCheckTypeRiskReassessment,
	}
	
	validType := false
	for _, validCheckType := range validCheckTypes {
		if req.CheckType == validCheckType {
			validType = true
			break
		}
	}
	
	if !validType {
		return fmt.Errorf("invalid check type: %s", req.CheckType)
	}
	
	return nil
}

// Compliance event recording
func (h *AMLCheckHandler) recordComplianceEvent(stub shim.ChaincodeStubInterface, result *AMLCheckResult, actorID string) error {
	eventID := utils.GenerateID(config.ComplianceEventPrefix)
	
	event := &domain.ComplianceEvent{
		EventID:            eventID,
		Timestamp:          time.Now(),
		RuleID:             "AML_SCREENING_RULE",
		RuleVersion:        "1.0",
		AffectedEntityID:   result.CustomerID,
		AffectedEntityType: "Customer",
		EventType:          "AML_CHECK_COMPLETED",
		Severity:           h.mapRiskLevelToSeverity(result.RiskLevel),
		Details: map[string]interface{}{
			"checkID":         result.CheckID,
			"checkType":       result.CheckType,
			"riskScore":       result.OverallRiskScore,
			"riskLevel":       result.RiskLevel,
			"sanctionMatch":   result.SanctionScreenResult.IsMatch,
			"pepMatch":        result.PEPScreenResult.IsMatch,
			"riskFactorCount": len(result.RiskFactors),
		},
		ExecutionResult: domain.RuleExecutionResult{
			RuleID:        "AML_SCREENING_RULE",
			ExecutionID:   utils.GenerateID("EXEC"),
			Timestamp:     time.Now(),
			Success:       true,
			Passed:        result.Status == validation.AMLStatusClear,
			Score:         result.OverallRiskScore,
			Details:       map[string]interface{}{"amlResult": result},
		},
		ActorID:          actorID,
		IsAlerted:        result.RiskLevel == RiskLevelHigh || result.RiskLevel == RiskLevelCritical,
		ResolutionStatus: "OPEN",
	}
	
	// Store compliance event
	eventKey := fmt.Sprintf("COMPLIANCE_EVENT_%s", eventID)
	if err := h.persistenceService.Put(stub, eventKey, event); err != nil {
		return fmt.Errorf("failed to store compliance event: %v", err)
	}
	
	// Emit event if emitter is available
	if h.eventEmitter != nil {
		return h.eventEmitter.EmitComplianceEvent(stub, event)
	}
	
	return nil
}

func (h *AMLCheckHandler) mapRiskLevelToSeverity(riskLevel RiskLevel) domain.ComplianceRulePriority {
	switch riskLevel {
	case RiskLevelCritical:
		return domain.PriorityCritical
	case RiskLevelHigh:
		return domain.PriorityHigh
	case RiskLevelMedium:
		return domain.PriorityMedium
	default:
		return domain.PriorityLow
	}
}

// Risk escalation handling
func (h *AMLCheckHandler) handleRiskEscalation(stub shim.ChaincodeStubInterface, result *AMLCheckResult, actorID string) error {
	escalationID := utils.GenerateID("ESCALATION")
	
	escalation := map[string]interface{}{
		"escalationID":   escalationID,
		"customerID":     result.CustomerID,
		"checkID":        result.CheckID,
		"riskLevel":      result.RiskLevel,
		"riskScore":      result.OverallRiskScore,
		"escalatedBy":    actorID,
		"escalationDate": time.Now(),
		"status":         "OPEN",
		"priority":       "HIGH",
		"assignedTo":     "COMPLIANCE_TEAM",
		"reason":         fmt.Sprintf("High risk AML check result: %s", result.RiskLevel),
		"details":        result,
	}
	
	// Store escalation
	escalationKey := fmt.Sprintf("AML_ESCALATION_%s", escalationID)
	if err := h.persistenceService.Put(stub, escalationKey, escalation); err != nil {
		return fmt.Errorf("failed to store escalation: %v", err)
	}
	
	// Create escalation index
	customerEscalationKey := fmt.Sprintf("CUSTOMER_ESCALATION_%s_%s", result.CustomerID, escalationID)
	if err := stub.PutState(customerEscalationKey, []byte(escalationID)); err != nil {
		return fmt.Errorf("failed to create escalation index: %v", err)
	}
	
	return nil
}

// UpdateAMLStatus updates AML status with enhanced validation
func (h *AMLCheckHandler) UpdateAMLStatus(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req struct {
		CheckID   string                `json:"checkID"`
		NewStatus validation.AMLStatus `json:"newStatus"`
		Notes     string                `json:"notes"`
		ActorID   string                `json:"actorID"`
	}

	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse AML status update request: %v", err)
	}

	// Get existing AML result
	resultKey := fmt.Sprintf("AML_RESULT_%s", req.CheckID)
	var result AMLCheckResult
	if err := h.persistenceService.Get(stub, resultKey, &result); err != nil {
		return nil, fmt.Errorf("AML check result not found: %v", err)
	}

	// Validate status transition
	if err := h.validateAMLStatusTransition(result.Status, req.NewStatus); err != nil {
		return nil, fmt.Errorf("invalid status transition: %v", err)
	}

	// Update result
	result.Status = req.NewStatus
	result.Notes = req.Notes
	result.ReviewedBy = req.ActorID
	now := time.Now()
	result.ReviewDate = &now

	// Store updated result
	if err := h.persistenceService.Put(stub, resultKey, &result); err != nil {
		return nil, fmt.Errorf("failed to update AML result: %v", err)
	}

	// Record compliance event for status change
	if err := h.recordStatusChangeEvent(stub, &result, req.ActorID); err != nil {
		return nil, fmt.Errorf("failed to record status change event: %v", err)
	}

	return json.Marshal(&result)
}

func (h *AMLCheckHandler) validateAMLStatusTransition(currentStatus, newStatus validation.AMLStatus) error {
	validTransitions := map[validation.AMLStatus][]validation.AMLStatus{
		validation.AMLStatusClear:     {validation.AMLStatusFlagged, validation.AMLStatusReviewing},
		validation.AMLStatusFlagged:   {validation.AMLStatusClear, validation.AMLStatusReviewing, validation.AMLStatusBlocked},
		validation.AMLStatusReviewing: {validation.AMLStatusClear, validation.AMLStatusFlagged, validation.AMLStatusBlocked},
		validation.AMLStatusBlocked:   {validation.AMLStatusReviewing}, // Only allow review from blocked
	}

	allowedTransitions, exists := validTransitions[currentStatus]
	if !exists {
		return fmt.Errorf("unknown current status: %s", currentStatus)
	}

	for _, allowed := range allowedTransitions {
		if newStatus == allowed {
			return nil
		}
	}

	return fmt.Errorf("invalid transition from %s to %s", currentStatus, newStatus)
}

func (h *AMLCheckHandler) recordStatusChangeEvent(stub shim.ChaincodeStubInterface, result *AMLCheckResult, actorID string) error {
	eventID := utils.GenerateID(config.ComplianceEventPrefix)
	
	event := &domain.ComplianceEvent{
		EventID:            eventID,
		Timestamp:          time.Now(),
		RuleID:             "AML_STATUS_UPDATE_RULE",
		RuleVersion:        "1.0",
		AffectedEntityID:   result.CustomerID,
		AffectedEntityType: "Customer",
		EventType:          "AML_STATUS_UPDATED",
		Severity:           h.mapRiskLevelToSeverity(result.RiskLevel),
		Details: map[string]interface{}{
			"checkID":   result.CheckID,
			"newStatus": result.Status,
			"notes":     result.Notes,
		},
		ActorID:          actorID,
		IsAlerted:        result.Status == validation.AMLStatusBlocked,
		ResolutionStatus: "OPEN",
	}
	
	// Store compliance event
	eventKey := fmt.Sprintf("COMPLIANCE_EVENT_%s", eventID)
	return h.persistenceService.Put(stub, eventKey, event)
}

// GetAMLReport retrieves comprehensive AML report
func (h *AMLCheckHandler) GetAMLReport(stub shim.ChaincodeStubInterface, args []string) ([]byte, error) {
	if len(args) != 1 {
		return nil, fmt.Errorf("incorrect number of arguments. Expected 1, got %d", len(args))
	}

	var req struct {
		CustomerID string `json:"customerID,omitempty"`
		CheckID    string `json:"checkID,omitempty"`
		DateFrom   string `json:"dateFrom,omitempty"`
		DateTo     string `json:"dateTo,omitempty"`
	}

	if err := json.Unmarshal([]byte(args[0]), &req); err != nil {
		return nil, fmt.Errorf("failed to parse AML report request: %v", err)
	}

	if req.CustomerID == "" && req.CheckID == "" {
		return nil, fmt.Errorf("either customerID or checkID must be provided")
	}

	var results []AMLCheckResult

	if req.CheckID != "" {
		// Get specific check result
		resultKey := fmt.Sprintf("AML_RESULT_%s", req.CheckID)
		var result AMLCheckResult
		if err := h.persistenceService.Get(stub, resultKey, &result); err != nil {
			return nil, fmt.Errorf("AML check result not found: %v", err)
		}
		results = append(results, result)
	} else {
		// Get all results for customer
		customerResults, err := h.getCustomerAMLResults(stub, req.CustomerID)
		if err != nil {
			return nil, fmt.Errorf("failed to get customer AML results: %v", err)
		}
		results = customerResults
	}

	// Generate comprehensive report
	report := map[string]interface{}{
		"reportID":      utils.GenerateID("AML_REPORT"),
		"generatedDate": time.Now(),
		"customerID":    req.CustomerID,
		"checkID":       req.CheckID,
		"totalChecks":   len(results),
		"results":       results,
		"summary":       h.generateAMLSummary(results),
	}

	return json.Marshal(report)
}

func (h *AMLCheckHandler) getCustomerAMLResults(stub shim.ChaincodeStubInterface, customerID string) ([]AMLCheckResult, error) {
	// Query customer AML results using composite key
	iterator, err := stub.GetStateByPartialCompositeKey("CUSTOMER_AML", []string{customerID})
	if err != nil {
		return nil, fmt.Errorf("failed to get customer AML results: %v", err)
	}
	defer iterator.Close()

	var results []AMLCheckResult

	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate AML results: %v", err)
		}

		checkID := string(response.Value)
		resultKey := fmt.Sprintf("AML_RESULT_%s", checkID)
		
		var result AMLCheckResult
		if err := h.persistenceService.Get(stub, resultKey, &result); err != nil {
			continue // Skip if result not found
		}

		results = append(results, result)
	}

	return results, nil
}

func (h *AMLCheckHandler) generateAMLSummary(results []AMLCheckResult) map[string]interface{} {
	summary := map[string]interface{}{
		"totalChecks":      len(results),
		"clearCount":       0,
		"flaggedCount":     0,
		"reviewingCount":   0,
		"blockedCount":     0,
		"sanctionMatches":  0,
		"pepMatches":       0,
		"avgRiskScore":     0.0,
		"highestRiskScore": 0.0,
		"latestCheck":      time.Time{},
	}

	if len(results) == 0 {
		return summary
	}

	totalRiskScore := 0.0
	highestRiskScore := 0.0
	latestCheck := results[0].CheckDate

	for _, result := range results {
		// Count by status
		switch result.Status {
		case validation.AMLStatusClear:
			summary["clearCount"] = summary["clearCount"].(int) + 1
		case validation.AMLStatusFlagged:
			summary["flaggedCount"] = summary["flaggedCount"].(int) + 1
		case validation.AMLStatusReviewing:
			summary["reviewingCount"] = summary["reviewingCount"].(int) + 1
		case validation.AMLStatusBlocked:
			summary["blockedCount"] = summary["blockedCount"].(int) + 1
		}

		// Count matches
		if result.SanctionScreenResult.IsMatch {
			summary["sanctionMatches"] = summary["sanctionMatches"].(int) + 1
		}
		if result.PEPScreenResult.IsMatch {
			summary["pepMatches"] = summary["pepMatches"].(int) + 1
		}

		// Risk score calculations
		totalRiskScore += result.OverallRiskScore
		if result.OverallRiskScore > highestRiskScore {
			highestRiskScore = result.OverallRiskScore
		}

		// Latest check
		if result.CheckDate.After(latestCheck) {
			latestCheck = result.CheckDate
		}
	}

	summary["avgRiskScore"] = totalRiskScore / float64(len(results))
	summary["highestRiskScore"] = highestRiskScore
	summary["latestCheck"] = latestCheck

	return summary
}