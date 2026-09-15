"""Single transactional path from actions or brush events to persisted figures."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import platform

import duckdb
import vl_convert

from .actions import compile_sql, compile_visualization, materialize, validate
from .dataset import load_rows, validate_rows
from .model import Artifact, Figure, Mapping
from .planner import Planner, planner_from_env, selection_filters


class Pipeline:
    def __init__(self, rows=None, artifact: Artifact | None = None,
                 planner: Planner | None = None, full_data: bool = False):
        if artifact is not None and (rows is not None or full_data):
            raise ValueError('Use either an artifact or input data')
        self.planner = planner if planner is not None else planner_from_env()
        if artifact is None:
            if rows is None:
                rows, source = load_rows(full_data)
            else:
                source = {'kind':'supplied trip rows', 'sample_rows':len(rows)}
            validate_rows(rows)
            artifact = Artifact(rows, source=source)
        artifact.validate()
        validate_rows(artifact.dataset)
        self.artifact = artifact

    def _base(self, parent_version=None):
        key = parent_version if parent_version is not None else self.artifact.head
        if key is None:
            return None, {'figures':{},'links':[]}
        if key not in self.artifact.versions:
            raise ValueError('Unknown parent artifact version')
        return key, copy.deepcopy(self.artifact.versions[key])

    def _figure(self, logical, node):
        if logical not in node['figures']:
            raise ValueError('Figure does not exist in the selected artifact state')
        return self.artifact.figures[node['figures'][logical]]

    def _make(self, actions, instruction, operation, logical, artifact_version, offset=0):
        actions = validate(actions)
        version_id = f'f{len(self.artifact.figures) + offset + 1:04d}'
        V,D,R = materialize(actions, self.artifact.dataset, version_id)
        C = {'actions':actions, 'sql':compile_sql(actions),
             'visualization_python':compile_visualization(actions),
             'environment':{'duckdb':duckdb.__version__, 'vl_convert':vl_convert.__version__,
                            'vega_lite':'5.20', 'python':platform.python_version()}}
        M = {'figure_id':logical, 'version_id':version_id, 'timestamp':datetime.now(timezone.utc).isoformat(),
             'operation':operation, 'instruction':instruction,
             'artifact_id':self.artifact.artifact_id, 'artifact_version':artifact_version}
        return Figure(V,C,D,M,R)

    def _commit(self, parent, node, figures, event, version):
        # Build the candidate first; a failed execution, rendering or validation
        # never leaves a partially appended ledger.
        candidate = copy.deepcopy(self.artifact)
        for figure in figures:
            candidate.figures[figure.M['version_id']] = copy.deepcopy(figure)
            node['figures'][figure.M['figure_id']] = figure.M['version_id']
        candidate.versions[version] = {
            'parents': [] if parent is None else [parent],
            'figures':node['figures'], 'links':node['links'], 'input':copy.deepcopy(event),
            'timestamp':datetime.now(timezone.utc).isoformat(),
        }
        candidate.head = version
        candidate.validate()
        self.artifact = candidate

    def execute(self, actions, instruction, parent_version=None):
        parent,node = self._base(parent_version)
        version = f'a{len(self.artifact.versions)+1:04d}'
        logical = f'chart{len({f.M["figure_id"] for f in self.artifact.figures.values()})+1:04d}'
        figure = self._make(actions,instruction,'generation',logical,version)
        self._commit(parent,node,[figure],{'type':'language','instruction':instruction,'actions':figure.C['actions']},version)
        return copy.deepcopy(figure)

    def follow_up(self, source_id, mark_ids, instruction):
        parent,node = self._base()
        source = self._figure(source_id,node)
        selection = Mapping.select(source,mark_ids)
        actions = validate(self.planner.plan(instruction,selection))
        # The minimal coordination contract is hour/borough -> zone counts.
        if source.C['actions'][-7]['field'] != 'pickup_hour' or actions[-7]['field'] != 'pickup_zone_id':
            raise ValueError('Coordination requires an hourly source and pickup-zone ranking')
        # Enforce brush semantics even for a provider-backed planner.
        filters = {a['field']:a['values'] for a in actions[1:-7]}
        if filters != {'pickup_hour':selection.hours,'pickup_borough':selection.boroughs}:
            raise ValueError('Planner must preserve selected hours and pickup borough')
        version = f'a{len(self.artifact.versions)+1:04d}'
        logical = f'chart{len({f.M["figure_id"] for f in self.artifact.figures.values()})+1:04d}'
        figure = self._make(actions,instruction,'extension',logical,version)
        node['links'].append({'source':source_id,'target':logical,
                              'dimensions':['pickup_hour','pickup_borough'],
                              'action_template':copy.deepcopy(actions)})
        event={'type':'extension','instruction':instruction,'source_figure_version':source.M['version_id'],
               'mark_ids':selection.mark_ids,'actions':actions}
        self._commit(parent,node,[figure],event,version)
        return copy.deepcopy(figure)

    def brush(self, source_id, mark_ids):
        parent,node = self._base()
        source = self._figure(source_id,node)
        selection = Mapping.select(source,mark_ids)
        links=[link for link in node['links'] if link['source']==source_id]
        if not links:
            raise ValueError('Source figure has no coordinated targets')
        version = f'a{len(self.artifact.versions)+1:04d}'
        updates=[]
        for link in links:
            template=copy.deepcopy(link['action_template'])
            remaining=[a for a in template[1:-7] if a['field'] not in link['dimensions']]
            actions=[template[0],*remaining,*selection_filters(selection),*template[-7:]]
            updates.append(self._make(actions,'Brush changed to hours '+str(selection.hours),
                                      'coordination',link['target'],version,len(updates)))
        event={'type':'brush','source_figure_version':source.M['version_id'],'mark_ids':selection.mark_ids,
               'actions_by_target':{f.M['figure_id']:f.C['actions'] for f in updates}}
        self._commit(parent,node,updates,event,version)
        return copy.deepcopy(updates)

    def replay(self, figure_version_id):
        self.artifact.validate()
        if figure_version_id not in self.artifact.figures:
            raise ValueError('Unknown figure version')
        figure=self.artifact.figures[figure_version_id]
        V,D,R=materialize(figure.C['actions'],self.artifact.dataset,figure_version_id,
                           sql=figure.C['sql'],visualization=figure.C['visualization_python'])
        # Replay validates the analytical result, mapping and visualization.
        # The inlined D['rows'] in the portable artifact may be a bounded
        # sample, so we compare schemas and aggregates but not full row lists.
        if (
            D['schema'] != figure.D['schema'] or
            D['result_schema'] != figure.D['result_schema'] or
            D['results'] != figure.D['results'] or
            R != figure.R or
            V['spec'] != figure.V['spec'] or
            V['summary'] != figure.V['summary']
        ):
            raise ValueError('Replay differs from recorded aggregates, mapping or visualization')
        return Figure(V,copy.deepcopy(figure.C),D,copy.deepcopy(figure.M),R)
