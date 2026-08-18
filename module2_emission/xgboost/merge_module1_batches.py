"""One-off utility: merge the existing verified 30-video Module 1 batch output
(outputs/module1_final_batch/) with a freshly-processed batch of additional videos
(outputs/module1_104_batch_NEW/) into one combined outputs/module1_104_batch/ directory,
so downstream scripts (enrich_module1_distances.py, build_copert_scenario_dataset.py,
copert_emission_engine.py, windows.py) can treat all 104 videos as one manifest without
reprocessing the 30 already-verified videos through YOLO+ByteTrack again.
"""

import argparse
import shutil
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--existing-dir", default="outputs/module1_final_batch")
    parser.add_argument("--new-dir", default="outputs/module1_104_batch_NEW")
    parser.add_argument("--output-dir", default="outputs/module1_104_batch")
    args = parser.parse_args()

    existing_dir = Path(args.existing_dir)
    new_dir = Path(args.new_dir)
    output_dir = Path(args.output_dir)
    output_runs = output_dir / "individual_runs"
    output_runs.mkdir(parents=True, exist_ok=True)

    for source_dir in (existing_dir / "individual_runs", new_dir / "individual_runs"):
        for video_dir in sorted(source_dir.iterdir()):
            if not video_dir.is_dir():
                continue
            destination = output_runs / video_dir.name
            if destination.exists():
                raise FileExistsError(f"video_id collision: {video_dir.name} exists in both batches.")
            shutil.copytree(video_dir, destination)

    existing_manifest = pd.read_csv(existing_dir / "module1_manifest.csv")
    new_manifest = pd.read_csv(new_dir / "module1_manifest.csv")
    combined_manifest = pd.concat([existing_manifest, new_manifest], ignore_index=True)
    combined_manifest = combined_manifest.sort_values(
        "video_id", key=lambda s: s.str.extract(r"(\d+)")[0].astype(int)
    ).reset_index(drop=True)
    combined_manifest.to_csv(output_dir / "module1_manifest.csv", index=False)

    included = combined_manifest.loc[combined_manifest["status"] == "INCLUDED"]
    print(f"Combined manifest: {len(combined_manifest)} videos "
          f"({len(included)} INCLUDED) -> {output_dir / 'module1_manifest.csv'}")
    print(f"Combined individual_runs: {len(list(output_runs.iterdir()))} video directories -> {output_runs}")


if __name__ == "__main__":
    main()
