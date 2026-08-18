# Cleanup log (2026-08-17, follow-up to Module 0)

## Git removed
`.git/` renamed to `_git_history_backup/` at the repo root. This is no longer a git
repository (`git status` correctly reports "not a git repository"). All 3 commits and the
GitHub remote link (github.com/Vishblr-7/Hybrid_Traffic_MJ.git) are preserved inside
`_git_history_backup/` -- to restore version control, rename it back to `.git`. It is
~1.6GB (mostly from an early mistaken commit that briefly included generated video data,
since reset before the final commit, but the object is still sitting in that backup).
Safe to delete once you're comfortable you won't need the history.

## Superseded/duplicate output folders relocated
Everything below was moved, not deleted (this bridge can't delete files) -- review and
empty these two folders yourself in Finder when ready:

**`outputs/_TO_DELETE_review_then_trash/`** (~1.0 GB):
- `copert_video02/`, `copert_video02_v2/` -- video02-only distance-methodology experiments,
  superseded by the canonical `outputs/copert_emissions/`
- `module1_smoke/` -- single-video smoke test, superseded by `outputs/module1_indra_batch/`
- `module2_copert_scenario/` -- pre-distance-enrichment version, superseded by
  `outputs/module2_copert_scenario_distance/`
- `output_videos/`, `videos/` -- annotated mp4s from calibration-tuning experiments
  (adaptive/, config_default_video2/, enhanced/, final_sample_video_1/, homography/,
  homography_robust/, latest_sample_video_1/, latest_uploads/, quality_gate/, plus loose
  files) predating the finalized INDRA batch calibration
- `csv/` -- the CSV counterparts of the same calibration experiments
- `images/` -- was already empty

**`_TO_DELETE_review_then_trash/`** (repo root, ~180 KB):
- `src/` -- emptied by the Module 0 restructure (its files moved into `module1_traffic/`
  and `archive/`); this was the now-empty shell
- `__pycache__/` -- stale bytecode cache
- `module 2/`, `module 3_optimision /` -- emptied by the Module 0 restructure; these were
  the original mistyped/space-suffixed folder names

## What's left in outputs/ (the canonical, current set)
`copert_emissions/` (COPERT emission results), `module1_indra_batch/` (the 30-video
Module 1 run, including its annotated videos -- current, not superseded),
`module1_distance_enriched/`, `module2_copert_scenario_distance/`.

## Not touched
`venv/` (1.3 GB, gitignored, your local environment), `datasets/` (1.9 GB, gitignored,
the INDRA_dataset), `INDRA_data_for_emissions/`, `videos/` (repo root, the 6 sample input
videos), `notebooks/`, `models/best.pt`.
