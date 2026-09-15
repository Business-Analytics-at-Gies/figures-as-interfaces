"""Run the paper's linked-figure interaction using actual local taxi trips."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import sys

from .model import Artifact
from .pipeline import Pipeline
from .planner import RuleBasedPlanner

TREND = 'Plot hourly trip counts for Manhattan in January 2024'
RANK = 'Rank pickup zones by trip count within the selected hours'


def mark_ids(figure, hours):
    return [r['mark_id'] for r in figure.V['spec']['data']['values'] if r['pickup_hour'] in hours]


def demo(output: Path):
    # The teaching demo is explicitly offline, even if a provider hook is configured.
    from .dataset import bundled_dir

    pipeline = Pipeline(planner=RuleBasedPlanner())
    hourly = pipeline.execute(pipeline.planner.plan(TREND), TREND)
    evening = pipeline.follow_up(hourly.M['figure_id'],mark_ids(hourly,[17,18,19,20]),RANK)
    morning = pipeline.brush(hourly.M['figure_id'],mark_ids(hourly,[7,8,9,10]))[0]
    output.mkdir(parents=True,exist_ok=True)
    parquet = bundled_dir() / 'yellow_tripdata_sample.parquet'
    pipeline.artifact.dataset_path = str(Path(os.path.relpath(parquet, output)))
    pipeline.artifact.save(output/'artifact.json')
    lines = [f"TLC January 2024: {len(pipeline.artifact.dataset):,} sampled trips, not full-month totals.",
             f"Manhattan: {len(hourly.D['rows']):,} trips across {len(hourly.D['results'])} hourly marks.",
             f'Instruction: {TREND}', f'Follow-up: {RANK}']
    for name,figure in [('hourly',hourly),('evening',evening),('morning',morning)]:
        (output/f'{name}.png').write_bytes(base64.b64decode(figure.V['png']))
        (output/f'{name}.vl.json').write_text(json.dumps(figure.V['spec'],indent=2)+'\n')
        (output/f'{name}.sql').write_text(figure.C['sql'])
        if name != 'hourly':
            lines.append(f"{name.title()} ({'17-20' if name == 'evening' else '07-10'} inclusive), {len(figure.D['rows']):,} trips; top 5 pickup zones:")
            lines.extend(f"  {row['pickup_zone']}: {row['trips']:,}" for row in figure.D['results'][:5])
    restored=Pipeline(artifact=Artifact.load(output/'artifact.json'))
    for key in restored.artifact.figures:
        restored.replay(key)
    lines.append(f'Replayed {len(restored.artifact.figures)} figure versions with identical data, mappings and specs.')
    lines.append(f'Files: {output.resolve()}')
    transcript='\n'.join(lines)+'\n'
    (output/'transcript.txt').write_text(transcript)
    print(transcript,end='')


def main(argv=None):
    parser=argparse.ArgumentParser(description='Offline DuckDB figures with reproducible provenance')
    commands=parser.add_subparsers(dest='command',required=True)
    demo_parser=commands.add_parser('demo',help='Run hourly -> evening zones -> morning zones')
    demo_parser.add_argument('--output',type=Path,default=Path('demo-output'))
    replay_parser=commands.add_parser('replay',help='Re-execute every saved figure from its JSON snapshot')
    replay_parser.add_argument('artifact',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.command=='demo':
            demo(args.output)
        else:
            pipeline=Pipeline(artifact=Artifact.load(args.artifact))
            for key in pipeline.artifact.figures:
                pipeline.replay(key)
            print(f'Replayed {len(pipeline.artifact.figures)} figure versions with identical data, mappings and specs.')
    except (OSError,ValueError) as error:
        print(f'Error: {error}',file=sys.stderr)
        return 2
    return 0
