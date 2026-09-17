# vulture allowlist: `vulture --make-whitelist src tests --min-confidence 60 > .vulture_allowlist.py`
# Each entry below was hand-reviewed and is a genuine false positive, not
# real dead code. Regenerate and re-review by hand (never commit unreviewed
# output) if the pre-push `vulture` hook starts failing.
created_at  # Fact.created_at (src/tvagent/core/models.py:34) — set via the
# Fact dataclass and round-tripped through dataclasses.asdict()/Fact(**...)
# in src/tvagent/adapters/memory_json.py (add_fact/get_facts), which vulture's
# static analysis can't see as a "read".
