package handlers

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shimtest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestSanctionListManager_CreateSanctionList(t *testing.T) {
	stub := shimtest.NewMockStub("sanction_test", nil)
	mockEmitter := &MockEventEmitter{}
	manager := NewSanctionListManager(mockEmitter)

	tests := []struct {
		name          string
		listDef       SanctionListDefinition
		expectedError bool
	}{
		{
			name: "Valid sanction list creation",
			listDef: SanctionListDefinition{
				ListName:        "Test OFAC SDN List",
				Source:          "US Treasury OFAC",
				SourceURL:       "https://www.treasury.gov/ofac/downloads/sdnlist.txt",
				Description:     "Test OFAC Specially Designated Nationals List",
				ListType:        SanctionListTypeSDN,
				Jurisdiction:    "US",
				IsActive:        true,
				AutoUpdate:      true,
				UpdateFrequency: "DAILY",
				Version:         "1.0",
				Checksum:        "abc123def456",
				CreatedBy:       "ADMIN_001",
			},
			expectedError: false,
		},
		{
			name: "Valid UN sanctions list creation",
			listDef: SanctionListDefinition{
				ListName:        "UN Security Council Sanctions",
				Source:          "United Nations",
				SourceURL:       "https://www.un.org/securitycouncil/sanctions/list",
				Description:     "UN Security Council Consolidated List",
				ListType:        SanctionListTypeUN,
				Jurisdiction:    "INTERNATIONAL",
				IsActive:        true,
				AutoUpdate:      false,
				UpdateFrequency: "WEEKLY",
				Version:         "2.1",
				Checksum:        "xyz789abc123",
				CreatedBy:       "ADMIN_002",
			},
			expectedError: false,
		},
		{
			name: "Invalid list - missing name",
			listDef: SanctionListDefinition{
				Source:       "Test Source",
				Jurisdiction: "US",
				CreatedBy:    "ADMIN_001",
			},
			expectedError: true,
		},
		{
			name: "Invalid list - missing source",
			listDef: SanctionListDefinition{
				ListName:     "Test List",
				Jurisdiction: "US",
				CreatedBy:    "ADMIN_001",
			},
			expectedError: true,
		},
		{
			name: "Invalid list - missing jurisdiction",
			listDef: SanctionListDefinition{
				ListName:  "Test List",
				Source:    "Test Source",
				CreatedBy: "ADMIN_001",
			},
			expectedError: true,
		},
		{
			name: "Invalid list - missing created by",
			listDef: SanctionListDefinition{
				ListName:     "Test List",
				Source:       "Test Source",
				Jurisdiction: "US",
			},
			expectedError: true,
		},
		{
			name: "Invalid list type",
			listDef: SanctionListDefinition{
				ListName:     "Test List",
				Source:       "Test Source",
				Jurisdiction: "US",
				ListType:     SanctionListType("INVALID_TYPE"),
				CreatedBy:    "ADMIN_001",
			},
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			listDefBytes, err := json.Marshal(tt.listDef)
			require.NoError(t, err)

			result, err := manager.CreateSanctionList(stub, []string{string(listDefBytes)})

			if tt.expectedError {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, result)

			var createdList SanctionListDefinition
			err = json.Unmarshal(result, &createdList)
			require.NoError(t, err)

			assert.NotEmpty(t, createdList.ListID)
			assert.Equal(t, tt.listDef.ListName, createdList.ListName)
			assert.Equal(t, tt.listDef.Source, createdList.Source)
			assert.Equal(t, tt.listDef.ListType, createdList.ListType)
			assert.Equal(t, tt.listDef.Jurisdiction, createdList.Jurisdiction)
			assert.Equal(t, tt.listDef.CreatedBy, createdList.CreatedBy)
			assert.NotZero(t, createdList.CreatedDate)
			assert.NotZero(t, createdList.LastModifiedDate)
			assert.NotZero(t, createdList.NextUpdate)

			// Verify event was emitted
			assert.Len(t, mockEmitter.EmittedEvents, 1)
		})
	}
}

func TestSanctionListManager_UpdateSanctionList(t *testing.T) {
	stub := shimtest.NewMockStub("sanction_test", nil)
	mockEmitter := &MockEventEmitter{}
	manager := NewSanctionListManager(mockEmitter)

	// First create a sanction list
	listDef := SanctionListDefinition{
		ListName:        "Test OFAC SDN List",
		Source:          "US Treasury OFAC",
		Description:     "Test OFAC Specially Designated Nationals List",
		ListType:        SanctionListTypeSDN,
		Jurisdiction:    "US",
		IsActive:        true,
		AutoUpdate:      true,
		UpdateFrequency: "DAILY",
		Version:         "1.0",
		Checksum:        "abc123def456",
		CreatedBy:       "ADMIN_001",
	}

	listDefBytes, err := json.Marshal(listDef)
	require.NoError(t, err)

	result, err := manager.CreateSanctionList(stub, []string{string(listDefBytes)})
	require.NoError(t, err)

	var createdList SanctionListDefinition
	err = json.Unmarshal(result, &createdList)
	require.NoError(t, err)

	// Create test sanction entries
	testEntries := []ComprehensiveSanctionEntry{
		{
			EntryID:     "SDN_TEST_001",
			ListID:      createdList.ListID,
			PrimaryName: "John Doe",
			Aliases:     []string{"Johnny Doe", "J. Doe"},
			EntityType:  EntityTypeIndividual,
			FirstName:   "John",
			LastName:    "Doe",
			DateOfBirth: &time.Time{},
			Nationality: []string{"US"},
			Addresses: []SanctionAddress{
				{
					AddressID:   "ADDR_001",
					AddressType: "PRIMARY",
					Street:      "123 Main St",
					City:        "New York",
					State:       "NY",
					Country:     "US",
					IsActive:    true,
				},
			},
			SanctionType:   "SDN",
			SanctionReason: "Terrorism",
			SanctionDate:   time.Now(),
			IsActive:       true,
			RiskScore:      95.0,
			RiskCategory:   "HIGH",
		},
		{
			EntryID:     "SDN_TEST_002",
			ListID:      createdList.ListID,
			PrimaryName: "Evil Corp",
			EntityType:  EntityTypeOrganization,
			OrganizationType: "Corporation",
			Addresses: []SanctionAddress{
				{
					AddressID:   "ADDR_002",
					AddressType: "BUSINESS",
					Street:      "456 Corporate Blvd",
					City:        "Los Angeles",
					State:       "CA",
					Country:     "US",
					IsActive:    true,
				},
			},
			SanctionType:   "SDN",
			SanctionReason: "Money Laundering",
			SanctionDate:   time.Now(),
			IsActive:       true,
			RiskScore:      90.0,
			RiskCategory:   "HIGH",
		},
	}

	tests := []struct {
		name          string
		updateReq     SanctionListUpdateRequest
		expectedError bool
	}{
		{
			name: "Valid full replace update",
			updateReq: SanctionListUpdateRequest{
				ListID:      createdList.ListID,
				UpdateType:  UpdateTypeFull,
				Entries:     testEntries,
				Version:     "2.0",
				Checksum:    "new_checksum_123",
				UpdatedBy:   "ADMIN_002",
				UpdateNotes: "Full list replacement with new entries",
			},
			expectedError: false,
		},
		{
			name: "Valid incremental update",
			updateReq: SanctionListUpdateRequest{
				ListID:      createdList.ListID,
				UpdateType:  UpdateTypeIncremental,
				Entries:     testEntries[:1], // Only first entry
				Version:     "2.1",
				Checksum:    "incremental_checksum_456",
				UpdatedBy:   "ADMIN_002",
				UpdateNotes: "Incremental update with one new entry",
			},
			expectedError: false,
		},
		{
			name: "Valid additions only update",
			updateReq: SanctionListUpdateRequest{
				ListID:      createdList.ListID,
				UpdateType:  UpdateTypeAdditions,
				Entries:     []ComprehensiveSanctionEntry{testEntries[1]}, // Second entry only
				Version:     "2.2",
				Checksum:    "additions_checksum_789",
				UpdatedBy:   "ADMIN_002",
				UpdateNotes: "Adding new entries only",
			},
			expectedError: false,
		},
		{
			name: "Invalid update - missing list ID",
			updateReq: SanctionListUpdateRequest{
				UpdateType: UpdateTypeFull,
				Entries:    testEntries,
				Version:    "3.0",
				UpdatedBy:  "ADMIN_002",
			},
			expectedError: true,
		},
		{
			name: "Invalid update - missing version",
			updateReq: SanctionListUpdateRequest{
				ListID:     createdList.ListID,
				UpdateType: UpdateTypeFull,
				Entries:    testEntries,
				UpdatedBy:  "ADMIN_002",
			},
			expectedError: true,
		},
		{
			name: "Invalid update - missing updated by",
			updateReq: SanctionListUpdateRequest{
				ListID:     createdList.ListID,
				UpdateType: UpdateTypeFull,
				Entries:    testEntries,
				Version:    "3.0",
			},
			expectedError: true,
		},
		{
			name: "Invalid update - invalid update type",
			updateReq: SanctionListUpdateRequest{
				ListID:     createdList.ListID,
				UpdateType: SanctionUpdateType("INVALID_TYPE"),
				Entries:    testEntries,
				Version:    "3.0",
				UpdatedBy:  "ADMIN_002",
			},
			expectedError: true,
		},
		{
			name: "Invalid update - non-existent list ID",
			updateReq: SanctionListUpdateRequest{
				ListID:     "NON_EXISTENT_LIST",
				UpdateType: UpdateTypeFull,
				Entries:    testEntries,
				Version:    "3.0",
				UpdatedBy:  "ADMIN_002",
			},
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			updateReqBytes, err := json.Marshal(tt.updateReq)
			require.NoError(t, err)

			result, err := manager.UpdateSanctionList(stub, []string{string(updateReqBytes)})

			if tt.expectedError {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, result)

			var updateResult SanctionListUpdateResult
			err = json.Unmarshal(result, &updateResult)
			require.NoError(t, err)

			assert.Equal(t, tt.updateReq.ListID, updateResult.ListID)
			assert.Equal(t, tt.updateReq.UpdateType, updateResult.UpdateType)
			assert.NotZero(t, updateResult.UpdateDate)
			assert.GreaterOrEqual(t, updateResult.ProcessingTime, int64(0))

			// Verify counts based on update type
			switch tt.updateReq.UpdateType {
			case UpdateTypeFull:
				assert.Equal(t, len(tt.updateReq.Entries), updateResult.AddedEntries)
				assert.Equal(t, len(tt.updateReq.Entries), updateResult.TotalEntries)
			case UpdateTypeAdditions:
				assert.Equal(t, len(tt.updateReq.Entries), updateResult.AddedEntries)
				assert.GreaterOrEqual(t, updateResult.TotalEntries, updateResult.AddedEntries)
			}
		})
	}
}

func TestSanctionListManager_GetSanctionList(t *testing.T) {
	stub := shimtest.NewMockStub("sanction_test", nil)
	mockEmitter := &MockEventEmitter{}
	manager := NewSanctionListManager(mockEmitter)

	// Create a test sanction list
	listDef := SanctionListDefinition{
		ListName:        "Test List for Retrieval",
		Source:          "Test Source",
		Description:     "Test list for retrieval testing",
		ListType:        SanctionListTypeCustom,
		Jurisdiction:    "TEST",
		IsActive:        true,
		AutoUpdate:      false,
		UpdateFrequency: "MONTHLY",
		Version:         "1.0",
		Checksum:        "test_checksum",
		CreatedBy:       "TEST_ADMIN",
	}

	listDefBytes, err := json.Marshal(listDef)
	require.NoError(t, err)

	createResult, err := manager.CreateSanctionList(stub, []string{string(listDefBytes)})
	require.NoError(t, err)

	var createdList SanctionListDefinition
	err = json.Unmarshal(createResult, &createdList)
	require.NoError(t, err)

	tests := []struct {
		name          string
		listID        string
		expectedError bool
	}{
		{
			name:          "Valid list ID",
			listID:        createdList.ListID,
			expectedError: false,
		},
		{
			name:          "Invalid list ID",
			listID:        "NON_EXISTENT_LIST",
			expectedError: true,
		},
		{
			name:          "Empty list ID",
			listID:        "",
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := manager.GetSanctionList(stub, []string{tt.listID})

			if tt.expectedError {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, result)

			var retrievedList SanctionListDefinition
			err = json.Unmarshal(result, &retrievedList)
			require.NoError(t, err)

			assert.Equal(t, createdList.ListID, retrievedList.ListID)
			assert.Equal(t, createdList.ListName, retrievedList.ListName)
			assert.Equal(t, createdList.Source, retrievedList.Source)
			assert.Equal(t, createdList.ListType, retrievedList.ListType)
		})
	}
}

func TestSanctionListManager_GetActiveSanctionLists(t *testing.T) {
	stub := shimtest.NewMockStub("sanction_test", nil)
	mockEmitter := &MockEventEmitter{}
	manager := NewSanctionListManager(mockEmitter)

	// Create multiple sanction lists with different active states
	lists := []SanctionListDefinition{
		{
			ListName:     "Active List 1",
			Source:       "Source 1",
			ListType:     SanctionListTypeSDN,
			Jurisdiction: "US",
			IsActive:     true,
			CreatedBy:    "ADMIN_001",
		},
		{
			ListName:     "Active List 2",
			Source:       "Source 2",
			ListType:     SanctionListTypeUN,
			Jurisdiction: "INTERNATIONAL",
			IsActive:     true,
			CreatedBy:    "ADMIN_002",
		},
		{
			ListName:     "Inactive List",
			Source:       "Source 3",
			ListType:     SanctionListTypeEU,
			Jurisdiction: "EU",
			IsActive:     false,
			CreatedBy:    "ADMIN_003",
		},
	}

	// Create all lists
	for _, listDef := range lists {
		listDefBytes, err := json.Marshal(listDef)
		require.NoError(t, err)

		_, err = manager.CreateSanctionList(stub, []string{string(listDefBytes)})
		require.NoError(t, err)
	}

	// Get active lists
	result, err := manager.GetActiveSanctionLists(stub, []string{})
	require.NoError(t, err)
	require.NotNil(t, result)

	var activeLists []SanctionListDefinition
	err = json.Unmarshal(result, &activeLists)
	require.NoError(t, err)

	// Should only return active lists
	assert.Len(t, activeLists, 2)

	for _, list := range activeLists {
		assert.True(t, list.IsActive)
	}
}

func TestSanctionListManager_SearchSanctionEntries(t *testing.T) {
	stub := shimtest.NewMockStub("sanction_test", nil)
	mockEmitter := &MockEventEmitter{}
	manager := NewSanctionListManager(mockEmitter)

	// Create a sanction list
	listDef := SanctionListDefinition{
		ListName:     "Test Search List",
		Source:       "Test Source",
		ListType:     SanctionListTypeCustom,
		Jurisdiction: "TEST",
		IsActive:     true,
		CreatedBy:    "TEST_ADMIN",
	}

	listDefBytes, err := json.Marshal(listDef)
	require.NoError(t, err)

	createResult, err := manager.CreateSanctionList(stub, []string{string(listDefBytes)})
	require.NoError(t, err)

	var createdList SanctionListDefinition
	err = json.Unmarshal(createResult, &createdList)
	require.NoError(t, err)

	// Add some test entries
	testEntries := []ComprehensiveSanctionEntry{
		{
			EntryID:     "SEARCH_TEST_001",
			ListID:      createdList.ListID,
			PrimaryName: "John Smith",
			EntityType:  EntityTypeIndividual,
			FirstName:   "John",
			LastName:    "Smith",
			IsActive:    true,
		},
		{
			EntryID:     "SEARCH_TEST_002",
			ListID:      createdList.ListID,
			PrimaryName: "Jane Doe",
			EntityType:  EntityTypeIndividual,
			FirstName:   "Jane",
			LastName:    "Doe",
			IsActive:    true,
		},
		{
			EntryID:     "SEARCH_TEST_003",
			ListID:      createdList.ListID,
			PrimaryName: "Evil Corporation",
			EntityType:  EntityTypeOrganization,
			IsActive:    true,
		},
	}

	// Add entries to the list
	updateReq := SanctionListUpdateRequest{
		ListID:     createdList.ListID,
		UpdateType: UpdateTypeAdditions,
		Entries:    testEntries,
		Version:    "1.1",
		UpdatedBy:  "TEST_ADMIN",
	}

	updateReqBytes, err := json.Marshal(updateReq)
	require.NoError(t, err)

	_, err = manager.UpdateSanctionList(stub, []string{string(updateReqBytes)})
	require.NoError(t, err)

	tests := []struct {
		name           string
		searchReq      map[string]interface{}
		expectedCount  int
		expectedError  bool
	}{
		{
			name: "Search by name - exact match",
			searchReq: map[string]interface{}{
				"searchTerm": "JOHN SMITH",
				"limit":      10,
			},
			expectedCount: 1,
		},
		{
			name: "Search by entity type - individuals",
			searchReq: map[string]interface{}{
				"searchTerm": "JOHN",
				"entityType": "INDIVIDUAL",
				"limit":      10,
			},
			expectedCount: 1,
		},
		{
			name: "Search by entity type - organizations",
			searchReq: map[string]interface{}{
				"searchTerm": "EVIL",
				"entityType": "ORGANIZATION",
				"limit":      10,
			},
			expectedCount: 1,
		},
		{
			name: "Search with list ID filter",
			searchReq: map[string]interface{}{
				"searchTerm": "JOHN",
				"listID":     createdList.ListID,
				"limit":      10,
			},
			expectedCount: 1,
		},
		{
			name: "Search with non-existent list ID",
			searchReq: map[string]interface{}{
				"searchTerm": "JOHN",
				"listID":     "NON_EXISTENT",
				"limit":      10,
			},
			expectedCount: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			searchReqBytes, err := json.Marshal(tt.searchReq)
			require.NoError(t, err)

			result, err := manager.SearchSanctionEntries(stub, []string{string(searchReqBytes)})

			if tt.expectedError {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, result)

			var searchResults []ComprehensiveSanctionEntry
			err = json.Unmarshal(result, &searchResults)
			require.NoError(t, err)

			assert.Len(t, searchResults, tt.expectedCount)

			// Verify search results contain expected data
			for _, entry := range searchResults {
				assert.NotEmpty(t, entry.EntryID)
				assert.NotEmpty(t, entry.PrimaryName)
				assert.True(t, entry.IsActive)
			}
		})
	}
}

func TestSanctionListManager_ValidationMethods(t *testing.T) {
	manager := NewSanctionListManager(nil)

	t.Run("validateSanctionListDefinition", func(t *testing.T) {
		validList := SanctionListDefinition{
			ListName:     "Valid List",
			Source:       "Valid Source",
			Jurisdiction: "US",
			ListType:     SanctionListTypeSDN,
			CreatedBy:    "ADMIN_001",
		}

		err := manager.validateSanctionListDefinition(&validList)
		assert.NoError(t, err)

		// Test missing required fields
		invalidLists := []SanctionListDefinition{
			{Source: "Source", Jurisdiction: "US", ListType: SanctionListTypeSDN, CreatedBy: "ADMIN"}, // Missing ListName
			{ListName: "Name", Jurisdiction: "US", ListType: SanctionListTypeSDN, CreatedBy: "ADMIN"}, // Missing Source
			{ListName: "Name", Source: "Source", ListType: SanctionListTypeSDN, CreatedBy: "ADMIN"},   // Missing Jurisdiction
			{ListName: "Name", Source: "Source", Jurisdiction: "US", CreatedBy: "ADMIN"},              // Missing ListType
			{ListName: "Name", Source: "Source", Jurisdiction: "US", ListType: SanctionListTypeSDN},   // Missing CreatedBy
		}

		for i, invalidList := range invalidLists {
			err := manager.validateSanctionListDefinition(&invalidList)
			assert.Error(t, err, "Expected error for invalid list %d", i)
		}
	})

	t.Run("validateSanctionEntry", func(t *testing.T) {
		validEntry := ComprehensiveSanctionEntry{
			EntryID:     "VALID_001",
			PrimaryName: "Valid Name",
			EntityType:  EntityTypeIndividual,
		}

		err := manager.validateSanctionEntry(&validEntry)
		assert.NoError(t, err)

		// Test missing required fields
		invalidEntries := []ComprehensiveSanctionEntry{
			{PrimaryName: "Name", EntityType: EntityTypeIndividual},                    // Missing EntryID
			{EntryID: "ID", EntityType: EntityTypeIndividual},                          // Missing PrimaryName
			{EntryID: "ID", PrimaryName: "Name"},                                       // Missing EntityType
			{EntryID: "ID", PrimaryName: "Name", EntityType: SanctionEntityType("INVALID")}, // Invalid EntityType
		}

		for i, invalidEntry := range invalidEntries {
			err := manager.validateSanctionEntry(&invalidEntry)
			assert.Error(t, err, "Expected error for invalid entry %d", i)
		}
	})
}

func TestSanctionListManager_UtilityMethods(t *testing.T) {
	manager := NewSanctionListManager(nil)

	t.Run("calculateNextUpdate", func(t *testing.T) {
		baseTime := time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC)

		tests := []struct {
			frequency    string
			expectedDays int
		}{
			{"DAILY", 1},
			{"WEEKLY", 7},
			{"MONTHLY", 31}, // January has 31 days
			{"INVALID", 31}, // Default to monthly
		}

		for _, tt := range tests {
			nextUpdate := manager.calculateNextUpdate(tt.frequency, baseTime)
			expectedDate := baseTime.AddDate(0, 0, tt.expectedDays)
			
			if tt.frequency == "MONTHLY" || tt.frequency == "INVALID" {
				expectedDate = baseTime.AddDate(0, 1, 0) // Add one month
			}
			
			assert.Equal(t, expectedDate, nextUpdate, "Frequency: %s", tt.frequency)
		}
	})
}

// Benchmark tests for performance validation

func BenchmarkSanctionListManager_CreateSanctionList(b *testing.B) {
	stub := shimtest.NewMockStub("sanction_benchmark", nil)
	manager := NewSanctionListManager(nil)

	listDef := SanctionListDefinition{
		ListName:        "Benchmark List",
		Source:          "Benchmark Source",
		Description:     "Benchmark test list",
		ListType:        SanctionListTypeCustom,
		Jurisdiction:    "BENCH",
		IsActive:        true,
		AutoUpdate:      false,
		UpdateFrequency: "MONTHLY",
		Version:         "1.0",
		Checksum:        "bench_checksum",
		CreatedBy:       "BENCH_ADMIN",
	}

	listDefBytes, _ := json.Marshal(listDef)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		// Use unique list name for each iteration
		listDef.ListName = fmt.Sprintf("Benchmark List %d", i)
		listDefBytes, _ = json.Marshal(listDef)
		
		_, err := manager.CreateSanctionList(stub, []string{string(listDefBytes)})
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkSanctionListManager_UpdateSanctionList(b *testing.B) {
	stub := shimtest.NewMockStub("sanction_benchmark", nil)
	manager := NewSanctionListManager(nil)

	// Create a base list
	listDef := SanctionListDefinition{
		ListName:     "Benchmark Update List",
		Source:       "Benchmark Source",
		ListType:     SanctionListTypeCustom,
		Jurisdiction: "BENCH",
		IsActive:     true,
		CreatedBy:    "BENCH_ADMIN",
	}

	listDefBytes, _ := json.Marshal(listDef)
	result, err := manager.CreateSanctionList(stub, []string{string(listDefBytes)})
	if err != nil {
		b.Fatal(err)
	}

	var createdList SanctionListDefinition
	json.Unmarshal(result, &createdList)

	// Prepare update request
	testEntry := ComprehensiveSanctionEntry{
		EntryID:     "BENCH_001",
		ListID:      createdList.ListID,
		PrimaryName: "Benchmark Entry",
		EntityType:  EntityTypeIndividual,
		IsActive:    true,
	}

	updateReq := SanctionListUpdateRequest{
		ListID:     createdList.ListID,
		UpdateType: UpdateTypeAdditions,
		Entries:    []ComprehensiveSanctionEntry{testEntry},
		Version:    "1.1",
		UpdatedBy:  "BENCH_ADMIN",
	}

	updateReqBytes, _ := json.Marshal(updateReq)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		// Use unique entry ID for each iteration
		testEntry.EntryID = fmt.Sprintf("BENCH_%d", i)
		updateReq.Entries = []ComprehensiveSanctionEntry{testEntry}
		updateReq.Version = fmt.Sprintf("1.%d", i+1)
		updateReqBytes, _ = json.Marshal(updateReq)
		
		_, err := manager.UpdateSanctionList(stub, []string{string(updateReqBytes)})
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkSanctionListManager_SearchSanctionEntries(b *testing.B) {
	stub := shimtest.NewMockStub("sanction_benchmark", nil)
	manager := NewSanctionListManager(nil)

	// Create a list with entries for searching
	listDef := SanctionListDefinition{
		ListName:     "Benchmark Search List",
		Source:       "Benchmark Source",
		ListType:     SanctionListTypeCustom,
		Jurisdiction: "BENCH",
		IsActive:     true,
		CreatedBy:    "BENCH_ADMIN",
	}

	listDefBytes, _ := json.Marshal(listDef)
	result, _ := manager.CreateSanctionList(stub, []string{string(listDefBytes)})

	var createdList SanctionListDefinition
	json.Unmarshal(result, &createdList)

	// Add multiple entries for searching
	entries := make([]ComprehensiveSanctionEntry, 100)
	for i := 0; i < 100; i++ {
		entries[i] = ComprehensiveSanctionEntry{
			EntryID:     fmt.Sprintf("SEARCH_BENCH_%d", i),
			ListID:      createdList.ListID,
			PrimaryName: fmt.Sprintf("Benchmark Person %d", i),
			EntityType:  EntityTypeIndividual,
			IsActive:    true,
		}
	}

	updateReq := SanctionListUpdateRequest{
		ListID:     createdList.ListID,
		UpdateType: UpdateTypeAdditions,
		Entries:    entries,
		Version:    "1.1",
		UpdatedBy:  "BENCH_ADMIN",
	}

	updateReqBytes, _ := json.Marshal(updateReq)
	manager.UpdateSanctionList(stub, []string{string(updateReqBytes)})

	searchReq := map[string]interface{}{
		"searchTerm": "BENCHMARK PERSON",
		"limit":      50,
	}

	searchReqBytes, _ := json.Marshal(searchReq)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := manager.SearchSanctionEntries(stub, []string{string(searchReqBytes)})
		if err != nil {
			b.Fatal(err)
		}
	}
}