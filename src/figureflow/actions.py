"""Allowlisted analytical actions compile into inspectable, replayable DuckDB SQL."""
from __future__ import annotations

import base64
import copy

import vl_convert as vlc

from .dataset import SCHEMA, connection_for, records
from .model import Mapping


def validate(actions: list[dict]) -> list[dict]:
    if not isinstance(actions, list) or not actions or any(not isinstance(a, dict) for a in actions):
        raise ValueError('Expected a nonempty action sequence')
    actions = copy.deepcopy(actions)
    ops = [a.get('op') for a in actions]
    tail = ['group_by', 'aggregate', 'sort_rows', 'add_chart_type', 'add_encoding', 'add_params', 'add_data']
    if ops[0] != 'select_table' or ops[-7:] != tail or any(o != 'filter_rows' for o in ops[1:-7]):
        raise ValueError('Unsupported action or invalid action order')
    if actions[0] != {'op': 'select_table', 'table': 'trips'}:
        raise ValueError('Unknown table')
    for action in actions[1:-7]:
        if set(action) != {'op', 'field', 'values'} or action['field'] not in {'pickup_borough', 'pickup_hour'}:
            raise ValueError('Invalid filter field')
        values = action['values']
        kind = str if action['field'] == 'pickup_borough' else int
        if not isinstance(values, list) or not values or any(type(v) is not kind for v in values):
            raise ValueError('Invalid filter value type')
        if action['field'] == 'pickup_hour' and any(not 0 <= v <= 23 for v in values):
            raise ValueError('Hour outside 0..23')
        action['values'] = sorted(set(values))
    group, aggregate, sort, chart, encoding, params, data = actions[-7:]
    by = group.get('field')
    if group != {'op': 'group_by', 'field': by} or by not in {'pickup_hour', 'pickup_zone_id'}:
        raise ValueError('Group by pickup hour or pickup zone')
    if aggregate != {'op': 'aggregate', 'function': 'count'}:
        raise ValueError('Only trip counts are supported')
    is_hour = by == 'pickup_hour'
    if sort != {'op': 'sort_rows', 'field': 'pickup_hour' if is_hour else 'trips', 'descending': not is_hour}:
        raise ValueError('Invalid sorting for this chart')
    if chart != {'op': 'add_chart_type', 'type': 'line' if is_hour else 'bar'}:
        raise ValueError('Chart does not match grouped data')
    if encoding != {'op': 'add_encoding', 'x': by, 'y': 'trips'}:
        raise ValueError('Encoding does not match grouped data')
    if params != {'op': 'add_params', 'type': 'interval', 'encoding': 'x'} or data != {'op': 'add_data'}:
        raise ValueError('Invalid interaction or data action')
    return actions


def sql_literal(value: str | int) -> str:
    return str(value) if type(value) is int else "'" + value.replace("'", "''") + "'"


def compile_sql(actions: list[dict]) -> str:
    actions = validate(actions)
    by = actions[-7]['field']
    predicates = [a['field'] + ' IN (' + ', '.join(sql_literal(v) for v in a['values']) + ')' for a in actions[1:-7]]
    where = ' AND '.join(predicates) or 'TRUE'
    groups = 'pickup_hour' if by == 'pickup_hour' else 'pickup_zone_id, pickup_zone'
    order = 'pickup_hour' if by == 'pickup_hour' else 'trips DESC, pickup_zone_id ASC'
    return (f'CREATE TEMP TABLE selected AS SELECT * FROM trips WHERE {where};\n'
            f'SELECT {groups}, count(*) AS trips FROM selected GROUP BY {groups} ORDER BY {order};\n')


def compile_visualization(actions: list[dict]) -> str:
    actions = validate(actions)
    by, chart = actions[-7]['field'], actions[-4]['type']
    is_hour = by == 'pickup_hour'
    # Horizontal bars keep full NYC zone names readable. Action encodings describe
    # grouping/measure; this renderer chooses orientation for their visual channels.
    category = {'field': 'pickup_hour' if is_hour else 'pickup_zone',
                'type': 'ordinal' if is_hour else 'nominal', 'title': 'Pickup hour' if is_hour else 'Pickup zone'}
    category['sort'] = list(range(24)) if is_hour else '-x'
    measure = {'field': 'trips', 'type': 'quantitative', 'title': 'Trips in sample', 'scale': {'zero': True}}
    spec = {
        '$schema': 'https://vega.github.io/schema/vega-lite/v5.json',
        'width': 640, 'height': 300 if is_hour else {'step': 19},
        'title': 'Hourly pickup counts' if is_hour else 'Pickup zones ranked by trips',
        'description': 'TLC January 2024 sample. Identifiable points or bars resolve to original trip rows.',
        'mark': {'type': chart, **({'point': True} if is_hour else {})},
        'params': [{'name': 'brush', 'select': {'type': 'interval', 'encodings': ['x' if is_hour else 'y']}}],
        'encoding': {'x': category if is_hour else measure, 'y': measure if is_hour else category,
                     'tooltip': [{'field': by}, {'field': 'trips'}, {'field': 'mark_id'}]},
        'config': {'background': 'white', 'font': 'Arial', 'axis': {'labelFontSize': 11, 'titleFontSize': 12, 'labelLimit': 310}},
    }
    return (
        "values = []\nmark_to_rows = {}\n"
        "for result in results:\n"
        f"    mark_id = version_id + ':' + str(result[{by!r}])\n"
        "    values.append({**result, 'mark_id': mark_id})\n"
        f"    mark_to_rows[mark_id] = lineage[str(result[{by!r}])]\n"
        f"spec = {spec!r}\n"
        "spec['data'] = {'values': values}\n"
        "boroughs = sorted({row['pickup_borough'] for row in rows})\n"
        "hours = sorted({row['pickup_hour'] for row in rows})\n"
        "scope = ', '.join(boroughs) + '; January 2024; hours ' + ', '.join(map(str, hours))\n"
        "spec['title'] = {'text': spec['title'], 'subtitle': scope}\n"
        "summary = 'TLC sample: ' + scope + '. ' + str(len(rows)) + ' trips. Counts: ' + '; '.join("
        f"str(row[{by!r}]) + '=' + str(row['trips']) for row in results)\n"
    )


def materialize(actions, source_rows, version_id, sql=None, visualization=None):
    canonical_sql = compile_sql(actions)
    canonical_visualization = compile_visualization(actions)
    if sql is not None and sql != canonical_sql:
        raise ValueError('Stored SQL code does not match validated actions')
    if visualization is not None and visualization != canonical_visualization:
        raise ValueError('Stored visualization code does not match validated actions')
    by = actions[-7]['field']
    with connection_for(source_rows) as connection:
        results = records(connection.execute(sql if sql is not None else canonical_sql))
        rows = records(connection.execute('SELECT * FROM selected ORDER BY row_id'))
        lineage = {str(k): ids for k,ids in connection.execute(
            f'SELECT {by}, list(row_id ORDER BY row_id) FROM selected GROUP BY {by} ORDER BY {by}').fetchall()}
    if not rows:
        raise ValueError('No rows match the requested analysis')
    context = {'rows': rows, 'results': results, 'lineage': lineage, 'version_id': version_id}
    exec(visualization if visualization is not None else canonical_visualization, context)
    png = vlc.vegalite_to_png(context['spec'], vl_version='5.20', allowed_base_urls=[])
    result_schema = {by: 'BIGINT', **({'pickup_zone':'VARCHAR'} if by == 'pickup_zone_id' else {}), 'trips':'BIGINT'}
    D = {'rows': rows, 'schema': dict(SCHEMA), 'results': results, 'result_schema': result_schema}
    V = {
        'spec': context['spec'],
        'png': base64.b64encode(png).decode('ascii'),
        'png_path': f"{version_id}.png",
        'summary': context['summary'],
    }
    return V, D, Mapping(context['mark_to_rows'])
