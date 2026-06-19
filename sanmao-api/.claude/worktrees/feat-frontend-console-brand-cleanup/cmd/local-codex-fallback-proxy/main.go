package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"
)

const (
	defaultListenAddr  = "127.0.0.1:13100"
	defaultTunnelBase  = "http://127.0.0.1:13000"
	defaultPublicBase  = "https://www.sanmao.fun"
	defaultHealthPath  = "/api/status"
	defaultProbeTTL    = 2 * time.Second
	defaultHTTPTimeout = 90 * time.Second
)

type upstreamTarget struct {
	name string
	base *url.URL
}

type upstreamStatus struct {
	target     upstreamTarget
	checkedAt  time.Time
	reachable  bool
	statusCode int
	err        string
}

type fallbackProxy struct {
	logger *log.Logger

	tunnel upstreamTarget
	public upstreamTarget

	healthPath string
	probeTTL   time.Duration

	probeClient  *http.Client
	proxyClient  *http.Client
	statusMu     sync.RWMutex
	cachedStatus upstreamStatus
}

func main() {
	logger := log.New(os.Stdout, "[codex-fallback] ", log.LstdFlags)

	listenAddr := envOrDefault("SANMAO_CODEX_FALLBACK_LISTEN", defaultListenAddr)
	tunnelBase := mustParseURL(envOrDefault("SANMAO_CODEX_TUNNEL_BASE", defaultTunnelBase))
	publicBase := mustParseURL(envOrDefault("SANMAO_CODEX_PUBLIC_BASE", defaultPublicBase))
	healthPath := envOrDefault("SANMAO_CODEX_HEALTH_PATH", defaultHealthPath)

	proxy := &fallbackProxy{
		logger: logger,
		tunnel: upstreamTarget{name: "tunnel", base: tunnelBase},
		public: upstreamTarget{name: "public", base: publicBase},
		healthPath: healthPath,
		probeTTL:   defaultProbeTTL,
		probeClient: &http.Client{
			Timeout: 3 * time.Second,
			Transport: &http.Transport{
				Proxy: nil,
			},
		},
		proxyClient: &http.Client{
			Timeout: defaultHTTPTimeout,
			Transport: &http.Transport{
				Proxy: nil,
			},
		},
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/api/status", proxy.handleStatus)
	mux.HandleFunc("/v1/", proxy.handleProxy)

	server := &http.Server{
		Addr:              listenAddr,
		Handler:           loggingMiddleware(logger, mux),
		ReadHeaderTimeout: 10 * time.Second,
	}

	logger.Printf("listening on http://%s", listenAddr)
	logger.Printf("tunnel upstream: %s", tunnelBase.String())
	logger.Printf("public upstream: %s", publicBase.String())
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		logger.Fatalf("server failed: %v", err)
	}
}

func (p *fallbackProxy) handleStatus(w http.ResponseWriter, r *http.Request) {
	status := p.currentStatus(r.Context(), true)
	payload := fmt.Sprintf(`{"ok":true,"selected_upstream":"%s","tunnel_reachable":%t,"checked_at":"%s","last_error":%q}`,
		status.target.name,
		status.reachable,
		status.checkedAt.Format(time.RFC3339),
		status.err,
	)
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-cache")
	_, _ = w.Write([]byte(payload))
}

func (p *fallbackProxy) handleProxy(w http.ResponseWriter, r *http.Request) {
	status := p.currentStatus(r.Context(), false)
	target := status.target

	upstreamURL := *target.base
	upstreamURL.Path = joinURLPath(upstreamURL.Path, r.URL.Path)
	upstreamURL.RawQuery = r.URL.RawQuery

	bodyReader, err := cloneBody(r)
	if err != nil {
		http.Error(w, fmt.Sprintf("read request body failed: %v", err), http.StatusBadRequest)
		return
	}

	upstreamReq, err := http.NewRequestWithContext(r.Context(), r.Method, upstreamURL.String(), bodyReader)
	if err != nil {
		http.Error(w, fmt.Sprintf("build upstream request failed: %v", err), http.StatusInternalServerError)
		return
	}

	copyHeaders(upstreamReq.Header, r.Header)
	upstreamReq.Host = upstreamURL.Host

	resp, err := p.proxyClient.Do(upstreamReq)
	if err != nil {
		http.Error(w, fmt.Sprintf("upstream request failed via %s: %v", target.name, err), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	copyResponseHeaders(w.Header(), resp.Header)
	w.Header().Set("X-Sanmao-Upstream", target.name)
	w.Header().Set("X-Sanmao-Upstream-Base", target.base.String())
	w.WriteHeader(resp.StatusCode)

	if flusher, ok := w.(http.Flusher); ok {
		if _, err := io.Copy(flushWriter{Writer: w, flusher: flusher}, resp.Body); err != nil {
			p.logger.Printf("stream copy ended via %s: %v", target.name, err)
		}
		return
	}

	if _, err := io.Copy(w, resp.Body); err != nil {
		p.logger.Printf("copy ended via %s: %v", target.name, err)
	}
}

func (p *fallbackProxy) currentStatus(ctx context.Context, force bool) upstreamStatus {
	p.statusMu.RLock()
	cached := p.cachedStatus
	p.statusMu.RUnlock()

	if !force && !cached.checkedAt.IsZero() && time.Since(cached.checkedAt) < p.probeTTL {
		return cached
	}

	status := p.probeTunnel(ctx)
	p.statusMu.Lock()
	p.cachedStatus = status
	p.statusMu.Unlock()
	return status
}

func (p *fallbackProxy) probeTunnel(ctx context.Context) upstreamStatus {
	healthURL := *p.tunnel.base
	healthURL.Path = joinURLPath(healthURL.Path, p.healthPath)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, healthURL.String(), nil)
	if err != nil {
		return upstreamStatus{
			target:    p.public,
			checkedAt: time.Now(),
			err:       err.Error(),
		}
	}

	resp, err := p.probeClient.Do(req)
	if err != nil {
		return upstreamStatus{
			target:    p.public,
			checkedAt: time.Now(),
			err:       err.Error(),
		}
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		return upstreamStatus{
			target:     p.tunnel,
			checkedAt:  time.Now(),
			reachable:  true,
			statusCode: resp.StatusCode,
		}
	}

	return upstreamStatus{
		target:     p.public,
		checkedAt:  time.Now(),
		reachable:  false,
		statusCode: resp.StatusCode,
		err:        fmt.Sprintf("health returned %d", resp.StatusCode),
	}
}

func cloneBody(r *http.Request) (io.Reader, error) {
	if r.Body == nil {
		return nil, nil
	}
	defer r.Body.Close()
	body, err := io.ReadAll(r.Body)
	if err != nil {
		return nil, err
	}
	r.Body = io.NopCloser(strings.NewReader(string(body)))
	return strings.NewReader(string(body)), nil
}

func copyHeaders(dst, src http.Header) {
	for key, values := range src {
		for _, value := range values {
			dst.Add(key, value)
		}
	}
}

func copyResponseHeaders(dst, src http.Header) {
	for key, values := range src {
		switch strings.ToLower(key) {
		case "content-length":
			continue
		default:
			for _, value := range values {
				dst.Add(key, value)
			}
		}
	}
}

func joinURLPath(basePath, requestPath string) string {
	base := strings.TrimRight(basePath, "/")
	path := "/" + strings.TrimLeft(requestPath, "/")
	if base == "" {
		return path
	}
	return base + path
}

func envOrDefault(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}

func mustParseURL(raw string) *url.URL {
	parsed, err := url.Parse(raw)
	if err != nil {
		panic(err)
	}
	return parsed
}

type flushWriter struct {
	io.Writer
	flusher http.Flusher
}

func (w flushWriter) Write(p []byte) (int, error) {
	n, err := w.Writer.Write(p)
	if n > 0 {
		w.flusher.Flush()
	}
	return n, err
}

func loggingMiddleware(logger *log.Logger, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		next.ServeHTTP(w, r)
		logger.Printf("%s %s (%s)", r.Method, r.URL.Path, time.Since(started).Round(time.Millisecond))
	})
}
