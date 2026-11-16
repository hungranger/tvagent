# profile.toml schema

One per language profile (`profiles/<lang>/profile.toml`); native templates live in `profiles/<lang>/templates/` and are copied to the same relative path (a trailing `.tmpl` is stripped, so unparsable-until-rendered TOML survives pre-commit) with `{{<manifest_key>}}` tokens replaced (`gate_setup.render`).

```toml
[gates.<name>]
tools = ["tool-a", "tool-b"]            # ordered
impl_lang = "rust"                      # rust | go | node | python
threshold_key = "coverage_floor"        # a KEY_DIRECTIONS key, or omit/absent for none
threshold_mechanism = "flag"            # flag (CLI flag in CI/hook) | config (native file) | none
blocking = true

[drift]                                  # native value must equal manifest value
"<native_path>#<dotted.key>" = "<manifest_key>"   # .toml or .json native files

[coverage]  metric = "line"
[measure]   <gate> = "<shell recipe to measure the current value>"
[greenfield] <manifest_key> = <starting value>
```

Rules:
- `flag` / `config` gates require their `threshold_key` in the manifest at render time.
- A `config` (config-only) key present in `[thresholds]` MUST have a `[drift]` binding; `manifest.py check-drift --gates <profile_dir>` fails otherwise.
- Render output is deterministic and contains no residual `{{`.
