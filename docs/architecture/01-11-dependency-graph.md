# 01-11: Session Dependency Graph

## Critical Path (Sequential)

`01 (Arch) -> 02 (HIL Spec) -> 06 (HIL Impl) -> 07 (Core Impl) -> 11 (API) -> 12 (Vault) -> 15 (Models) -> 17 (Integration) -> 18 (Deploy)`

## Parallelizable Tracks

- **Spec Track (Phase A):** Sessions 02, 03, 04, 05 can run concurrently after 01
- **Code Track (Phase B):** 06 -> (07 || 08) -> 09 -> 10
- **Integration Track (Phase C/D):** 11, 12, 13, 14, 15, 16 can overlap once dependencies met
- **Validation (Phase E):** 17 -> 18 (strictly sequential)

## Effort Estimates

| Session | Spec Pages | Code LOC | Est. Sessions |
|---------|------------|----------|---------------|
| 01 | 12 (modular) | ~500 (scaffold) | 1 |
| 02 | 8 | ~800 | 1 |
| 03 | 9 | ~600 | 1 |
| 04 | 8 | ~700 | 1 |
| 05 | 10 | ~1200 | 1.5 |
| 06-18 | - | ~37,000 | ~17 |

**Total:** ~22-28 focused sessions. Critical path: 9 sessions.
