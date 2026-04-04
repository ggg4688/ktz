package main

import (
	"net/http"
	"testing"
	"time"
)

func TestNewServerTimeouts(t *testing.T) {
	srv := newServer(":8080", http.NewServeMux())

	if srv.ReadHeaderTimeout != 5*time.Second {
		t.Fatalf("unexpected ReadHeaderTimeout: got=%s", srv.ReadHeaderTimeout)
	}
	if srv.ReadTimeout != 15*time.Second {
		t.Fatalf("unexpected ReadTimeout: got=%s", srv.ReadTimeout)
	}
	if srv.WriteTimeout != 15*time.Second {
		t.Fatalf("unexpected WriteTimeout: got=%s", srv.WriteTimeout)
	}
	if srv.IdleTimeout != 60*time.Second {
		t.Fatalf("unexpected IdleTimeout: got=%s", srv.IdleTimeout)
	}
}
