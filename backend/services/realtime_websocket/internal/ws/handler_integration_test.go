package ws

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/websocket"
)

func dialWS(serverURL, origin string) (*websocket.Conn, *http.Response, error) {
	wsURL := "ws" + strings.TrimPrefix(serverURL, "http") + "/ws"
	header := http.Header{}
	header.Set("Origin", origin)

	conn, resp, err := websocket.DefaultDialer.Dial(wsURL, header)
	return conn, resp, err
}

func dialWSSuccess(t *testing.T, serverURL, origin string) *websocket.Conn {
	t.Helper()

	conn, _, err := dialWS(serverURL, origin)
	if err != nil {
		t.Fatalf("dial websocket failed: %v", err)
	}
	return conn
}

func startTestServer(t *testing.T) (*Hub, *httptest.Server) {
	t.Helper()

	hub := NewHub()
	go hub.Run()

	mux := http.NewServeMux()
	mux.HandleFunc("/ws", NewHandler(hub))
	server := httptest.NewServer(mux)

	return hub, server
}

func TestBroadcastValidJSONWithMockData(t *testing.T) {
	_, server := startTestServer(t)
	defer server.Close()

	sender := dialWSSuccess(t, server.URL, server.URL)
	defer sender.Close()

	receiver := dialWSSuccess(t, server.URL, server.URL)
	defer receiver.Close()

	mockPayload := []byte(`{"sensor":"temp","value":24.5}`)
	if err := sender.WriteMessage(websocket.TextMessage, mockPayload); err != nil {
		t.Fatalf("sender write failed: %v", err)
	}

	_ = receiver.SetReadDeadline(time.Now().Add(2 * time.Second))
	_, got, err := receiver.ReadMessage()
	if err != nil {
		t.Fatalf("receiver read failed: %v", err)
	}
	if string(got) != string(mockPayload) {
		t.Fatalf("unexpected broadcast payload: got=%q want=%q", string(got), string(mockPayload))
	}
}

func TestDropInvalidJSONWithMockData(t *testing.T) {
	_, server := startTestServer(t)
	defer server.Close()

	sender := dialWSSuccess(t, server.URL, server.URL)
	defer sender.Close()

	receiver := dialWSSuccess(t, server.URL, server.URL)
	defer receiver.Close()

	if err := sender.WriteMessage(websocket.TextMessage, []byte("not-json")); err != nil {
		t.Fatalf("sender write failed: %v", err)
	}

	_ = receiver.SetReadDeadline(time.Now().Add(400 * time.Millisecond))
	_, _, err := receiver.ReadMessage()
	if err == nil {
		t.Fatal("expected no broadcast for invalid json, but got a message")
	}
}

func TestRejectsCrossOriginConnection(t *testing.T) {
	_, server := startTestServer(t)
	defer server.Close()

	conn, resp, err := dialWS(server.URL, "https://evil.example")
	if conn != nil {
		_ = conn.Close()
		t.Fatal("expected websocket handshake to fail for cross-origin request")
	}
	if err == nil {
		t.Fatal("expected websocket handshake error for cross-origin request")
	}
	if resp == nil {
		t.Fatal("expected http response on failed websocket handshake")
	}
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("unexpected status code: got=%d want=%d", resp.StatusCode, http.StatusForbidden)
	}
}

func TestRejectsMissingOrigin(t *testing.T) {
	_, server := startTestServer(t)
	defer server.Close()

	conn, resp, err := dialWS(server.URL, "")
	if conn != nil {
		_ = conn.Close()
		t.Fatal("expected websocket handshake to fail for empty origin")
	}
	if err == nil {
		t.Fatal("expected websocket handshake error for empty origin")
	}
	if resp == nil {
		t.Fatal("expected http response on failed websocket handshake")
	}
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("unexpected status code: got=%d want=%d", resp.StatusCode, http.StatusForbidden)
	}
}
