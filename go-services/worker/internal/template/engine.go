package template

import (
	"context"
	"fmt"
	"time"

	"github.com/flosch/pongo2/v6"
	lru "github.com/hashicorp/golang-lru/v2"
	"go.uber.org/zap"
)

// DefaultCacheSize is the default maximum number of templates to cache.
const DefaultCacheSize = 1000

// Engine provides template rendering functionality using pongo2.
// It supports caching of compiled templates and recursive rendering
// for nested data structures (common in operation payloads).
type Engine struct {
	logger       *zap.Logger
	cache        *lru.Cache[string, *pongo2.Template] // LRU cache with size limit
	preprocessor *Preprocessor
	validator    *Validator
}

// NewEngine creates a new template engine instance with default cache size.
func NewEngine(logger *zap.Logger) *Engine {
	return NewEngineWithCacheSize(logger, DefaultCacheSize)
}

// NewEngineWithCacheSize creates a new template engine with custom cache size.
func NewEngineWithCacheSize(logger *zap.Logger, cacheSize int) *Engine {
	cache, err := lru.New[string, *pongo2.Template](cacheSize)
	if err != nil {
		// This should never happen with valid cache size
		logger.Error("failed to create LRU cache, using default size",
			zap.Error(err),
			zap.Int("requested_size", cacheSize),
			zap.Int("fallback_size", DefaultCacheSize),
		)
		cache, _ = lru.New[string, *pongo2.Template](DefaultCacheSize)
	}
	return &Engine{
		logger:       logger,
		cache:        cache,
		preprocessor: NewPreprocessor(),
		validator:    NewValidator(),
	}
}

// Render renders a template string with the given context data.
// The template is cached for subsequent renders.
// Jinja2 syntax (loop.index, etc.) is automatically converted to pongo2 syntax.
func (e *Engine) Render(ctx context.Context, templateStr string, data map[string]interface{}) (string, error) {
	// Check for cancellation
	select {
	case <-ctx.Done():
		return "", ctx.Err()
	default:
	}

	// Validate security FIRST
	if err := e.validator.Validate(templateStr); err != nil {
		return "", err
	}

	// Validate context
	if err := e.validator.IsSafeContext(data); err != nil {
		return "", err
	}

	// Preprocess Jinja2 -> pongo2 syntax
	processedTemplate := e.preprocessor.Process(templateStr)

	// Get or compile template
	tpl, err := e.getOrCompile(processedTemplate)
	if err != nil {
		return "", NewCompilationError("failed to compile template", err)
	}

	// Build pongo2 context
	pongoCtx := pongo2.Context(data)

	// Execute template
	result, err := tpl.Execute(pongoCtx)
	if err != nil {
		return "", NewExecutionError("failed to execute template", err)
	}

	return result, nil
}

// RenderWithTimeout renders template with execution timeout protection.
// This prevents infinite loops or extremely slow templates from blocking the system.
func (e *Engine) RenderWithTimeout(ctx context.Context, templateStr string, data map[string]interface{}, timeout time.Duration) (string, error) {
	// Create timeout context
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	// Buffered channels to prevent goroutine leak on timeout
	resultCh := make(chan string, 1)
	errCh := make(chan error, 1)

	go func() {
		result, err := e.Render(ctx, templateStr, data)

		// Non-blocking writes to avoid goroutine leak when context times out
		if err != nil {
			select {
			case errCh <- err:
			default:
				// Channel full or nobody listening (timeout occurred)
			}
			return
		}
		select {
		case resultCh <- result:
		default:
			// Channel full or nobody listening (timeout occurred)
		}
	}()

	select {
	case result := <-resultCh:
		return result, nil
	case err := <-errCh:
		return "", err
	case <-ctx.Done():
		return "", NewExecutionError("template rendering timeout", ctx.Err())
	}
}

// RenderRecursive renders template data recursively.
// This is useful for nested structures like operation payloads where
// values at any level might contain template expressions.
func (e *Engine) RenderRecursive(ctx context.Context, data interface{}, templateContext map[string]interface{}) (interface{}, error) {
	// Check for cancellation
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	default:
	}

	switch v := data.(type) {
	case string:
		// Render string as template
		return e.Render(ctx, v, templateContext)

	case map[string]interface{}:
		// Recursively render map values
		result := make(map[string]interface{}, len(v))
		for key, val := range v {
			rendered, err := e.RenderRecursive(ctx, val, templateContext)
			if err != nil {
				return nil, fmt.Errorf("failed to render key %q: %w", key, err)
			}
			result[key] = rendered
		}
		return result, nil

	case []interface{}:
		// Recursively render array elements
		result := make([]interface{}, len(v))
		for i, item := range v {
			rendered, err := e.RenderRecursive(ctx, item, templateContext)
			if err != nil {
				return nil, fmt.Errorf("failed to render index %d: %w", i, err)
			}
			result[i] = rendered
		}
		return result, nil

	default:
		// Return non-template values as-is (int, float, bool, nil, etc.)
		return data, nil
	}
}

// getOrCompile returns a cached template or compiles and caches a new one.
func (e *Engine) getOrCompile(templateStr string) (*pongo2.Template, error) {
	// Check cache first
	if cached, ok := e.cache.Get(templateStr); ok {
		return cached, nil
	}

	// Compile template
	tpl, err := pongo2.FromString(templateStr)
	if err != nil {
		return nil, err
	}

	// Store in cache (LRU handles eviction automatically)
	e.cache.Add(templateStr, tpl)

	return tpl, nil
}

// RenderJSON renders a JSON-like structure (map) with templates in values.
// This is the primary method for rendering operation payloads.
func (e *Engine) RenderJSON(ctx context.Context, templateJSON map[string]interface{}, data map[string]interface{}) (map[string]interface{}, error) {
	rendered, err := e.RenderRecursive(ctx, templateJSON, data)
	if err != nil {
		return nil, err
	}

	result, ok := rendered.(map[string]interface{})
	if !ok {
		return nil, NewValidationError(fmt.Sprintf("expected map result, got %T", rendered), nil)
	}

	return result, nil
}

// Validate checks if a template string is syntactically valid.
func (e *Engine) Validate(templateStr string) error {
	_, err := pongo2.FromString(templateStr)
	if err != nil {
		return NewValidationError("invalid template syntax", err)
	}
	return nil
}

// ClearCache removes all cached templates.
// Useful for testing or when templates are updated.
func (e *Engine) ClearCache() {
	e.cache.Purge()
}

// CacheLen returns the number of cached templates.
func (e *Engine) CacheLen() int {
	return e.cache.Len()
}
