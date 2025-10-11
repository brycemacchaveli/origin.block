package shared

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"regexp"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
)

// GenerateID creates a unique identifier using timestamp and random component
func GenerateID(prefix string) string {
	timestamp := time.Now().UnixNano()
	// Add a small random component to ensure uniqueness even with same timestamp
	hash := sha256.Sum256([]byte(fmt.Sprintf("%d_%d", timestamp, timestamp%1000)))
	hashStr := hex.EncodeToString(hash[:4]) // Use first 4 bytes for shorter ID
	return fmt.Sprintf("%s_%d_%s", prefix, timestamp, hashStr)
}

// HashString creates a SHA256 hash of the input string
func HashString(input string) string {
	hash := sha256.Sum256([]byte(input))
	return hex.EncodeToString(hash[:])
}

// ValidateRequired checks if required fields are not empty
func ValidateRequired(fields map[string]string) error {
	for fieldName, value := range fields {
		if value == "" {
			return fmt.Errorf("required field '%s' is empty", fieldName)
		}
	}
	return nil
}

// GetStateAsJSON retrieves and unmarshals JSON data from the ledger
func GetStateAsJSON(stub shim.ChaincodeStubInterface, key string, result interface{}) error {
	data, err := stub.GetState(key)
	if err != nil {
		return fmt.Errorf("failed to get state for key %s: %v", key, err)
	}
	if data == nil {
		return fmt.Errorf("no data found for key %s", key)
	}
	return json.Unmarshal(data, result)
}

// PutStateAsJSON marshals and stores JSON data to the ledger
func PutStateAsJSON(stub shim.ChaincodeStubInterface, key string, value interface{}) error {
	data, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("failed to marshal data: %v", err)
	}
	return stub.PutState(key, data)
}

// ============================================================================
// VALIDATION UTILITIES
// ============================================================================

// ValidationRule represents a validation rule with a name and validation function
type ValidationRule struct {
	Name      string
	Validator func(value string) error
}

// ValidateEmail checks if the email format is valid
func ValidateEmail(email string) error {
	emailRegex := regexp.MustCompile(`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`)
	if !emailRegex.MatchString(email) {
		return fmt.Errorf("invalid email format: %s", email)
	}
	return nil
}

// ValidatePhone checks if the phone number format is valid (basic validation)
func ValidatePhone(phone string) error {
	phoneRegex := regexp.MustCompile(`^\+?[1-9]\d{7,14}$`)
	if !phoneRegex.MatchString(phone) {
		return fmt.Errorf("invalid phone format: %s", phone)
	}
	return nil
}

// ValidateAmount checks if the amount is positive and within reasonable limits
func ValidateAmount(amount float64) error {
	if amount <= 0 {
		return fmt.Errorf("amount must be positive: %f", amount)
	}
	if amount > 1000000000 { // 1 billion limit
		return fmt.Errorf("amount exceeds maximum limit: %f", amount)
	}
	return nil
}

// ValidateStatus checks if the status is in the allowed list
func ValidateStatus(status string, allowedStatuses []string) error {
	for _, allowed := range allowedStatuses {
		if status == allowed {
			return nil
		}
	}
	return fmt.Errorf("invalid status '%s', allowed values: %v", status, allowedStatuses)
}

// ValidateStringLength checks if string length is within bounds
func ValidateStringLength(value string, minLength, maxLength int, fieldName string) error {
	length := len(value)
	if length < minLength {
		return fmt.Errorf("%s must be at least %d characters long", fieldName, minLength)
	}
	if length > maxLength {
		return fmt.Errorf("%s must be at most %d characters long", fieldName, maxLength)
	}
	return nil
}

// ValidateFields validates multiple fields using validation rules
func ValidateFields(fields map[string]string, rules map[string][]ValidationRule) error {
	for fieldName, value := range fields {
		if fieldRules, exists := rules[fieldName]; exists {
			for _, rule := range fieldRules {
				if err := rule.Validator(value); err != nil {
					return fmt.Errorf("validation failed for field '%s' (rule: %s): %v", fieldName, rule.Name, err)
				}
			}
		}
	}
	return nil
}

// ============================================================================
// ACCESS CONTROL UTILITIES
// ============================================================================

// ActorType represents the type of actor in the system
type ActorType string

const (
	ActorTypeInternalUser    ActorType = "Internal_User"
	ActorTypeExternalPartner ActorType = "External_Partner"
	ActorTypeSystem          ActorType = "System"
)

// ActorRole represents the role of an actor
type ActorRole string

const (
	RoleUnderwriter       ActorRole = "Underwriter"
	RoleIntroducer        ActorRole = "Introducer"
	RoleComplianceOfficer ActorRole = "Compliance_Officer"
	RoleCreditOfficer     ActorRole = "Credit_Officer"
	RoleCustomerService   ActorRole = "Customer_Service"
	RoleRiskAnalyst       ActorRole = "Risk_Analyst"
	RoleSystemAdmin       ActorRole = "System_Admin"
	RoleRegulator         ActorRole = "Regulator"
)

// Permission represents a specific permission
type Permission string

const (
	PermissionCreateCustomer     Permission = "CREATE_CUSTOMER"
	PermissionUpdateCustomer     Permission = "UPDATE_CUSTOMER"
	PermissionViewCustomer       Permission = "VIEW_CUSTOMER"
	PermissionCreateLoan         Permission = "CREATE_LOAN"
	PermissionUpdateLoan         Permission = "UPDATE_LOAN"
	PermissionApproveLoan        Permission = "APPROVE_LOAN"
	PermissionViewLoan           Permission = "VIEW_LOAN"
	PermissionViewCompliance     Permission = "VIEW_COMPLIANCE"
	PermissionUpdateCompliance   Permission = "UPDATE_COMPLIANCE"
	PermissionViewReports        Permission = "VIEW_REPORTS"
	PermissionRegulatorAccess    Permission = "REGULATOR_ACCESS"
)

// Actor represents an actor in the system
type Actor struct {
	ActorID           string      `json:"actorID"`
	ActorType         ActorType   `json:"actorType"`
	ActorName         string      `json:"actorName"`
	Role              ActorRole   `json:"role"`
	BlockchainIdentity string     `json:"blockchainIdentity"`
	Permissions       []Permission `json:"permissions"`
	IsActive          bool        `json:"isActive"`
	CreatedDate       time.Time   `json:"createdDate"`
	LastUpdated       time.Time   `json:"lastUpdated"`
}

// GetRolePermissions returns default permissions for a given role
func GetRolePermissions(role ActorRole) []Permission {
	rolePermissions := map[ActorRole][]Permission{
		RoleUnderwriter: {
			PermissionViewCustomer, PermissionViewLoan, PermissionUpdateLoan,
			PermissionViewCompliance, PermissionViewReports,
		},
		RoleIntroducer: {
			PermissionCreateCustomer, PermissionUpdateCustomer, PermissionViewCustomer,
			PermissionCreateLoan, PermissionViewLoan,
		},
		RoleComplianceOfficer: {
			PermissionViewCustomer, PermissionViewLoan, PermissionViewCompliance,
			PermissionUpdateCompliance, PermissionViewReports,
		},
		RoleCreditOfficer: {
			PermissionViewCustomer, PermissionViewLoan, PermissionApproveLoan,
			PermissionViewCompliance, PermissionViewReports,
		},
		RoleCustomerService: {
			PermissionCreateCustomer, PermissionUpdateCustomer, PermissionViewCustomer,
		},
		RoleRiskAnalyst: {
			PermissionViewCustomer, PermissionViewLoan, PermissionViewCompliance,
			PermissionViewReports,
		},
		RoleSystemAdmin: {
			PermissionViewCustomer, PermissionViewLoan, PermissionViewCompliance,
			PermissionViewReports,
		},
		RoleRegulator: {
			PermissionViewCustomer, PermissionViewLoan, PermissionViewCompliance,
			PermissionViewReports, PermissionRegulatorAccess,
		},
	}
	
	if permissions, exists := rolePermissions[role]; exists {
		return permissions
	}
	return []Permission{}
}

// HasPermission checks if an actor has a specific permission
func (a *Actor) HasPermission(permission Permission) bool {
	if !a.IsActive {
		return false
	}
	
	for _, p := range a.Permissions {
		if p == permission {
			return true
		}
	}
	return false
}

// ValidateActorAccess validates if an actor can perform an action
func ValidateActorAccess(stub shim.ChaincodeStubInterface, actorID string, requiredPermission Permission) (*Actor, error) {
	// Get actor from ledger
	var actor Actor
	err := GetStateAsJSON(stub, "ACTOR_"+actorID, &actor)
	if err != nil {
		return nil, fmt.Errorf("failed to get actor %s: %v", actorID, err)
	}
	
	// Check if actor has required permission
	if !actor.HasPermission(requiredPermission) {
		return nil, fmt.Errorf("actor %s does not have permission %s", actorID, requiredPermission)
	}
	
	return &actor, nil
}

// GetCallerIdentity extracts the caller's identity from the transaction context
func GetCallerIdentity(stub shim.ChaincodeStubInterface) (string, error) {
	// Get the creator's certificate
	creator, err := stub.GetCreator()
	if err != nil {
		return "", fmt.Errorf("failed to get transaction creator: %v", err)
	}
	
	// For simplicity, we'll hash the creator certificate to get a unique identifier
	// In a real implementation, you would parse the X.509 certificate
	creatorHash := HashString(string(creator))
	return creatorHash, nil
}

// ============================================================================
// CRYPTOGRAPHIC UTILITIES
// ============================================================================

// HashDocument creates a SHA256 hash of document content
func HashDocument(content []byte) string {
	hash := sha256.Sum256(content)
	return hex.EncodeToString(hash[:])
}

// EncryptSensitiveData encrypts sensitive data using AES-GCM
func EncryptSensitiveData(plaintext, key string) (string, error) {
	keyBytes := []byte(key)
	if len(keyBytes) != 32 {
		// Create a 32-byte key from the provided key
		hash := sha256.Sum256(keyBytes)
		keyBytes = hash[:]
	}
	
	block, err := aes.NewCipher(keyBytes)
	if err != nil {
		return "", fmt.Errorf("failed to create cipher: %v", err)
	}
	
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("failed to create GCM: %v", err)
	}
	
	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return "", fmt.Errorf("failed to generate nonce: %v", err)
	}
	
	ciphertext := gcm.Seal(nonce, nonce, []byte(plaintext), nil)
	return hex.EncodeToString(ciphertext), nil
}

// DecryptSensitiveData decrypts data encrypted with EncryptSensitiveData
func DecryptSensitiveData(ciphertext, key string) (string, error) {
	keyBytes := []byte(key)
	if len(keyBytes) != 32 {
		// Create a 32-byte key from the provided key
		hash := sha256.Sum256(keyBytes)
		keyBytes = hash[:]
	}
	
	data, err := hex.DecodeString(ciphertext)
	if err != nil {
		return "", fmt.Errorf("failed to decode hex: %v", err)
	}
	
	block, err := aes.NewCipher(keyBytes)
	if err != nil {
		return "", fmt.Errorf("failed to create cipher: %v", err)
	}
	
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("failed to create GCM: %v", err)
	}
	
	nonceSize := gcm.NonceSize()
	if len(data) < nonceSize {
		return "", fmt.Errorf("ciphertext too short")
	}
	
	nonce, ciphertext_bytes := data[:nonceSize], data[nonceSize:]
	plaintext, err := gcm.Open(nil, nonce, ciphertext_bytes, nil)
	if err != nil {
		return "", fmt.Errorf("failed to decrypt: %v", err)
	}
	
	return string(plaintext), nil
}

// HashSensitiveData creates a one-way hash for sensitive data (like National ID)
func HashSensitiveData(data, salt string) string {
	combined := data + salt
	hash := sha256.Sum256([]byte(combined))
	return hex.EncodeToString(hash[:])
}

// ============================================================================
// HISTORY TRACKING UTILITIES
// ============================================================================

// HistoryEntry represents a single history entry
type HistoryEntry struct {
	HistoryID      string    `json:"historyID"`
	EntityID       string    `json:"entityID"`
	EntityType     string    `json:"entityType"`
	Timestamp      time.Time `json:"timestamp"`
	ChangeType     string    `json:"changeType"`
	FieldName      string    `json:"fieldName"`
	PreviousValue  string    `json:"previousValue"`
	NewValue       string    `json:"newValue"`
	ActorID        string    `json:"actorID"`
	TransactionID  string    `json:"transactionID"`
}

// RecordHistoryEntry creates and stores a history entry
func RecordHistoryEntry(stub shim.ChaincodeStubInterface, entityID, entityType, changeType, fieldName, previousValue, newValue, actorID string) error {
	historyID := GenerateID("HIST")
	txID := stub.GetTxID()
	
	entry := HistoryEntry{
		HistoryID:     historyID,
		EntityID:      entityID,
		EntityType:    entityType,
		Timestamp:     time.Now(),
		ChangeType:    changeType,
		FieldName:     fieldName,
		PreviousValue: previousValue,
		NewValue:      newValue,
		ActorID:       actorID,
		TransactionID: txID,
	}
	
	return PutStateAsJSON(stub, historyID, entry)
}

// GetEntityHistory retrieves all history entries for an entity
func GetEntityHistory(stub shim.ChaincodeStubInterface, entityID string) ([]HistoryEntry, error) {
	// Use a composite key to query history entries
	iterator, err := stub.GetStateByPartialCompositeKey("HISTORY", []string{entityID})
	if err != nil {
		return nil, fmt.Errorf("failed to get history iterator: %v", err)
	}
	defer iterator.Close()
	
	var history []HistoryEntry
	for iterator.HasNext() {
		response, err := iterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to iterate history: %v", err)
		}
		
		var entry HistoryEntry
		err = json.Unmarshal(response.Value, &entry)
		if err != nil {
			return nil, fmt.Errorf("failed to unmarshal history entry: %v", err)
		}
		
		history = append(history, entry)
	}
	
	return history, nil
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

// CreateCompositeKey creates a composite key for complex queries
func CreateCompositeKey(stub shim.ChaincodeStubInterface, objectType string, attributes []string) (string, error) {
	return stub.CreateCompositeKey(objectType, attributes)
}

// SplitCompositeKey splits a composite key back into its components
func SplitCompositeKey(stub shim.ChaincodeStubInterface, compositeKey string) (string, []string, error) {
	return stub.SplitCompositeKey(compositeKey)
}

// EmitEvent emits a chaincode event
func EmitEvent(stub shim.ChaincodeStubInterface, eventName string, payload interface{}) error {
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal event payload: %v", err)
	}
	
	return stub.SetEvent(eventName, payloadBytes)
}

// ValidateTransactionTimestamp ensures the transaction timestamp is reasonable
func ValidateTransactionTimestamp(stub shim.ChaincodeStubInterface) error {
	txTimestamp, err := stub.GetTxTimestamp()
	if err != nil {
		return fmt.Errorf("failed to get transaction timestamp: %v", err)
	}
	
	now := time.Now()
	txTime := time.Unix(txTimestamp.Seconds, int64(txTimestamp.Nanos))
	
	// Check if transaction is too far in the future (more than 5 minutes)
	if txTime.After(now.Add(5 * time.Minute)) {
		return fmt.Errorf("transaction timestamp is too far in the future")
	}
	
	// Check if transaction is too old (more than 1 hour)
	if txTime.Before(now.Add(-1 * time.Hour)) {
		return fmt.Errorf("transaction timestamp is too old")
	}
	
	return nil
}