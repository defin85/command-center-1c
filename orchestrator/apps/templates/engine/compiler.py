"""
Template compiler with caching.

Compiles Jinja2 templates and caches compiled versions
to avoid recompilation on every render.

Performance Impact:
- First render: compile + cache (baseline)
- Subsequent renders: cache hit (~2x faster)
- Cache: In-memory dict (thread-safe)

Note:
    Uses in-memory cache instead of Django cache because
    Jinja2 Template objects are not pickle-serializable.
    For distributed caching (multi-process), consider
    using Jinja2 bytecode cache with Redis backend.
"""

from jinja2 import Template
from typing import Dict, Any
import hashlib
import json
import logging
import threading

logger = logging.getLogger(__name__)


class TemplateCompiler:
    """Compiles and caches Jinja2 templates (in-memory)."""

    # Class-level cache (shared across all instances)
    _cache: Dict[str, Template] = {}
    _cache_lock = threading.Lock()

    CACHE_PREFIX = "template_compiled_"
    MAX_CACHE_SIZE = 10000  # Prevent unbounded growth

    def __init__(self, env):
        """
        Initialize compiler with Jinja2 environment.

        Args:
            env: Jinja2 Environment instance (ImmutableSandboxedEnvironment)
        """
        self.env = env

    def get_compiled_template(
        self,
        template_id: str,
        template_source: Any
    ) -> Template:
        """
        Get compiled template (from cache or compile).

        Args:
            template_id: Template ID (for cache key)
            template_source: Template data (dict, list, or str)

        Returns:
            Compiled Jinja2 Template

        Note:
            Cache key = PREFIX + template_id + hash(source)
            This ensures different versions of same template_id
            get separate cache entries.
        """
        # Convert source to string for hashing
        if isinstance(template_source, (dict, list)):
            source_str = json.dumps(template_source, sort_keys=True, ensure_ascii=False)
        else:
            source_str = str(template_source)

        # Generate cache key (template_id + hash of source)
        source_hash = hashlib.sha256(source_str.encode('utf-8')).hexdigest()[:16]
        cache_key = f"{self.CACHE_PREFIX}{template_id}_{source_hash}"

        # Try to get from cache (thread-safe)
        with self._cache_lock:
            compiled = self._cache.get(cache_key)

        if compiled is None:
            # Cache miss - compile template
            logger.debug(
                f"Template cache miss - compiling",
                extra={'template_id': template_id, 'cache_key': cache_key}
            )

            compiled = self.env.from_string(source_str)

            # Cache compiled template (thread-safe)
            with self._cache_lock:
                # Check cache size limit
                if len(self._cache) >= self.MAX_CACHE_SIZE:
                    # Simple eviction: clear oldest half
                    logger.warning(
                        f"Template cache full ({len(self._cache)} entries) - evicting oldest entries"
                    )
                    keys_to_remove = list(self._cache.keys())[:self.MAX_CACHE_SIZE // 2]
                    for key in keys_to_remove:
                        del self._cache[key]

                self._cache[cache_key] = compiled
        else:
            # Cache hit
            logger.debug(
                f"Template cache hit",
                extra={'template_id': template_id, 'cache_key': cache_key}
            )

        return compiled

    def invalidate_cache(self, template_id: str):
        """
        Invalidate all cached versions of a template.

        Args:
            template_id: Template ID to invalidate

        Note:
            Removes all cache entries matching the template_id prefix.
        """
        with self._cache_lock:
            # Find all keys matching this template_id
            keys_to_remove = [
                key for key in self._cache.keys()
                if key.startswith(f"{self.CACHE_PREFIX}{template_id}_")
            ]

            # Remove them
            for key in keys_to_remove:
                del self._cache[key]

            logger.info(
                f"Cache invalidation completed for template",
                extra={'template_id': template_id, 'entries_removed': len(keys_to_remove)}
            )

    def clear_all_cache(self):
        """
        Clear all cached templates.

        Useful for testing or manual cache cleanup.
        """
        with self._cache_lock:
            cache_size = len(self._cache)
            self._cache.clear()

        logger.info(f"All template cache cleared ({cache_size} entries removed)")

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dict with cache size and max size
        """
        with self._cache_lock:
            return {
                'size': len(self._cache),
                'max_size': self.MAX_CACHE_SIZE,
                'usage_percent': int(len(self._cache) / self.MAX_CACHE_SIZE * 100)
            }
