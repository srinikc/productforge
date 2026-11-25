package cache

import (
	"context"
	"sync"
	"time"
)

type entry struct {
	val []byte
	exp time.Time
}

// Store is a bounded in-memory CacheStore for local/dev and tests.
type Store struct {
	mu   sync.Mutex
	data map[string]entry
	now  func() time.Time
}

func New() *Store { return &Store{data: map[string]entry{}, now: time.Now} }

func (s *Store) Get(_ context.Context, key string) ([]byte, bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	e, ok := s.data[key]
	if !ok {
		return nil, false, nil
	}
	if !e.exp.IsZero() && !s.now().Before(e.exp) {
		delete(s.data, key)
		return nil, false, nil
	}
	return append([]byte(nil), e.val...), true, nil
}

func (s *Store) Set(_ context.Context, key string, val []byte, ttl time.Duration) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.data[key]; !exists && len(s.data) >= 10000 {
		now := s.now()
		for k, e := range s.data {
			if !e.exp.IsZero() && !now.Before(e.exp) {
				delete(s.data, k)
			}
		}
		for k := range s.data {
			delete(s.data, k)
			break
		}
	}
	var exp time.Time
	if ttl > 0 {
		exp = s.now().Add(ttl)
	}
	s.data[key] = entry{val: append([]byte(nil), val...), exp: exp}
	return nil
}

func (s *Store) Delete(_ context.Context, key string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.data, key)
	return nil
}
