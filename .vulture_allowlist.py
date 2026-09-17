# vulture allowlist: `vulture --make-whitelist src tests > .vulture_allowlist.py`
# Currently empty — at --min-confidence 80, vulture found no framework/interface
# false positives (Protocol dispatch, dataclass fields, CLI `main`, pytest
# fixtures) to allowlist, and no real dead code either. Regenerate and
# re-review by hand (never commit unreviewed output) if the pre-push
# `vulture` hook starts failing.
