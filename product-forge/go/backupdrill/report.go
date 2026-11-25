package backupdrill

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"time"
)

// DrillRecord is persisted per command so cadence/staleness can be alerted on.
type DrillRecord struct {
	Command string          `json:"command"`
	At      time.Time       `json:"at"`
	OK      bool            `json:"ok"`
	Report  json.RawMessage `json:"report"`
}

// SaveReport writes <dir>/<command>-<utc>.json.
func SaveReport(dir, command string, ok bool, report any) (string, error) {
	if dir == "" {
		return "", nil
	}
	if err := os.MkdirAll(dir, 0o750); err != nil {
		return "", err
	}
	raw, err := json.Marshal(report)
	if err != nil {
		return "", err
	}
	rec := DrillRecord{Command: command, At: time.Now().UTC(), OK: ok, Report: raw}
	b, err := json.MarshalIndent(rec, "", "  ")
	if err != nil {
		return "", err
	}
	path := filepath.Join(dir, fmt.Sprintf("%s-%s.json", command, rec.At.Format("20060102T150405Z")))
	if err := os.WriteFile(path, b, 0o640); err != nil {
		return "", err
	}
	return path, nil
}

// LatestReport returns the newest record for command.
func LatestReport(dir, command string) (DrillRecord, error) {
	var rec DrillRecord
	paths, err := filepath.Glob(filepath.Join(dir, command+"-*.json"))
	if err != nil {
		return rec, err
	}
	if len(paths) == 0 {
		return rec, fmt.Errorf("backupdrill: no %s report in %s", command, dir)
	}
	sort.Strings(paths)
	b, err := os.ReadFile(paths[len(paths)-1])
	if err != nil {
		return rec, err
	}
	if err := json.Unmarshal(b, &rec); err != nil {
		return rec, err
	}
	return rec, nil
}

// CheckFreshness fails when a required command has no fresh, successful report.
func CheckFreshness(dir string, commands []string, maxAge time.Duration) error {
	for _, c := range commands {
		rec, err := LatestReport(dir, c)
		if err != nil {
			return err
		}
		if !rec.OK {
			return fmt.Errorf("backupdrill: last %s drill FAILED (%s)", c, rec.At.Format(time.RFC3339))
		}
		if age := time.Since(rec.At); age > maxAge {
			return fmt.Errorf("backupdrill: last %s drill is stale (%s old > %s)", c, age.Round(time.Minute), maxAge)
		}
	}
	return nil
}
