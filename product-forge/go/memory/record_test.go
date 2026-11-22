package memory

import (
	"errors"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/google/uuid"
)

func validRecord() MemoryRecord {
	now := time.Now().UTC()
	validUntil := now.Add(24 * time.Hour)
	return MemoryRecord{
		ID:        uuid.New().String(),
		TenantID:  "tenant-core-001",
		ProjectID: "proj-alpha",
		Kind:      KindWorking,
		Scope:     "session",
		Authority: TierL1_Extracted,
		Provenance: ProvenanceInfo{
			CreatedBy: "agent:coder",
			CreatedAt: now,
		},
		Content:    "Canonical memory payload content",
		Confidence: 0.95,
		ValidFrom:  now,
		ValidUntil: &validUntil,
		Tags:       []string{"session_init", "auth_ok"},
		Metadata: map[string]any{
			"turn_index": 3,
			"verified":   true,
			"score":      0.88,
			"origin":     "cli",
		},
	}
}

func TestMemoryRecord_Validate_Success(t *testing.T) {
	rec := validRecord()
	if err := rec.Validate(); err != nil {
		t.Fatalf("expected valid record to pass, got: %v", err)
	}
}

func TestMemoryRecord_Validate_MissingRequiredFields(t *testing.T) {
	// Missing ID
	rec := validRecord()
	rec.ID = ""
	if err := rec.Validate(); !errors.Is(err, ErrInvalidID) {
		t.Errorf("expected ErrInvalidID, got: %v", err)
	}

	// Invalid UUID format
	rec = validRecord()
	rec.ID = "not-a-valid-uuid"
	if err := rec.Validate(); !errors.Is(err, ErrInvalidID) {
		t.Errorf("expected ErrInvalidID for malformed UUID, got: %v", err)
	}

	// Empty payload and payload_ref
	rec = validRecord()
	rec.Content = ""
	rec.PayloadRef = ""
	if err := rec.Validate(); !errors.Is(err, ErrEmptyPayload) {
		t.Errorf("expected ErrEmptyPayload, got: %v", err)
	}

	// Invalid Confidence
	rec = validRecord()
	rec.Confidence = 1.5
	if err := rec.Validate(); err == nil {
		t.Errorf("expected error for confidence > 1.0, got nil")
	}

	// Invalid SupersededBy UUID
	rec = validRecord()
	rec.SupersededBy = "malformed-uuid"
	if err := rec.Validate(); !errors.Is(err, ErrInvalidSupersededBy) {
		t.Errorf("expected ErrInvalidSupersededBy, got: %v", err)
	}
}

func TestMemoryRecord_TenantIsolation(t *testing.T) {
	rec := validRecord()
	if err := rec.ValidateTenant(); err != nil {
		t.Fatalf("expected tenant validation to pass, got: %v", err)
	}
}

func TestMemoryRecord_MissingTenant_FailsClosed(t *testing.T) {
	rec := validRecord()
	rec.TenantID = ""
	if err := rec.ValidateTenant(); !errors.Is(err, ErrMissingTenant) {
		t.Errorf("expected ErrMissingTenant, got: %v", err)
	}
	if err := rec.Validate(); !errors.Is(err, ErrMissingTenant) {
		t.Errorf("expected Validate() to fail on missing tenant, got: %v", err)
	}

	rec = validRecord()
	rec.ProjectID = ""
	if err := rec.ValidateTenant(); !errors.Is(err, ErrMissingProject) {
		t.Errorf("expected ErrMissingProject, got: %v", err)
	}
}

func TestMemoryKind_ValidTaxonomy(t *testing.T) {
	kinds := []MemoryKind{
		KindWorking,
		KindSemantic,
		KindEpisodic,
		KindProcedural,
		KindProspective,
		KindExternal,
	}

	for _, k := range kinds {
		if err := ValidateMemoryKind(k); err != nil {
			t.Errorf("expected kind %s to be valid, got: %v", k, err)
		}
	}
}

func TestMemoryKind_UnknownKind_FailsClosed(t *testing.T) {
	unknown := []MemoryKind{
		"unknown",
		"random_cache",
		"temporary",
		"",
	}

	for _, k := range unknown {
		if err := ValidateMemoryKind(k); !errors.Is(err, ErrInvalidKind) {
			t.Errorf("expected ErrInvalidKind for %q, got: %v", k, err)
		}
	}
}

func TestMapLegacyType_AllLegacyTypes(t *testing.T) {
	expected := map[string]MemoryKind{
		"short_term":        KindWorking,
		"working_memory":    KindWorking,
		"long_term_fact":    KindSemantic,
		"concept":           KindSemantic,
		"session_event":     KindEpisodic,
		"conversation_turn": KindEpisodic,
		"execution_step":    KindProcedural,
		"workflow_rule":     KindProcedural,
	}

	for legacy, expectedKind := range expected {
		kind, tags, err := MapLegacyType(legacy)
		if err != nil {
			t.Errorf("failed to map legacy type %q: %v", legacy, err)
			continue
		}
		if kind != expectedKind {
			t.Errorf("expected %q -> %s, got %s", legacy, expectedKind, kind)
		}
		if len(tags) == 0 {
			t.Errorf("expected preservation tag for %q, got none", legacy)
		}
	}
}

func TestMapLegacyType_Unknown_FailsClosed(t *testing.T) {
	_, _, err := MapLegacyType("non_existent_legacy_category")
	if !errors.Is(err, ErrUnknownLegacyType) {
		t.Errorf("expected ErrUnknownLegacyType, got: %v", err)
	}
}

func TestTemporalBounds_ValidRange(t *testing.T) {
	now := time.Now().UTC()
	future := now.Add(1 * time.Hour)

	if err := ValidateTemporalBounds(now, &future); err != nil {
		t.Fatalf("expected valid temporal bounds to pass, got: %v", err)
	}
	if err := ValidateTemporalBounds(now, nil); err != nil {
		t.Fatalf("expected nil valid_until (infinite validity) to pass, got: %v", err)
	}
}

func TestTemporalBounds_InvertedRange_FailsClosed(t *testing.T) {
	now := time.Now().UTC()
	past := now.Add(-1 * time.Hour)

	if err := ValidateTemporalBounds(now, &past); !errors.Is(err, ErrInvalidTemporalBounds) {
		t.Errorf("expected ErrInvalidTemporalBounds for inverted range, got: %v", err)
	}
}

func TestMemoryValidation_AuditLogged(t *testing.T) {
	var loggedStatus string
	var loggedID string
	AuditCallback = func(recordID, tenantID, status string, err error) {
		loggedID = recordID
		loggedStatus = status
	}
	defer func() { AuditCallback = nil }()

	rec := validRecord()
	if err := rec.Validate(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if loggedStatus != "PASS" || loggedID != rec.ID {
		t.Errorf("audit log mismatch: got status=%s, id=%s", loggedStatus, loggedID)
	}
}

func TestMemoryValidation_FailureAudit(t *testing.T) {
	var loggedStatus string
	AuditCallback = func(recordID, tenantID, status string, err error) {
		loggedStatus = status
	}
	defer func() { AuditCallback = nil }()

	rec := validRecord()
	rec.Kind = "invalid_kind"
	_ = rec.Validate()

	if loggedStatus != "FAIL" {
		t.Errorf("expected audit status FAIL, got: %s", loggedStatus)
	}
}

func TestMemoryRecord_PayloadLimits(t *testing.T) {
	rec := validRecord()
	rec.Embedding = make([]float32, 1536)
	if err := rec.Validate(); err != nil {
		t.Fatalf("expected 1536-dim embedding to pass, got: %v", err)
	}
}

func TestMemoryRecord_OversizedPayload_Rejected(t *testing.T) {
	rec := validRecord()
	rec.Content = strings.Repeat("a", MaxContentBytes+1)
	if err := rec.Validate(); !errors.Is(err, ErrPayloadTooLarge) {
		t.Errorf("expected ErrPayloadTooLarge, got: %v", err)
	}

	rec = validRecord()
	rec.Embedding = make([]float32, MaxEmbeddingDimensions+1)
	if err := rec.Validate(); !errors.Is(err, ErrEmbeddingTooLarge) {
		t.Errorf("expected ErrEmbeddingTooLarge, got: %v", err)
	}
}

func TestMemoryRecord_MetadataScalarValidation(t *testing.T) {
	rec := validRecord()
	// Nested map must fail closed to prevent arbitrary unversioned JSON structures
	rec.Metadata = map[string]any{
		"nested_object": map[string]any{"danger": "arbitrary"},
	}
	if err := rec.Validate(); !errors.Is(err, ErrInvalidMetadataScalar) {
		t.Errorf("expected ErrInvalidMetadataScalar for nested map, got: %v", err)
	}

	// Slice must fail closed
	rec.Metadata = map[string]any{
		"slice_value": []string{"a", "b"},
	}
	if err := rec.Validate(); !errors.Is(err, ErrInvalidMetadataScalar) {
		t.Errorf("expected ErrInvalidMetadataScalar for slice, got: %v", err)
	}
}

func TestMemoryRecord_ConcurrentValidation(t *testing.T) {
	var wg sync.WaitGroup
	rec := validRecord()

	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if err := rec.Validate(); err != nil {
				t.Errorf("concurrent validation failed: %v", err)
			}
		}()
	}
	wg.Wait()
}
