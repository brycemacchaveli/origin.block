package validation

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// FieldRule represents a validation rule for a field
type FieldRule struct {
	Name        string
	Description string
	Validator   func(value interface{}) error
}

// Common field validation rules
var (
	// String validation rules
	RequiredRule = FieldRule{
		Name:        "required",
		Description: "Field is required and cannot be empty",
		Validator: func(value interface{}) error {
			if value == nil {
				return fmt.Errorf("field is required")
			}
			if str, ok := value.(string); ok && strings.TrimSpace(str) == "" {
				return fmt.Errorf("field is required")
			}
			return nil
		},
	}
	
	EmailRule = FieldRule{
		Name:        "email",
		Description: "Field must be a valid email address",
		Validator: func(value interface{}) error {
			str, ok := value.(string)
			if !ok {
				return fmt.Errorf("email must be a string")
			}
			emailRegex := regexp.MustCompile(`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`)
			if !emailRegex.MatchString(str) {
				return fmt.Errorf("invalid email format")
			}
			return nil
		},
	}
	
	PhoneRule = FieldRule{
		Name:        "phone",
		Description: "Field must be a valid phone number",
		Validator: func(value interface{}) error {
			str, ok := value.(string)
			if !ok {
				return fmt.Errorf("phone must be a string")
			}
			phoneRegex := regexp.MustCompile(`^\+?[1-9]\d{7,14}$`)
			if !phoneRegex.MatchString(str) {
				return fmt.Errorf("invalid phone format")
			}
			return nil
		},
	}
	
	// Numeric validation rules
	PositiveNumberRule = FieldRule{
		Name:        "positive",
		Description: "Field must be a positive number",
		Validator: func(value interface{}) error {
			switch v := value.(type) {
			case int:
				if v <= 0 {
					return fmt.Errorf("must be positive")
				}
			case int64:
				if v <= 0 {
					return fmt.Errorf("must be positive")
				}
			case float64:
				if v <= 0 {
					return fmt.Errorf("must be positive")
				}
			case string:
				num, err := strconv.ParseFloat(v, 64)
				if err != nil {
					return fmt.Errorf("must be a valid number")
				}
				if num <= 0 {
					return fmt.Errorf("must be positive")
				}
			default:
				return fmt.Errorf("must be a number")
			}
			return nil
		},
	}
)

// CreateMinLengthRule creates a rule for minimum string length
func CreateMinLengthRule(minLength int) FieldRule {
	return FieldRule{
		Name:        fmt.Sprintf("minLength_%d", minLength),
		Description: fmt.Sprintf("Field must be at least %d characters long", minLength),
		Validator: func(value interface{}) error {
			str, ok := value.(string)
			if !ok {
				return fmt.Errorf("value must be a string")
			}
			if len(str) < minLength {
				return fmt.Errorf("must be at least %d characters long", minLength)
			}
			return nil
		},
	}
}

// CreateMaxLengthRule creates a rule for maximum string length
func CreateMaxLengthRule(maxLength int) FieldRule {
	return FieldRule{
		Name:        fmt.Sprintf("maxLength_%d", maxLength),
		Description: fmt.Sprintf("Field must be at most %d characters long", maxLength),
		Validator: func(value interface{}) error {
			str, ok := value.(string)
			if !ok {
				return fmt.Errorf("value must be a string")
			}
			if len(str) > maxLength {
				return fmt.Errorf("must be at most %d characters long", maxLength)
			}
			return nil
		},
	}
}

// CreateRangeRule creates a rule for numeric range validation
func CreateRangeRule(min, max float64) FieldRule {
	return FieldRule{
		Name:        fmt.Sprintf("range_%.2f_%.2f", min, max),
		Description: fmt.Sprintf("Field must be between %.2f and %.2f", min, max),
		Validator: func(value interface{}) error {
			var num float64
			var err error
			
			switch v := value.(type) {
			case int:
				num = float64(v)
			case int64:
				num = float64(v)
			case float64:
				num = v
			case string:
				num, err = strconv.ParseFloat(v, 64)
				if err != nil {
					return fmt.Errorf("must be a valid number")
				}
			default:
				return fmt.Errorf("must be a number")
			}
			
			if num < min || num > max {
				return fmt.Errorf("must be between %.2f and %.2f", min, max)
			}
			return nil
		},
	}
}

// CreateEnumRule creates a rule for enum validation
func CreateEnumRule(allowedValues []string) FieldRule {
	return FieldRule{
		Name:        fmt.Sprintf("enum_%s", strings.Join(allowedValues, "_")),
		Description: fmt.Sprintf("Field must be one of: %s", strings.Join(allowedValues, ", ")),
		Validator: func(value interface{}) error {
			str, ok := value.(string)
			if !ok {
				return fmt.Errorf("value must be a string")
			}
			
			for _, allowed := range allowedValues {
				if str == allowed {
					return nil
				}
			}
			
			return fmt.Errorf("must be one of: %s", strings.Join(allowedValues, ", "))
		},
	}
}

// CreateDateRule creates a rule for date validation
func CreateDateRule(format string) FieldRule {
	return FieldRule{
		Name:        fmt.Sprintf("date_%s", format),
		Description: fmt.Sprintf("Field must be a valid date in format %s", format),
		Validator: func(value interface{}) error {
			str, ok := value.(string)
			if !ok {
				return fmt.Errorf("date must be a string")
			}
			
			_, err := time.Parse(format, str)
			if err != nil {
				return fmt.Errorf("invalid date format, expected %s", format)
			}
			return nil
		},
	}
}

// CreateRegexRule creates a rule for regex pattern validation
func CreateRegexRule(pattern, description string) FieldRule {
	regex := regexp.MustCompile(pattern)
	return FieldRule{
		Name:        fmt.Sprintf("regex_%s", pattern),
		Description: description,
		Validator: func(value interface{}) error {
			str, ok := value.(string)
			if !ok {
				return fmt.Errorf("value must be a string")
			}
			
			if !regex.MatchString(str) {
				return fmt.Errorf("does not match required pattern: %s", description)
			}
			return nil
		},
	}
}