package memory

import (
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
)

//go:embed memory_legacy_mapping.json
var embeddedLegacyMappingJSON []byte

var (
	ErrInvalidID                   = errors.New("invalid record ID: must be valid UUID v4")
	ErrMissingTenant               = errors.New("missing mandatory tenant_id")
	ErrMissingProject              = errors.New("missing mandatory project_id")
	ErrInvalidKind                 = errors.New("invalid memory kind: unknown taxonomy classification")
	ErrInvalidAuthorityTier        = errors.New("invalid authority tier")
	ErrEmptyPayload                = errors.New("record must contain either non-empty content or payload_ref")
	ErrPayloadTooLarge             = errors.New("content exceeds maximum allowed size (1MB)")
	ErrEmbeddingTooLarge           = errors.New("embedding dimensions exceed configured maximum (3072)")
	ErrInvalidTemporalBounds       = errors.New("invalid temporal bounds: valid_from must be strictly before valid_until")
	ErrInvalidSupersededBy         = errors.New("invalid superseded_by identifier: must be valid UUID")
	ErrSelfReferencingSupersededBy = errors.New("record cannot supersede itself: superseded_by cannot equal id")
	ErrTooManyTags                 = errors.New("too many tags: maximum 50 allowed")
	ErrInvalidTagFormat            = errors.New("invalid tag format: must match ^[a-zA-Z0-9_.:-]+$")
	ErrTooManyMetadataEntries      = errors.New("too many metadata entries: maximum 50 allowed")
	ErrInvalidMetadataKey          = errors.New("invalid metadata key format: must match ^[a-zA-Z0-9_.:-]+$")
	ErrInvalidMetadataScalar       = errors.New("invalid metadata value: only scalar types (string, float64, bool, int64) allowed")
	ErrMetadataValueTooLarge       = errors.New("metadata string value exceeds maximum length (4096 bytes)")
	ErrInvalidPayloadRefScheme     = errors.New("invalid payload_ref: must be a well-formed URI using a supported scheme (s3, https, http, gs, file)")
	ErrUnknownLegacyType           = errors.New("unknown legacy memory type")
)

var identifierRegex = regexp.MustCompile(`^[a-zA-Z0-9_.:-]+$`)

const (
	MaxContentBytes        = 1048576 // 1MB
	MaxMetadataValueBytes  = 4096    // 4KB per metadata value
	MaxEmbeddingDimensions = 3072
	MaxTags                = 50
	MaxMetadataEntries     = 50
)

// MemoryKind defines the 6-kind taxonomy per Section 4 & 10 of Agent Memory Architecture.
type MemoryKind string

const (
	KindWorking     MemoryKind = "working"
	KindSemantic    MemoryKind = "semantic"
	KindEpisodic    MemoryKind = "episodic"
	KindProcedural  MemoryKind = "procedural"
	KindProspective MemoryKind = "prospective"
	KindExternal    MemoryKind = "external"
)

// AuthorityTier represents the epistemic weight of the record.
type AuthorityTier string

const (
	TierL0_Parametric     AuthorityTier = "L0_Parametric"
	TierL1_Extracted      AuthorityTier = "L1_Extracted"
	TierL2_Refined        AuthorityTier = "L2_Refined"
	TierL3_Synthesized    AuthorityTier = "L3_Synthesized"
	TierL4_GovernedPolicy AuthorityTier = "L4_GovernedPolicy"
	TierL5_RuntimeControl AuthorityTier = "L5_RuntimeControl"
)

// ProvenanceInfo captures origin tracking information.
type ProvenanceInfo struct {
	CreatedBy     string     `json:"created_by"`
	CreatedAt     time.Time  `json:"created_at"`
	ObservedAt    *time.Time `json:"observed_at,omitempty"`
	SourceEventID string     `json:"source_event_id,omitempty"`
}

// MemoryEvidence records verification and provenance audit.
type MemoryEvidence struct {
	Source     string `json:"source"`
	EventID    string `json:"event_id,omitempty"`
	RecordedBy string `json:"recorded_by"`
	Signature  string `json:"signature,omitempty"`
}

// MemoryRecord represents the canonical data contract for agent memory.
type MemoryRecord struct {
	ID           string         `json:"id"`
	TenantID     string         `json:"tenant_id"`
	ProjectID    string         `json:"project_id"`
	Kind         MemoryKind     `json:"kind"`
	Scope        string         `json:"scope"`
	Authority    AuthorityTier  `json:"authority_tier"`
	Provenance   ProvenanceInfo `json:"provenance"`
	Content      string         `json:"content"`
	PayloadRef   string         `json:"payload_ref,omitempty"`
	Confidence   float64        `json:"confidence"`
	ValidFrom    time.Time      `json:"valid_from"`
	ValidUntil   *time.Time     `json:"valid_until,omitempty"`
	SupersededBy string         `json:"superseded_by,omitempty"`
	Tags         []string       `json:"tags,omitempty"`
	EmbeddingRef string         `json:"embedding_ref,omitempty"`
	Embedding    []float32      `json:"embedding,omitempty"`
	Evidence     MemoryEvidence `json:"evidence,omitempty"`
	Metadata     map[string]any `json:"metadata,omitempty"`
}

// ValidateMemoryKind enforces the 6-kind taxonomy. Unknown kinds fail closed.
func ValidateMemoryKind(k MemoryKind) error {
	switch k {
	case KindWorking, KindSemantic, KindEpisodic, KindProcedural, KindProspective, KindExternal:
		return nil
	default:
		return fmt.Errorf("%w: %q", ErrInvalidKind, k)
	}
}

// ValidateAuthorityTier checks if the authority tier is recognized.
func ValidateAuthorityTier(a AuthorityTier) error {
	switch a {
	case TierL0_Parametric, TierL1_Extracted, TierL2_Refined, TierL3_Synthesized, TierL4_GovernedPolicy, TierL5_RuntimeControl:
		return nil
	default:
		return fmt.Errorf("%w: %q", ErrInvalidAuthorityTier, a)
	}
}

// ValidateTenant enforces tenant and project identity invariants.
func (r *MemoryRecord) ValidateTenant() error {
	if strings.TrimSpace(r.TenantID) == "" {
		return ErrMissingTenant
	}
	if strings.TrimSpace(r.ProjectID) == "" {
		return ErrMissingProject
	}
	return nil
}

// ValidateTemporalBounds asserts UTC time consistency and strict temporal ordering.
func ValidateTemporalBounds(from time.Time, until *time.Time) error {
	if from.IsZero() {
		return fmt.Errorf("%w: valid_from cannot be zero", ErrInvalidTemporalBounds)
	}
	if until != nil {
		if !from.Before(*until) || from.Equal(*until) {
			return fmt.Errorf("%w: valid_from (%v) must be strictly before valid_until (%v)", ErrInvalidTemporalBounds, from, *until)
		}
	}
	return nil
}

// ValidatePayloadBounds verifies content length and embedding dimensions.
func ValidatePayloadBounds(content string, embedding []float32) error {
	if len(content) > MaxContentBytes {
		return fmt.Errorf("%w: %d > %d", ErrPayloadTooLarge, len(content), MaxContentBytes)
	}
	if len(embedding) > MaxEmbeddingDimensions {
		return fmt.Errorf("%w: %d > %d", ErrEmbeddingTooLarge, len(embedding), MaxEmbeddingDimensions)
	}
	return nil
}

var (
	auditMu       sync.RWMutex
	auditCallback func(recordID, tenantID, status string, err error)
)

// SetAuditCallback registers a thread-safe telemetry listener.
func SetAuditCallback(fn func(recordID, tenantID, status string, err error)) {
	auditMu.Lock()
	defer auditMu.Unlock()
	auditCallback = fn
}

// EmitMemoryValidationAudit records structured validation audit events safely.
func EmitMemoryValidationAudit(recordID, tenantID, status string, err error) {
	auditMu.RLock()
	fn := auditCallback
	auditMu.RUnlock()
	if fn != nil {
		fn(recordID, tenantID, status, err)
	}
}

// Validate performs full canonical validation on the MemoryRecord.
func (r *MemoryRecord) Validate() error {
	// 1. UUID validation for ID
	if _, err := uuid.Parse(r.ID); err != nil {
		errOut := fmt.Errorf("%w: %v", ErrInvalidID, err)
		EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", errOut)
		return errOut
	}

	// 2. Tenant isolation validation
	if err := r.ValidateTenant(); err != nil {
		EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", err)
		return err
	}

	// 3. Taxonomy kind validation (fail-closed)
	if err := ValidateMemoryKind(r.Kind); err != nil {
		EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", err)
		return err
	}

	// 4. Authority tier validation
	if r.Authority != "" {
		if err := ValidateAuthorityTier(r.Authority); err != nil {
			EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", err)
			return err
		}
	}

	// 5. Payload presence & bounds
	if strings.TrimSpace(r.Content) == "" && strings.TrimSpace(r.PayloadRef) == "" {
		EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", ErrEmptyPayload)
		return ErrEmptyPayload
	}

	if r.PayloadRef != "" {
		u, err := url.Parse(r.PayloadRef)
		if err != nil || u.Scheme == "" {
			EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", ErrInvalidPayloadRefScheme)
			return ErrInvalidPayloadRefScheme
		}
		switch strings.ToLower(u.Scheme) {
		case "s3", "https", "http", "gs", "file":
			// Valid schemes
		default:
			EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", ErrInvalidPayloadRefScheme)
			return ErrInvalidPayloadRefScheme
		}
	}

	if err := ValidatePayloadBounds(r.Content, r.Embedding); err != nil {
		EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", err)
		return err
	}

	// 6. Confidence range (0.0 - 1.0)
	if r.Confidence < 0.0 || r.Confidence > 1.0 {
		errOut := fmt.Errorf("confidence must be between 0.0 and 1.0: got %f", r.Confidence)
		EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", errOut)
		return errOut
	}

	// 7. Temporal ordering (strictly valid_from < valid_until)
	if err := ValidateTemporalBounds(r.ValidFrom, r.ValidUntil); err != nil {
		EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", err)
		return err
	}

	// 8. SupersededBy UUID format and non-self-referencing check
	if strings.TrimSpace(r.SupersededBy) != "" {
		if strings.TrimSpace(r.SupersededBy) == strings.TrimSpace(r.ID) {
			EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", ErrSelfReferencingSupersededBy)
			return ErrSelfReferencingSupersededBy
		}
		if _, err := uuid.Parse(r.SupersededBy); err != nil {
			errOut := fmt.Errorf("%w: %v", ErrInvalidSupersededBy, err)
			EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", errOut)
			return errOut
		}
	}

	// 9. Tags validation
	if len(r.Tags) > MaxTags {
		EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", ErrTooManyTags)
		return ErrTooManyTags
	}
	for _, tag := range r.Tags {
		if !identifierRegex.MatchString(tag) {
			errOut := fmt.Errorf("%w: %q", ErrInvalidTagFormat, tag)
			EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", errOut)
			return errOut
		}
	}

	// 10. Metadata scalar validation (strictly reject nested maps/slices to avoid unversioned arbitrary objects)
	if len(r.Metadata) > MaxMetadataEntries {
		EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", ErrTooManyMetadataEntries)
		return ErrTooManyMetadataEntries
	}
	for k, v := range r.Metadata {
		if !identifierRegex.MatchString(k) {
			errOut := fmt.Errorf("%w: %q", ErrInvalidMetadataKey, k)
			EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", errOut)
			return errOut
		}
		if v == nil {
			continue
		}
		switch val := v.(type) {
		case string:
			if len(val) > MaxMetadataValueBytes {
				errOut := fmt.Errorf("%w: key %q exceeds %d bytes", ErrMetadataValueTooLarge, k, MaxMetadataValueBytes)
				EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", errOut)
				return errOut
			}
		case float64, float32, bool, int, int64, int32:
			// Allowed primitive scalars
		default:
			errOut := fmt.Errorf("%w: key %q has non-scalar type %T", ErrInvalidMetadataScalar, k, v)
			EmitMemoryValidationAudit(r.ID, r.TenantID, "FAIL", errOut)
			return errOut
		}
	}

	EmitMemoryValidationAudit(r.ID, r.TenantID, "PASS", nil)
	return nil
}

type legacyMappingPayload struct {
	Mappings map[string]struct {
		Kind string   `json:"kind"`
		Tags []string `json:"tags"`
	} `json:"mappings"`
}

var cachedLegacyMappings map[string]struct {
	Kind MemoryKind
	Tags []string
}

func init() {
	cachedLegacyMappings = make(map[string]struct {
		Kind MemoryKind
		Tags []string
	})

	var parsed legacyMappingPayload
	if err := json.Unmarshal(embeddedLegacyMappingJSON, &parsed); err == nil {
		for k, v := range parsed.Mappings {
			cachedLegacyMappings[k] = struct {
				Kind MemoryKind
				Tags []string
			}{
				Kind: MemoryKind(v.Kind),
				Tags: v.Tags,
			}
		}
	}
}

// MapLegacyType maps legacy 8 categories to canonical memory kinds with preservation tags.
func MapLegacyType(legacyType string) (MemoryKind, []string, error) {
	entry, found := cachedLegacyMappings[legacyType]
	if !found {
		return "", nil, fmt.Errorf("%w: %q", ErrUnknownLegacyType, legacyType)
	}
	return entry.Kind, entry.Tags, nil
}
