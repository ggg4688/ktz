package main

import (
	"log"
	"net/http"
	"time"

	ws "realtime_websocket/internal/ws"
)

func newServer(addr string, handler http.Handler) *http.Server {
	return &http.Server{
		Addr:              addr,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
	}
}

func main() {
	hub := ws.NewHub()
	go hub.Run()

	mux := http.NewServeMux()
	mux.HandleFunc("/ws", ws.NewHandler(hub))

	server := newServer(":8080", mux)

	log.Println("websocket service listening on :8080")
	log.Fatal(server.ListenAndServe())
}
