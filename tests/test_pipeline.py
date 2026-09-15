"""Behavior tests with independent, hand-counted trips and actual TLC sample."""
import copy
import json
import socket
import sys
import types

import duckdb
import pytest

from figureflow import Artifact, Mapping, Pipeline, RuleBasedPlanner, planner_from_env

TREND = "Plot hourly trip counts for Manhattan in January 2024"
RANK = "Rank pickup zones by trip count within the selected hours"


def trips():
    # Manhattan evening: A=3, B=1; morning: B=3, A=1. Queens excluded.
    return [dict(row_id=str(i), pickup_zone_id=zone, pickup_zone={1: "A", 2: "B", 3: "C"}[zone],
                 pickup_borough="Queens" if zone == 3 else "Manhattan", pickup_hour=hour,
                 pickup_date="2024-01-01" if i % 2 else "2024-01-02")
            for i, (zone, hour) in enumerate([(1,18), (1,18), (1,19), (2,19),
                                             (2,8), (2,8), (2,9), (1,9), (3,18), (3,8)])]


def pipe():
    return Pipeline(rows=trips())


def trend(p):
    return p.execute(RuleBasedPlanner().plan(TREND), TREND)


def marks(f, hours):
    return [r["mark_id"] for r in f.V["spec"]["data"]["values"] if r["pickup_hour"] in hours]


def evening(p):
    f = trend(p)
    return f, p.follow_up(f.M["figure_id"], marks(f, [18,19]), RANK)


def test_trend_counts_and_figure_tuple():
    p = pipe()
    f = trend(p)
    assert len(f.D["rows"]) == 8
    assert f.D["results"] == [{"pickup_hour": h, "trips": 2} for h in [8,9,18,19]]
    assert f.D["schema"]["row_id"] == "VARCHAR"
    assert f.D["result_schema"] == {"pickup_hour": "BIGINT", "trips": "BIGINT"}
    assert "GROUP BY" in f.C["sql"]
    assert "Manhattan" in f.V["summary"]
    import base64
    assert base64.b64decode(f.V["png"]).startswith(b"\x89PNG\r\n\x1a\n")
    assert f.M["operation"] == "generation"
    assert f.M["timestamp"].endswith("+00:00")
    assert f.M["artifact_version"] == p.artifact.head


def test_mark_mapping_retrieves_every_contributing_trip():
    f = trend(pipe())
    selection = Mapping.select(f, marks(f, [18,19]))
    assert {r["row_id"] for r in selection.rows} == {"0","1","2","3"}
    assert selection.hours == [18,19]
    assert selection.boroughs == ["Manhattan"]
    assert all(len(ids) == 2 for ids in f.R.mark_to_rows.values())


def test_duplicate_marks_do_not_duplicate_trips():
    f = trend(pipe())
    ids = marks(f, [18])
    assert len(Mapping.select(f, ids + ids).rows) == 2


@pytest.mark.parametrize("ids", [[], ["unknown"]])
def test_bad_selection_is_atomic(ids):
    p = pipe()
    f = trend(p)
    before = p.artifact.to_dict()
    with pytest.raises(ValueError):
        p.follow_up(f.M["figure_id"], ids, RANK)
    assert p.artifact.to_dict() == before


def test_follow_up_preserves_borough_and_selected_hours():
    p = pipe()
    source, target = evening(p)
    assert target.D["results"] == [{"pickup_zone_id":1,"pickup_zone":"A","trips":3}, {"pickup_zone_id":2,"pickup_zone":"B","trips":1}]
    assert len(target.D["rows"]) == 4
    assert {r["pickup_hour"] for r in target.D["rows"]} == {18,19}
    node = p.artifact.versions[p.artifact.head]
    assert node["input"]["mark_ids"] == marks(source,[18,19])
    assert node["links"][0]["dimensions"] == ["pickup_hour", "pickup_borough"]
    assert target.M["operation"] == "extension"
    selected = Mapping.select(target, [target.V["spec"]["data"]["values"][0]["mark_id"]])
    assert {r["row_id"] for r in selected.rows} == {"0","1","2"}


def test_morning_brush_updates_same_chart_preserving_evening():
    p = pipe()
    source, target = evening(p)
    old = copy.deepcopy(p.artifact.to_dict())
    old_head = p.artifact.head
    updated = p.brush(source.M["figure_id"], marks(source,[8,9]))[0]
    assert updated.M["figure_id"] == target.M["figure_id"]
    assert updated.M["version_id"] != target.M["version_id"]
    assert updated.D["results"] == [{"pickup_zone_id":2,"pickup_zone":"B","trips":3}, {"pickup_zone_id":1,"pickup_zone":"A","trips":1}]
    assert p.artifact.versions[old_head] == old["versions"][old_head]
    assert p.artifact.figures[target.M["version_id"]].D == target.D
    assert p.artifact.versions[p.artifact.head]["parents"] == [old_head]


def test_branch_from_prior_version():
    p = pipe()
    source,target = evening(p)
    old_head=p.artifact.head
    prompt=TREND.replace("Manhattan","Queens")
    branch=p.execute(RuleBasedPlanner().plan(prompt),prompt,parent_version=source.M["artifact_version"])
    node=p.artifact.versions[branch.M["artifact_version"]]
    assert node["parents"] == [source.M["artifact_version"]]
    assert target.M["figure_id"] not in node["figures"]
    assert old_head in p.artifact.versions


def test_updates_all_directly_linked_charts():
    p=pipe()
    source,first=evening(p)
    second=p.follow_up(source.M["figure_id"],marks(source,[18,19]),RANK)
    updated=p.brush(source.M["figure_id"],marks(source,[8,9]))
    assert {f.M["figure_id"] for f in updated} == {first.M["figure_id"],second.M["figure_id"]}
    assert all(f.D["results"][0]["pickup_zone"] == "B" for f in updated)


def test_json_roundtrip_and_replay(tmp_path):
    p=pipe()
    source,_=evening(p)
    p.brush(source.M["figure_id"],marks(source,[8,9]))
    path=tmp_path/'artifact.json'
    p.artifact.save(path)
    loaded=Artifact.load(path)
    assert loaded.to_dict() == p.artifact.to_dict()
    restored=Pipeline(artifact=loaded)
    for key,f in loaded.figures.items():
        replay=restored.replay(key)
        # Aggregated results, schemas, mapping and spec are identical; the
        # inlined D['rows'] may be a bounded sample in the portable artifact.
        assert replay.D["schema"] == f.D["schema"]
        assert replay.D["result_schema"] == f.D["result_schema"]
        assert replay.D["results"] == f.D["results"]
        assert replay.V["spec"] == f.V["spec"]
        assert replay.R == f.R
    assert restored.artifact.to_dict() == loaded.to_dict()


def test_repeat_has_identical_data_and_distinct_mark_ids():
    p=pipe()
    f=trend(p)
    again=trend(p)
    assert f.D == again.D
    assert list(f.R.mark_to_rows.values()) == list(again.R.mark_to_rows.values())
    assert set(f.R.mark_to_rows).isdisjoint(again.R.mark_to_rows)


@pytest.mark.parametrize("damage",["op","field","type","order","encoding","injection"])
def test_invalid_actions_rejected_without_history(damage):
    p=pipe()
    a=RuleBasedPlanner().plan(TREND)
    if damage == "op": a[0]["op"]="run_shell"
    elif damage == "field": a[1]["field"]="missing"
    elif damage == "type": a[1]["values"]=[1]
    elif damage == "order": a.reverse()
    elif damage == "injection": a[1]["field"]="pickup_hour); DROP TABLE trips; --"
    else: next(x for x in a if x["op"]=="add_encoding")["x"]="pickup_zone"
    before=p.artifact.to_dict()
    with pytest.raises(ValueError): p.execute(a,"bad")
    assert p.artifact.to_dict() == before


def test_empty_results_are_atomic():
    p=pipe()
    a=RuleBasedPlanner().plan(TREND)
    a.insert(1,{"op":"filter_rows","field":"pickup_hour","values":[0]})
    with pytest.raises(ValueError,match="rows"): p.execute(a,"empty")
    assert not p.artifact.versions


@pytest.mark.parametrize("prompt",["Predict rainfall", "Plot hourly mean tip percent for Manhattan", "Plot hourly trip counts for Manhattan in February 2024"])
def test_unsupported_planning_refused(prompt):
    with pytest.raises(ValueError): RuleBasedPlanner().plan(prompt)


def test_stale_mark_rejected():
    p=pipe()
    source,target=evening(p)
    with pytest.raises(ValueError): Mapping.select(target,marks(source,[18]))


def test_edited_sql_is_not_executed():
    p=pipe()
    f=trend(p)
    p.artifact.figures[f.M["version_id"]].C["sql"]="SELECT error('executed')"
    with pytest.raises(ValueError,match="code|SQL"): p.replay(f.M["version_id"])


@pytest.mark.parametrize("damage",["dataset","cycle","missing_figure","head"])
def test_corrupt_ledger_rejected(tmp_path,damage):
    p=pipe(); f=trend(p); data=p.artifact.to_dict()
    if damage=="dataset": data["dataset"][0]["pickup_hour"]=0
    elif damage=="cycle": data["versions"][p.artifact.head]["parents"]=[p.artifact.head]
    elif damage=="missing_figure": data["figures"].pop(f.M["version_id"])
    else: data["head"]="absent"
    path=tmp_path/'broken.json'; path.write_text(json.dumps(data))
    # Sidecar is intentionally missing; load should still reject the malformed
    # ledger rather than failing with an uncaught FileNotFoundError.
    with pytest.raises(ValueError): Artifact.load(path)


def test_planner_hook_is_opt_in(monkeypatch):
    assert isinstance(planner_from_env(),RuleBasedPlanner)
    module=types.ModuleType("local_planner")
    class LocalPlanner:
        def plan(self,instruction,selection=None): return RuleBasedPlanner().plan(TREND)
    module.factory=LocalPlanner
    monkeypatch.setitem(sys.modules,"local_planner",module)
    monkeypatch.setenv("FIGUREFLOW_PLANNER","local_planner:factory")
    p=Pipeline(rows=trips(),planner=planner_from_env())
    f=p.execute(p.planner.plan("provider input"),"provider input")
    assert len(f.D["rows"])==8


def test_default_sample_and_actual_counts():
    p=Pipeline(); f=trend(p)
    assert len(p.artifact.dataset)==50000
    with duckdb.connect() as con:
        expected=con.execute("SELECT hour(tpep_pickup_datetime), count(*) FROM read_parquet('data/yellow_tripdata_sample.parquet') t JOIN read_csv('data/taxi_zone_lookup.csv') z ON t.PULocationID=z.LocationID WHERE z.Borough='Manhattan' GROUP BY 1 ORDER BY 1").fetchall()
    assert [(r['pickup_hour'],r['trips']) for r in f.D['results']] == expected
    assert len(f.D['results'])==24
    assert p.artifact.source['sample_rows']==50000


def test_missing_full_source_is_clear(monkeypatch):
    monkeypatch.delenv('FIGUREFLOW_TAXI_PARQUET',raising=False)
    with pytest.raises(ValueError,match='FIGUREFLOW_TAXI_PARQUET'):
        Pipeline(full_data=True)


def test_duplicate_row_ids_rejected():
    rows=trips(); rows[1]['row_id']=rows[0]['row_id']
    with pytest.raises(ValueError,match='row_id'): Pipeline(rows=rows)


def test_network_blocked():
    from pytest_socket import SocketBlockedError
    with pytest.raises(SocketBlockedError): socket.socket()


def test_artifact_schema_and_selection_without_package(tmp_path):
    from pathlib import Path
    from jsonschema import Draft202012Validator
    p=pipe(); source,target=evening(p)
    data=p.artifact.to_dict()
    schema=json.loads(Path('docs/artifact.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(data)
    path=tmp_path/'portable.json'; p.artifact.save(path)
    document=json.loads(path.read_text())
    state=document['versions'][document['head']]
    f=document['figures'][state['figures'][source.M['figure_id']]]
    selected_marks=[r['mark_id'] for r in f['V']['spec']['data']['values'] if r['pickup_hour']==18]
    ids={i for mark in selected_marks for i in f['R']['mark_to_rows'][mark]}
    assert [r['row_id'] for r in f['D']['rows'] if r['row_id'] in ids]==['0','1']


def test_stored_sql_runs_without_reference_compiler():
    p=pipe(); _,f=evening(p)
    with duckdb.connect() as c:
        c.execute('CREATE TABLE trips (row_id VARCHAR, pickup_zone_id BIGINT, pickup_zone VARCHAR, pickup_borough VARCHAR, pickup_hour BIGINT, pickup_date VARCHAR)')
        c.executemany('INSERT INTO trips VALUES (?,?,?,?,?,?)',[tuple(r.values()) for r in trips()])
        assert c.execute(f.C['sql']).fetchall()==[(1,'A',3),(2,'B',1)]


def test_brush_does_not_call_planner_again():
    p=pipe(); source,_=evening(p)
    class OfflineNow:
        def plan(self,*args): raise AssertionError('Coordination must reuse stored actions')
    p.planner=OfflineNow()
    assert p.brush(source.M['figure_id'],marks(source,[8,9]))[0].D['results'][0]['pickup_zone']=='B'


def test_render_failure_does_not_append_partial_state(monkeypatch):
    import figureflow.actions as actions
    p=pipe(); before=p.artifact.to_dict()
    def broken(*args,**kwargs): raise RuntimeError('renderer unavailable')
    monkeypatch.setattr(actions.vlc,'vegalite_to_png',broken)
    with pytest.raises(RuntimeError): trend(p)
    assert p.artifact.to_dict()==before


def test_corrupt_missing_dataset_hash_rejected(tmp_path):
    p=pipe(); trend(p); data=p.artifact.to_dict(); data.pop('dataset_hash')
    path=tmp_path/'corrupt.json'; path.write_text(json.dumps(data))
    with pytest.raises(ValueError): Artifact.load(path)


def test_coordination_rejects_provider_ignoring_scope():
    p=pipe(); source=trend(p)
    class BadPlanner:
        def plan(self,prompt,selection):
            a=RuleBasedPlanner().plan(prompt,selection)
            return [x for x in a if x.get('field')!='pickup_borough']
    p.planner=BadPlanner()
    before=p.artifact.to_dict()
    with pytest.raises(ValueError): p.follow_up(source.M['figure_id'],marks(source,[18,19]),RANK)
    assert p.artifact.to_dict()==before
