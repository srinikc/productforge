package eventtransport

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/smtp"
	"os"
	"strings"
	"time"

	"productforge/edpdata"
)

type SMTPConfig struct {
	Host, Port, User, Password, From string
	TLS                              bool
}

type Notify struct {
	APIURL      string
	Client      *http.Client
	MinPriority string
	SMTP        SMTPConfig
}

func NewNotify() *Notify {
	api := os.Getenv("PF_NOTIFY_API_URL")
	if api == "" {
		api = "http://127.0.0.1:8000"
	}
	return &Notify{APIURL: strings.TrimRight(api, "/"), Client: &http.Client{Timeout: 10 * time.Second},
		MinPriority: firstNonEmpty(os.Getenv("PF_NOTIFY_EMAIL_MIN_PRIORITY"), "medium"),
		SMTP: SMTPConfig{Host: os.Getenv("PF_SMTP_HOST"), Port: firstNonEmpty(os.Getenv("PF_SMTP_PORT"), "587"),
			User: os.Getenv("PF_SMTP_USER"), Password: os.Getenv("PF_SMTP_PASSWORD"), From: os.Getenv("PF_SMTP_FROM"), TLS: os.Getenv("PF_SMTP_TLS") != "false"}}
}
func firstNonEmpty(v, d string) string {
	if strings.TrimSpace(v) != "" {
		return v
	}
	return d
}

func (n *Notify) Deliver(ctx context.Context, sub edpdata.Subscription, ev edpdata.Event) error {
	priority := priorityOf(ev.Type)
	payload := map[string]any{"project": sub.TenantID, "notification_type": "custom", "title": ev.Type, "message": string(ev.Payload), "priority": priority}
	body, _ := json.Marshal(payload)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, n.APIURL+"/api/v1/notifications", bytes.NewReader(body))
	if err != nil {
		return edpdata.PermanentError{Err: err}
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Idempotency-Key", ev.EventID)
	if tok := os.Getenv("PF_API_TOKEN"); tok != "" {
		req.Header.Set("Authorization", "Bearer "+tok)
	}
	resp, err := n.Client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("notification API status %d", resp.StatusCode)
	}
	if !emailEligible(priority, n.MinPriority) || n.SMTP.Host == "" || n.SMTP.From == "" {
		return nil
	}
	return n.sendEmail(sub, ev, priority)
}
func priorityOf(eventType string) string {
	switch {
	case strings.Contains(eventType, "critical"):
		return "critical"
	case strings.Contains(eventType, "high"):
		return "high"
	case strings.Contains(eventType, "low"):
		return "low"
	default:
		return "medium"
	}
}
func emailEligible(priority, min string) bool {
	rank := map[string]int{"low": 1, "medium": 2, "high": 3, "critical": 4}
	return rank[priority] >= rank[strings.ToLower(min)]
}
func (n *Notify) sendEmail(sub edpdata.Subscription, ev edpdata.Event, priority string) error {
	addr := n.SMTP.Host + ":" + n.SMTP.Port
	auth := smtp.PlainAuth("", n.SMTP.User, n.SMTP.Password, n.SMTP.Host)
	msg := []byte("To: " + n.SMTP.From + "\r\nSubject: [PF " + priority + "] " + ev.Type + "\r\n\r\n" + string(ev.Payload) + "\r\n")
	return smtp.SendMail(addr, auth, n.SMTP.From, []string{n.SMTP.From}, msg)
}
