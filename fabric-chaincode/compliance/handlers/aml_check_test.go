package handlers

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-chaincode-go/shimtest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/brycemacchaveli/origin.block/fabric-chaincode/shared/validation"
)

// MockEventEmitter implements the EventEmitter interface for testing
type MockEventEmitter struct {
	EmittedEvents []interface{}
}

func (m *MockEventEmitter) EmitComplianceEvent(stub shim.ChaincodeStubInterface, event interface{}) error {
	m.EmittedEvents = append(m.EmittedEvents, event)
	return nil
}

func (m *MockEventEmitter) EmitRuleExecutionEvent(stub shim.ChaincodeStubInterface, result interface{}) error {
	m.EmittedEvents = append(m.EmittedEvents, result)
	return nil
}

func TestAMLCheckHandler_PerformAMLCheck(t *testing.T) {
	stub := shimtest.NewMockStub("aml_test", nil)
	mockEmitter := &MockEventEmitter{}
	handler := NewAMLCheckHandler(mockEmitter)

	tests := []struct {
		name           string
		request        AMLCheckRequest
		expectedStatus validation.AMLStatus
		expectedError  bool
	}{
		{
			name: "Valid customer onboarding check - low risk",
			request: AMLCheckRequest{
				CustomerID: "CUST_001",
				CustomerData: CustomerAMLData{
					FirstName:   "John",
					LastName:    "Smith",
					DateOfBirth: time.Date(1980, 1, 1, 0, 0, 0, 0, time.UTC),
					NationalID:  "ID123456789",
					Nationality: "US",
					Address:     "123 Main St, New York, NY",
					Country:     "US",
					Occupation:  "Engineer",
				},
				CheckType: AMLCheckTypeCustomerOnboarding,
				ActorID:   "ACTOR_001",
			},
			expectedStatus: validation.AMLStatusClear,
			expectedError:  false,
		},
		{
			name: "High-risk country customer - should be flagged",
			request: AMLCheckRequest{
				CustomerID: "CUST_002",
				CustomerData: CustomerAMLData{
					FirstName:   "Ahmad",
					LastName:    "Hassan",
					DateOfBirth: time.Date(1975, 5, 15, 0, 0, 0, 0, time.UTC),
					NationalID:  "AF987654321",
					Nationality: "AF",
					Address:     "Kabul, Afghanistan",
					Country:     "AF",
					Occupation:  "Businessman",
				},
				CheckType: AMLCheckTypeCustomerOnboarding,
				ActorID:   "ACTOR_001",
			},
			expectedStatus: validation.AMLStatusFlagged,
			expectedError:  false,
		},
		{
			name: "High-risk occupation - should be flagged",
			request: AMLCheckRequest{
				CustomerID: "CUST_003",
				CustomerData: CustomerAMLData{
					FirstName:   "Maria",
					LastName:    "Rodriguez",
					DateOfBirth: time.Date(1970, 3, 20, 0, 0, 0, 0, time.UTC),
					NationalID:  "ES123456789",
					Nationality: "ES",
					Address:     "Madrid, Spain",
					Country:     "ES",
					Occupation:  "POLITICIAN",
				},
				CheckType: AMLCheckTypeCustomerOnboarding,
				ActorID:   "ACTOR_001",
			},
			expectedStatus: validation.AMLStatusFlagged,
			expectedError:  false,
		},
		{
			name: "High-value transaction - should trigger review",
			request: AMLCheckRequest{
				CustomerID: "CUST_004",
				CustomerData: CustomerAMLData{
					FirstName:   "Robert",
					LastName:    "Johnson",
					DateOfBirth: time.Date(1985, 8, 10, 0, 0, 0, 0, time.UTC),
					NationalID:  "US987654321",
					Nationality: "US",
					Address:     "Los Angeles, CA",
					Country:     "US",
					Occupation:  "Consultant",
				},
				TransactionData: &TransactionAMLData{
					TransactionID:   "TXN_001",
					Amount:          150000.00,
					Currency:        "USD",
					TransactionType: "WIRE_TRANSFER",
					TransactionDate: time.Now(),
				},
				CheckType: AMLCheckTypeTransactionBased,
				ActorID:   "ACTOR_001",
			},
			expectedStatus: validation.AMLStatusReviewing,
			expectedError:  false,
		},
		{
			name: "Invalid request - missing customer ID",
			request: AMLCheckRequest{
				CustomerData: CustomerAMLData{
					FirstName: "Test",
					LastName:  "User",
				},
				CheckType: AMLCheckTypeCustomerOnboarding,
				ActorID:   "ACTOR_001",
			},
			expectedError: true,
		},
		{
			name: "Invalid request - missing actor ID",
			request: AMLCheckRequest{
				CustomerID: "CUST_005",
				CustomerData: CustomerAMLData{
					FirstName:  "Test",
					LastName:   "User",
					NationalID: "TEST123",
				},
				CheckType: AMLCheckTypeCustomerOnboarding,
			},
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			requestBytes, err := json.Marshal(tt.request)
			require.NoError(t, err)

			result, err := handler.PerformAMLCheck(stub, []string{string(requestBytes)})

			if tt.expectedError {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, result)

			var amlResult AMLCheckResult
			err = json.Unmarshal(result, &amlResult)
			require.NoError(t, err)

			assert.Equal(t, tt.expectedStatus, amlResult.Status)
			assert.Equal(t, tt.request.CustomerID, amlResult.CustomerID)
			assert.Equal(t, tt.request.CheckType, amlResult.CheckType)
			assert.NotEmpty(t, amlResult.CheckID)
			assert.NotZero(t, amlResult.CheckDate)
			assert.NotZero(t, amlResult.ExpiryDate)
			assert.Equal(t, tt.request.ActorID, amlResult.CheckedBy)

			// Verify risk assessment was performed
			assert.GreaterOrEqual(t, amlResult.OverallRiskScore, 0.0)
			assert.LessOrEqual(t, amlResult.OverallRiskScore, 1.0)
			assert.NotEmpty(t, amlResult.RiskLevel)

			// Verify sanction and PEP screening was performed
			assert.NotNil(t, amlResult.SanctionScreenResult)
			assert.NotNil(t, amlResult.PEPScreenResult)
			assert.NotZero(t, amlResult.SanctionScreenResult.ScreeningDate)
			assert.NotZero(t, amlResult.PEPScreenResult.ScreeningDate)

			// Verify recommendations and actions are generated for high-risk cases
			if amlResult.RiskLevel == RiskLevelHigh || amlResult.RiskLevel == RiskLevelCritical {
				assert.NotEmpty(t, amlResult.Recommendations)
				assert.NotEmpty(t, amlResult.RequiredActions)
			}
		})
	}
}

func TestAMLCheckHandler_UpdateAMLStatus(t *testing.T) {
	stub := shimtest.NewMockStub("aml_test", nil)
	mockEmitter := &MockEventEmitter{}
	handler := NewAMLCheckHandler(mockEmitter)

	// First, create an AML check result
	initialRequest := AMLCheckRequest{
		CustomerID: "CUST_001",
		CustomerData: CustomerAMLData{
			FirstName:   "John",
			LastName:    "Doe",
			DateOfBirth: time.Date(1980, 1, 1, 0, 0, 0, 0, time.UTC),
			NationalID:  "ID123456789",
			Nationality: "US",
			Address:     "123 Main St",
			Country:     "US",
		},
		CheckType: AMLCheckTypeCustomerOnboarding,
		ActorID:   "ACTOR_001",
	}

	requestBytes, err := json.Marshal(initialRequest)
	require.NoError(t, err)

	result, err := handler.PerformAMLCheck(stub, []string{string(requestBytes)})
	require.NoError(t, err)

	var amlResult AMLCheckResult
	err = json.Unmarshal(result, &amlResult)
	require.NoError(t, err)

	tests := []struct {
		name          string
		checkID       string
		newStatus     validation.AMLStatus
		notes         string
		actorID       string
		expectedError bool
	}{
		{
			name:      "Valid status update - clear to flagged",
			checkID:   amlResult.CheckID,
			newStatus: validation.AMLStatusFlagged,
			notes:     "Additional risk factors identified",
			actorID:   "ACTOR_002",
		},
		{
			name:      "Valid status update - flagged to reviewing",
			checkID:   amlResult.CheckID,
			newStatus: validation.AMLStatusReviewing,
			notes:     "Under manual review",
			actorID:   "ACTOR_002",
		},
		{
			name:          "Invalid check ID",
			checkID:       "INVALID_ID",
			newStatus:     validation.AMLStatusFlagged,
			notes:         "Test",
			actorID:       "ACTOR_002",
			expectedError: true,
		},
		{
			name:          "Invalid status transition",
			checkID:       amlResult.CheckID,
			newStatus:     validation.AMLStatus("INVALID_STATUS"),
			notes:         "Test",
			actorID:       "ACTOR_002",
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			updateRequest := struct {
				CheckID   string                `json:"checkID"`
				NewStatus validation.AMLStatus `json:"newStatus"`
				Notes     string                `json:"notes"`
				ActorID   string                `json:"actorID"`
			}{
				CheckID:   tt.checkID,
				NewStatus: tt.newStatus,
				Notes:     tt.notes,
				ActorID:   tt.actorID,
			}

			updateBytes, err := json.Marshal(updateRequest)
			require.NoError(t, err)

			result, err := handler.UpdateAMLStatus(stub, []string{string(updateBytes)})

			if tt.expectedError {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, result)

			var updatedResult AMLCheckResult
			err = json.Unmarshal(result, &updatedResult)
			require.NoError(t, err)

			assert.Equal(t, tt.newStatus, updatedResult.Status)
			assert.Equal(t, tt.notes, updatedResult.Notes)
			assert.Equal(t, tt.actorID, updatedResult.ReviewedBy)
			assert.NotNil(t, updatedResult.ReviewDate)
		})
	}
}

func TestAMLCheckHandler_GetAMLReport(t *testing.T) {
	stub := shimtest.NewMockStub("aml_test", nil)
	mockEmitter := &MockEventEmitter{}
	handler := NewAMLCheckHandler(mockEmitter)

	// Create multiple AML check results for testing
	customerID := "CUST_REPORT_TEST"
	
	for i := 0; i < 3; i++ {
		request := AMLCheckRequest{
			CustomerID: customerID,
			CustomerData: CustomerAMLData{
				FirstName:   "Test",
				LastName:    "Customer",
				DateOfBirth: time.Date(1980, 1, 1, 0, 0, 0, 0, time.UTC),
				NationalID:  "TEST123456789",
				Nationality: "US",
				Address:     "Test Address",
				Country:     "US",
			},
			CheckType: AMLCheckTypePeriodicReview,
			ActorID:   "ACTOR_001",
		}

		requestBytes, err := json.Marshal(request)
		require.NoError(t, err)

		_, err = handler.PerformAMLCheck(stub, []string{string(requestBytes)})
		require.NoError(t, err)
	}

	tests := []struct {
		name          string
		request       map[string]interface{}
		expectedError bool
	}{
		{
			name: "Get report by customer ID",
			request: map[string]interface{}{
				"customerID": customerID,
			},
		},
		{
			name: "Invalid request - no customer ID or check ID",
			request: map[string]interface{}{
				"dateFrom": "2023-01-01",
			},
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			requestBytes, err := json.Marshal(tt.request)
			require.NoError(t, err)

			result, err := handler.GetAMLReport(stub, []string{string(requestBytes)})

			if tt.expectedError {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, result)

			var report map[string]interface{}
			err = json.Unmarshal(result, &report)
			require.NoError(t, err)

			assert.Contains(t, report, "reportID")
			assert.Contains(t, report, "generatedDate")
			assert.Contains(t, report, "totalChecks")
			assert.Contains(t, report, "results")
			assert.Contains(t, report, "summary")

			// Verify we have results
			totalChecks, ok := report["totalChecks"].(float64)
			require.True(t, ok)
			assert.Greater(t, totalChecks, 0.0)
		})
	}
}

func TestAMLCheckHandler_RiskAssessment(t *testing.T) {
	handler := NewAMLCheckHandler(nil)

	tests := []struct {
		name             string
		customerData     CustomerAMLData
		transactionData  *TransactionAMLData
		expectedRiskLevel RiskLevel
	}{
		{
			name: "Low risk customer",
			customerData: CustomerAMLData{
				FirstName:   "John",
				LastName:    "Smith",
				Country:     "US",
				Occupation:  "Engineer",
			},
			expectedRiskLevel: RiskLevelLow,
		},
		{
			name: "High risk country",
			customerData: CustomerAMLData{
				FirstName:   "Ahmad",
				LastName:    "Hassan",
				Country:     "AF", // Afghanistan - high risk
				Occupation:  "Businessman",
			},
			expectedRiskLevel: RiskLevelHigh,
		},
		{
			name: "High risk occupation",
			customerData: CustomerAMLData{
				FirstName:   "Maria",
				LastName:    "Rodriguez",
				Country:     "ES",
				Occupation:  "POLITICIAN",
			},
			expectedRiskLevel: RiskLevelHigh,
		},
		{
			name: "High value transaction",
			customerData: CustomerAMLData{
				FirstName:   "Robert",
				LastName:    "Johnson",
				Country:     "US",
				Occupation:  "Consultant",
			},
			transactionData: &TransactionAMLData{
				Amount:   150000.00,
				Currency: "USD",
			},
			expectedRiskLevel: RiskLevelHigh,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			stub := shimtest.NewMockStub("risk_test", nil)
			
			riskFactors, err := handler.assessRiskFactors(stub, &tt.customerData, tt.transactionData)
			require.NoError(t, err)

			// Create a mock result to test risk calculation
			result := &AMLCheckResult{
				RiskFactors: riskFactors,
				SanctionScreenResult: SanctionScreenResult{IsMatch: false, MatchConfidence: 0.0},
				PEPScreenResult:      PEPScreenResult{IsMatch: false, MatchConfidence: 0.0},
			}

			overallScore := handler.calculateOverallRiskScore(result)
			riskLevel := handler.determineRiskLevel(overallScore)

			assert.GreaterOrEqual(t, overallScore, 0.0)
			assert.LessOrEqual(t, overallScore, 1.0)

			// For high-risk cases, verify the risk level is appropriate
			if tt.expectedRiskLevel == RiskLevelHigh {
				assert.True(t, riskLevel == RiskLevelHigh || riskLevel == RiskLevelCritical,
					"Expected high or critical risk level, got %s", riskLevel)
			}
		})
	}
}

func TestAMLCheckHandler_SanctionScreening(t *testing.T) {
	handler := NewAMLCheckHandler(nil)
	stub := shimtest.NewMockStub("sanction_test", nil)

	tests := []struct {
		name         string
		customerData CustomerAMLData
		expectMatch  bool
	}{
		{
			name: "No sanction match",
			customerData: CustomerAMLData{
				FirstName:   "Regular",
				LastName:    "Customer",
				DateOfBirth: time.Date(1990, 1, 1, 0, 0, 0, 0, time.UTC),
				Nationality: "US",
			},
			expectMatch: false,
		},
		{
			name: "Potential sanction match",
			customerData: CustomerAMLData{
				FirstName:   "John",
				LastName:    "Doe",
				DateOfBirth: time.Date(1970, 1, 1, 0, 0, 0, 0, time.UTC),
				Nationality: "US",
			},
			expectMatch: true, // This matches our mock data
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := handler.performSanctionScreening(stub, &tt.customerData, nil)
			require.NoError(t, err)

			assert.Equal(t, tt.expectMatch, result.IsMatch)
			assert.NotEmpty(t, result.ListsScreened)
			assert.NotZero(t, result.ScreeningDate)

			if tt.expectMatch {
				assert.NotEmpty(t, result.Matches)
				assert.Greater(t, result.MatchConfidence, 0.0)
			}
		})
	}
}

func TestAMLCheckHandler_NameMatching(t *testing.T) {
	handler := NewAMLCheckHandler(nil)

	tests := []struct {
		name1      string
		name2      string
		minConfidence float64
	}{
		{"John Doe", "John Doe", 1.0},
		{"John Doe", "Jon Doe", 0.8},
		{"John Smith", "Jane Smith", 0.6},
		{"John Doe", "Mary Johnson", 0.0},
	}

	for _, tt := range tests {
		t.Run(fmt.Sprintf("%s vs %s", tt.name1, tt.name2), func(t *testing.T) {
			confidence := handler.calculateNameMatchConfidence(tt.name1, tt.name2)
			assert.GreaterOrEqual(t, confidence, tt.minConfidence)
			assert.LessOrEqual(t, confidence, 1.0)
		})
	}
}

func TestAMLCheckHandler_StatusTransitions(t *testing.T) {
	handler := NewAMLCheckHandler(nil)

	validTransitions := []struct {
		from validation.AMLStatus
		to   validation.AMLStatus
	}{
		{validation.AMLStatusClear, validation.AMLStatusFlagged},
		{validation.AMLStatusClear, validation.AMLStatusReviewing},
		{validation.AMLStatusFlagged, validation.AMLStatusClear},
		{validation.AMLStatusFlagged, validation.AMLStatusReviewing},
		{validation.AMLStatusFlagged, validation.AMLStatusBlocked},
		{validation.AMLStatusReviewing, validation.AMLStatusClear},
		{validation.AMLStatusReviewing, validation.AMLStatusFlagged},
		{validation.AMLStatusReviewing, validation.AMLStatusBlocked},
		{validation.AMLStatusBlocked, validation.AMLStatusReviewing},
	}

	invalidTransitions := []struct {
		from validation.AMLStatus
		to   validation.AMLStatus
	}{
		{validation.AMLStatusBlocked, validation.AMLStatusClear},
		{validation.AMLStatusBlocked, validation.AMLStatusFlagged},
	}

	for _, tt := range validTransitions {
		t.Run(fmt.Sprintf("Valid: %s to %s", tt.from, tt.to), func(t *testing.T) {
			err := handler.validateAMLStatusTransition(tt.from, tt.to)
			assert.NoError(t, err)
		})
	}

	for _, tt := range invalidTransitions {
		t.Run(fmt.Sprintf("Invalid: %s to %s", tt.from, tt.to), func(t *testing.T) {
			err := handler.validateAMLStatusTransition(tt.from, tt.to)
			assert.Error(t, err)
		})
	}
}

func TestAMLCheckHandler_ExpiryDateCalculation(t *testing.T) {
	handler := NewAMLCheckHandler(nil)

	tests := []struct {
		checkType    AMLCheckType
		expectedDays int
	}{
		{AMLCheckTypeCustomerOnboarding, 365},
		{AMLCheckTypePeriodicReview, 365},
		{AMLCheckTypeTransactionBased, 180}, // 6 months
		{AMLCheckTypeRiskReassessment, 90},  // 3 months
	}

	baseTime := time.Now()

	for _, tt := range tests {
		t.Run(string(tt.checkType), func(t *testing.T) {
			expiryDate := handler.calculateExpiryDate(tt.checkType)
			expectedDate := baseTime.AddDate(0, 0, tt.expectedDays)
			
			// Allow for small time differences due to execution time
			diff := expiryDate.Sub(expectedDate)
			assert.Less(t, diff.Abs(), time.Minute)
		})
	}
}

// Benchmark tests for performance validation

func BenchmarkAMLCheckHandler_PerformAMLCheck(b *testing.B) {
	stub := shimtest.NewMockStub("aml_benchmark", nil)
	handler := NewAMLCheckHandler(nil)

	request := AMLCheckRequest{
		CustomerID: "BENCH_CUST_001",
		CustomerData: CustomerAMLData{
			FirstName:   "Benchmark",
			LastName:    "Customer",
			DateOfBirth: time.Date(1980, 1, 1, 0, 0, 0, 0, time.UTC),
			NationalID:  "BENCH123456789",
			Nationality: "US",
			Address:     "Benchmark Address",
			Country:     "US",
		},
		CheckType: AMLCheckTypeCustomerOnboarding,
		ActorID:   "BENCH_ACTOR",
	}

	requestBytes, _ := json.Marshal(request)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := handler.PerformAMLCheck(stub, []string{string(requestBytes)})
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkAMLCheckHandler_SanctionScreening(b *testing.B) {
	handler := NewAMLCheckHandler(nil)
	stub := shimtest.NewMockStub("sanction_benchmark", nil)

	customerData := CustomerAMLData{
		FirstName:   "Benchmark",
		LastName:    "Customer",
		DateOfBirth: time.Date(1980, 1, 1, 0, 0, 0, 0, time.UTC),
		Nationality: "US",
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := handler.performSanctionScreening(stub, &customerData, nil)
		if err != nil {
			b.Fatal(err)
		}
	}
}