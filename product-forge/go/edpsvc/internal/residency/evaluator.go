package residency

import "strings"

// PolicyEvaluator is the concrete Evaluator (the seam defined by EDP-05/BI-PF-1297). It decides whether a
// cross-border transfer is permitted by a policy, deterministically and fail-closed on unknown transfer modes.
type PolicyEvaluator struct{}

// Evaluate returns the residency decision for req under policy. Same-region (or empty target) is allowed;
// otherwise the policy's cross_border_transfer mode governs, and an unknown mode is denied (fail-closed).
func (PolicyEvaluator) Evaluate(req TransferRequest, policy Policy) (Decision, error) {
	d := Decision{PolicyID: policy.ID, PolicyVer: policy.Version}
	target := strings.ToUpper(strings.TrimSpace(req.Target))
	origin := strings.ToUpper(strings.TrimSpace(req.Region))
	if target == "" || target == origin {
		d.Allowed = true
		d.Reasons = []string{"intra-region"}
		return d, nil
	}
	allowed := false
	for _, r := range policy.AllowedRegions {
		if strings.ToUpper(strings.TrimSpace(r)) == target {
			allowed = true
			break
		}
	}
	switch strings.ToLower(strings.TrimSpace(policy.CrossBorderTransfer)) {
	case "allowed":
		d.Allowed = true
		d.Reasons = []string{"cross-border allowed by policy"}
	case "conditioned":
		d.Allowed = allowed
		if allowed {
			d.Reasons = []string{"target is in allowed_regions (conditioned)"}
		} else {
			d.Reasons = []string{"target not in allowed_regions (conditioned)"}
		}
	case "restricted":
		d.Allowed = allowed
		if allowed {
			d.Reasons = []string{"target is in allowed_regions"}
		} else {
			d.Reasons = []string{"cross-border restricted by policy"}
		}
	default:
		d.Allowed = false
		d.Reasons = []string{"unknown cross_border_transfer mode -> fail-closed"}
	}
	return d, nil
}
