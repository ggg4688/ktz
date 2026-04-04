package ws

import (
	"testing"
	"time"
)

func TestBroadcastDoesNotBlockWhenQueueIsFull(t *testing.T) {
	hub := NewHub()

	for i := 0; i < cap(hub.broadcast); i++ {
		hub.broadcast <- []byte(`{"mock":"data"}`)
	}

	done := make(chan struct{})
	go func() {
		hub.Broadcast([]byte(`{"mock":"overflow"}`))
		close(done)
	}()

	select {
	case <-done:
	case <-time.After(200 * time.Millisecond):
		t.Fatal("broadcast blocked on full queue")
	}
}
