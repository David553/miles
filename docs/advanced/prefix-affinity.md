# Token-prefix affinity in the custom Miles router

Opt in with `--use-miles-router --miles-router-prefix-affinity`. This chooses a healthy worker with the longest recently observed token prefix, subject to a four-active-request load-skew limit. Without the flag, existing minimum-active-request routing remains in use. This is separate from SGLang gateway policies.

The router hashes complete 32-token blocks from `/generate` input_ids, including model and adapter identity. It records hints after successful responses, retains at most65,536 worker/block entries for120seconds, and drops hints on deregistration, quarantine, and routed flush/disk-update/version-update calls. Engine cache eviction and direct trainer-to-engine updates may leave hints temporarily stale; hints influence placement only, never authorize KV reuse. Multimodal, batched token lists and text-only payloads fall back to existing routing.

The direct control/update path remains unchanged. Clients should not route one weight-update call through this load balancer and assume every engine was updated. When using TP2DP2, address affinity alone does not guarantee DP-rank affinity. This change does not add streaming support to the existing buffering custom proxy.

Five CPU/HTTP tests cover repeated and growing prefixes, load spill, expiration, bounded memory, model/adapter separation, deregistration, failed HTTP counter cleanup, and payload preservation. Run in a minimal environment with `python -m pytest --confcutdir=tests/router tests/router`; the parent repository test conftest otherwise imports trainer/Ray dependencies.

Hardware cache-hit/throughput qualification remains pending. Independent upstream sglang-router0.3.2 tests are recorded separately; this fallback does not claim that upstream gateway lacks token routing.
