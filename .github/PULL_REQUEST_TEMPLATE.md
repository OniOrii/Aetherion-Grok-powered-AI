## Summary
<!-- One paragraph describing the change. Link any related issue. -->

## Motivation / Context
<!-- Why is this needed? How does it align with Maximum Nativeness? -->

## Changes
- [ ] ...

## Checklist (Required)
- [ ] Changes respect core invariants:
  - [ ] Web dashboard (`web/`) still never touches or exposes secrets.
  - [ ] Media sentinel / direct delivery pattern (`media/delivery.py`) is untouched (if media touched).
  - [ ] Activation policy, per-user rate limiting (6/60s), and guild whitelist (`ALLOWED_GUILD_IDS`) behavior unchanged.
  - [ ] Voice session / DAVE path still works (`/join`, wake word, playback lock).
  - [ ] OAuth handling and `oauth/` storage unchanged.
  - [ ] Decoupled bot vs web processes preserved.
- [ ] I have added or updated tests where appropriate.
- [ ] All tests pass: `pytest -q` and `python scripts/check.py --skip-docker`.
- [ ] I ran `aetherion --check` or `groksito --check` locally.
- [ ] Documentation updated if user-facing or process changed.
- [ ] No unrelated files or scope creep.
- [ ] I understand this project is MIT licensed and contributions fall under it.

## Testing Performed
<!-- Describe manual + automated verification. -->

## Screenshots / Examples (if UI or behavior change)

## Additional Notes
