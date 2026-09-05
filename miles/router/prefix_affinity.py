"""Bounded token-prefix hints for the custom Miles HTTP router.

Hints predict reuse; the engine's radix cache remains the authority on KV.
"""
import hashlib
import json
import struct
import time
from collections import OrderedDict


def request_prefixes(body: bytes, *, block_size: int = 32) -> tuple[bytes, ...]:
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return ()
    if not isinstance(data, dict) or any(data.get(k) for k in ("image_data", "video_data", "audio_data", "input_embeds")):
        return ()
    tokens = data.get("input_ids")
    if not isinstance(tokens, list) or not all(type(t) is int and 0 <= t < 2**32 for t in tokens):
        return ()
    # Do not predict reuse of the last token, which computes prompt logits.
    identity = json.dumps([data.get("model"), data.get("lora_path")], sort_keys=True).encode()
    digest = hashlib.sha256(identity).digest()
    prefixes = []
    for start in range(0, len(tokens) - block_size, block_size):
        block = struct.pack(f"<{block_size}I", *tokens[start:start + block_size])
        digest = hashlib.sha256(digest + block).digest()
        prefixes.append(digest)
    return tuple(prefixes)


class PrefixAffinity:
    def __init__(self, *, max_entries=65536, ttl=120.0, max_load_skew=4, clock=time.monotonic):
        if max_entries < 1 or ttl <= 0 or max_load_skew < 0:
            raise ValueError("Invalid prefix-affinity bounds")
        self.max_entries, self.ttl, self.max_load_skew = max_entries, ttl, max_load_skew
        self.clock = clock
        self.entries = OrderedDict()
        self.epoch = 0

    def choose(self, loads, prefixes):
        if not loads:
            raise RuntimeError("No healthy workers available in the pool")
        now = self.clock()
        while self.entries and next(iter(self.entries.values())) <= now:
            self.entries.popitem(last=False)
        minimum = min(loads.values())
        eligible = [w for w in loads if loads[w] <= minimum + self.max_load_skew]
        scores = {w: 0 for w in eligible}
        for depth, prefix in enumerate(prefixes, 1):
            for worker in eligible:
                if self.entries.get((prefix, worker), 0) > now:
                    scores[worker] = depth
        return min(eligible, key=lambda w: (-scores[w], loads[w]))

    def remember(self, worker, prefixes, *, epoch):
        if epoch != self.epoch:
            return
        expires = self.clock() + self.ttl
        for prefix in prefixes:
            key = (prefix, worker)
            self.entries[key] = expires
            self.entries.move_to_end(key)
        while len(self.entries) > self.max_entries:
            self.entries.popitem(last=False)

    def clear(self):
        self.entries.clear()
        self.epoch += 1

    def remove_worker(self, worker):
        # Also suppress completions that were in flight before deregistration.
        self.epoch += 1
        self.entries = OrderedDict((k, v) for k, v in self.entries.items() if k[1] != worker)
