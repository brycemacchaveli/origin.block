package interfaces

// ValidationResult represents the result of a validation operation
type ValidationResult struct {
	IsValid bool     `json:"isValid"`
	Errors  []string `json:"errors,omitempty"`
}

// FieldValidator defines validation for individual fields
type FieldValidator interface {
	ValidateField(fieldName string, value interface{}) ValidationResult
	GetValidationRules(fieldName string) []string
}

// EntityValidator defines validation for complete entities
type EntityValidator interface {
	ValidateEntity(entity interface{}) ValidationResult
	ValidateEntityUpdate(currentEntity, updatedEntity interface{}) ValidationResult
}

// BusinessRuleValidator defines business logic validation
type BusinessRuleValidator interface {
	ValidateBusinessRules(entity interface{}, context map[string]interface{}) ValidationResult
	GetApplicableRules(entityType string) []string
}

// CompositeValidator combines multiple validation strategies
type CompositeValidator interface {
	FieldValidator
	EntityValidator
	BusinessRuleValidator
	
	// Add custom validators
	AddValidator(name string, validator interface{}) error
	RemoveValidator(name string) error
}