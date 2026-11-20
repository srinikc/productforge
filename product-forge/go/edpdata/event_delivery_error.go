package edpdata

import "time"

// PermanentError marks a delivery failure that must not be retried.
type PermanentError struct{ Err error }

func (e PermanentError) Error() string { return e.Err.Error() }
func (e PermanentError) Unwrap() error { return e.Err }
func (PermanentError) Permanent() bool { return true }

// RetryAfterError supplies a minimum retry delay.
type RetryAfterError interface {
	error
	RetryAfter() time.Duration
}

func IsPermanent(err error) bool {
	type permanent interface{ Permanent() bool }
	for err != nil {
		if p, ok := err.(permanent); ok && p.Permanent() {
			return true
		}
		type unwrapper interface{ Unwrap() error }
		u, ok := err.(unwrapper)
		if !ok {
			return false
		}
		err = u.Unwrap()
	}
	return false
}
