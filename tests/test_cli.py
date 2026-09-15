import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[1]


def run(*args):
    env=dict(os.environ, PYTHONPATH=str(ROOT/'tests/network_guard'))
    return subprocess.run([sys.executable,'-m','figureflow',*map(str,args)],cwd=ROOT,env=env,text=True,capture_output=True)


@pytest.fixture(scope='module')
def demo(tmp_path_factory):
    output=tmp_path_factory.mktemp('demo')
    return output,run('demo','--output',output)


def test_cli_reports_evening_and_morning(demo):
    _,result=demo
    assert result.returncode==0,result.stderr
    assert '50,000' in result.stdout
    assert 'Evening' in result.stdout and 'Morning' in result.stdout
    assert 'Replayed 3 figure versions' in result.stdout


def test_demo_exports_portable_artifact_and_figures(demo):
    output,result=demo
    assert result.returncode==0,result.stderr
    document=json.loads((output/'artifact.json').read_text())
    Draft202012Validator(json.loads((ROOT/'docs/artifact.schema.json').read_text())).validate(document)
    assert len(document['versions'])==3
    assert len(document['figures'])==3
    for name in ['hourly','evening','morning']:
        assert (output/f'{name}.png').read_bytes().startswith(b'\x89PNG')
        assert json.loads((output/f'{name}.vl.json').read_text())['data']['values']
        assert 'GROUP BY' in (output/f'{name}.sql').read_text()
    figures=list(document['figures'].values())
    assert figures[1]['M']['figure_id']==figures[2]['M']['figure_id']
    assert figures[1]['D']['results']!=figures[2]['D']['results']


def test_fresh_process_replay(demo):
    output,result=demo
    assert result.returncode==0,result.stderr
    replay=run('replay',output/'artifact.json')
    assert replay.returncode==0,replay.stderr
    assert 'Replayed 3 figure versions' in replay.stdout


def test_cli_missing_artifact_is_actionable():
    result=run('replay','.scratch/missing-artifact.json')
    assert result.returncode==2
    assert 'Error:' in result.stderr and 'Traceback' not in result.stderr


def test_committed_example_is_schema_valid_and_replayable():
    path=ROOT/'examples/taxi-artifact.json'
    assert path.exists()
    data=json.loads(path.read_text())
    Draft202012Validator(json.loads((ROOT/'docs/artifact.schema.json').read_text())).validate(data)
    result=run('replay',path)
    assert result.returncode==0,result.stderr


def test_notebook_analysis_cells_run_offline(tmp_path, monkeypatch):
    notebook=ROOT/'examples/taxi_figures.ipynb'
    assert notebook.exists()
    document=json.loads(notebook.read_text())
    monkeypatch.setenv('FIGUREFLOW_DEMO_OUTPUT',str(tmp_path/'notebook-output'))
    context={'REPO':ROOT}
    for cell in document['cells']:
        if cell['cell_type']=='code' and 'install' not in cell.get('metadata',{}).get('tags',[]):
            exec(compile(''.join(cell['source']),str(notebook),'exec'),context)
    assert len(context['selected_rows'])>0
    assert set(r['pickup_hour'] for r in context['selected_rows'])=={17,18,19,20}
