// Package backlogctx parses a plan/design document into per-item backlog field projections.
//
// Document format: a heading containing an item id ("## BI-PF-1309 ...") starts a section; inside it,
// "field: value" lines set a field and bullet lines following a bare "field:" collect a list. Only
// whitelisted fields are read. See ADR-0007/0008 (generic capability service; logic in Go).
package backlogctx

import (
	"regexp"
	"strings"
)

var (
	itemHeading = regexp.MustCompile(`(?i)^\s{0,3}#{1,6}\s+(.*?)\b(BI-PF-\d+)\b(.*)$`)
	fieldLine   = regexp.MustCompile(`(?i)^\s*(?:[-*]\s+)?([a-z_]+)\s*[:=]\s*(.*)$`)
	bullet      = regexp.MustCompile(`^\s*(?:[-*]|\d+\.)\s+(.*)$`)
	trimLead    = regexp.MustCompile(`^[\s\-–—:.]*`)
)

func set(names ...string) map[string]bool {
	m := make(map[string]bool, len(names))
	for _, n := range names {
		m[n] = true
	}
	return m
}

var (
	contextFields = set("objective", "acceptance_criteria", "in_scope", "out_of_scope",
		"affected_components", "affected_files", "approach", "verification", "risks", "rollback",
		"evidence", "owner", "summary", "brief")
	editableFields = set("title", "body", "type", "label", "tag", "origin", "value", "effort", "risk", "moscow")
	depFields      = set("dependencies", "blocked_by")
	listFields     = set("acceptance_criteria", "in_scope", "out_of_scope", "affected_components",
		"affected_files", "verification", "risks", "evidence", "dependencies", "blocked_by")
)

func isKnown(f string) bool {
	return contextFields[f] || editableFields[f] || depFields[f]
}

func coerce(field, raw string) any {
	value := strings.TrimSpace(raw)
	if field == "brief" {
		return map[string]any{"what_adds": value}
	}
	if listFields[field] {
		parts := strings.Split(value, ",")
		out := make([]string, 0, len(parts))
		for _, p := range parts {
			if s := strings.TrimSpace(p); s != "" {
				out = append(out, s)
			}
		}
		return out
	}
	return value
}

// Parse returns {item_id: {field: value}} from the document text.
func Parse(text string) map[string]map[string]any {
	sections := map[string]map[string]any{}
	cur := ""
	curField := ""
	for _, raw := range strings.Split(text, "\n") {
		if m := itemHeading.FindStringSubmatch(raw); m != nil {
			cur = strings.ToUpper(m[2])
			if sections[cur] == nil {
				sections[cur] = map[string]any{}
			}
			title := strings.TrimSpace(trimLead.ReplaceAllString(strings.TrimSpace(m[1])+" "+strings.TrimSpace(m[3]), ""))
			if title != "" && sections[cur]["title"] == nil {
				sections[cur]["title"] = title
			}
			curField = ""
			continue
		}
		if cur == "" {
			continue
		}
		if strings.TrimSpace(raw) == "" {
			curField = ""
			continue
		}
		if m := fieldLine.FindStringSubmatch(raw); m != nil && isKnown(strings.ToLower(m[1])) {
			key := strings.ToLower(m[1])
			val := strings.TrimSpace(m[2])
			if val != "" {
				sections[cur][key] = coerce(key, val)
				curField = ""
			} else {
				if _, ok := sections[cur][key]; !ok {
					sections[cur][key] = []string{}
				}
				curField = key
			}
			continue
		}
		if m := bullet.FindStringSubmatch(raw); m != nil && curField != "" {
			list, _ := sections[cur][curField].([]string)
			sections[cur][curField] = append(list, strings.TrimSpace(m[1]))
		}
	}
	for id, fields := range sections {
		if len(fields) == 0 {
			delete(sections, id)
		}
	}
	return sections
}

// IsMissing reports whether a current field value is absent/empty.
func IsMissing(v any) bool {
	switch t := v.(type) {
	case nil:
		return true
	case string:
		return strings.TrimSpace(t) == ""
	case []string:
		return len(t) == 0
	case []any:
		return len(t) == 0
	case map[string]any:
		return len(t) == 0
	}
	return false
}

// Changes returns the desired fields that should be written (missing-only unless overwrite).
func Changes(current, desired map[string]any, overwrite bool) map[string]any {
	out := map[string]any{}
	for k, v := range desired {
		if overwrite || IsMissing(current[k]) {
			out[k] = v
		}
	}
	return out
}

// Route splits fields into context / editable / dependencies groups for the backlog API.
func Route(fields map[string]any) (ctx, edit, deps map[string]any) {
	ctx, edit, deps = map[string]any{}, map[string]any{}, map[string]any{}
	for k, v := range fields {
		switch {
		case contextFields[k]:
			ctx[k] = v
		case editableFields[k]:
			edit[k] = v
		case depFields[k]:
			deps[k] = v
		}
	}
	return ctx, edit, deps
}
