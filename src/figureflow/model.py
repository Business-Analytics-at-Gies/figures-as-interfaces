"""Serializable figure states, mark lineage and append-only artifact snapshots."""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


@dataclass
class Selection:
    rows: list[dict]
    hours: list[int]
    boroughs: list[str]
    mark_ids: list[str]


@dataclass
class Mapping:
    """R_t: version-scoped visual marks to the exact contributing row ids."""
    mark_to_rows: dict[str, list[str]]

    @staticmethod
    def select(figure: Figure, mark_ids: list[str]) -> Selection:
        if not isinstance(mark_ids, list) or not mark_ids or any(type(m) is not str for m in mark_ids):
            raise ValueError("Select one or more mark ids")
        unique = list(dict.fromkeys(mark_ids))
        if any(m not in figure.R.mark_to_rows for m in unique):
            raise ValueError("Unknown or stale mark id for this figure version")
        ids = {r for m in unique for r in figure.R.mark_to_rows[m]}
        rows = copy.deepcopy([r for r in figure.D["rows"] if r["row_id"] in ids])
        if len(rows) != len(ids):
            raise ValueError("Mapping references missing source rows")
        return Selection(rows, sorted({r["pickup_hour"] for r in rows}), sorted({r["pickup_borough"] for r in rows}), unique)


@dataclass
class Figure:
    """F_t = {V_t, C_t, D_t, M_t}, plus its explicit bidirectional relation."""
    V: dict
    C: dict
    D: dict
    M: dict
    R: Mapping

    @classmethod
    def from_dict(cls, value: dict) -> Figure:
        value = copy.deepcopy(value)
        value["R"] = Mapping(**value["R"])
        return cls(**value)


@dataclass
class Artifact:
    """A versioned DAG of complete exploration states, including coordination."""
    dataset: list[dict]
    artifact_id: str = "taxi-exploration"
    source: dict = field(default_factory=dict)
    figures: dict[str, Figure] = field(default_factory=dict)
    versions: dict[str, dict] = field(default_factory=dict)
    head: str | None = None
    format_version: int = 1
    dataset_hash: str = ""

    def __post_init__(self):
        self.dataset = copy.deepcopy(self.dataset)
        if not self.dataset_hash:
            self.dataset_hash = digest(self.dataset)

    def to_dict(self) -> dict:
        return asdict(self)

    def validate(self) -> None:
        if self.format_version != 1 or digest(self.dataset) != self.dataset_hash:
            raise ValueError("Unsupported format or dataset checksum mismatch")
        if self.head is None and (self.versions or self.figures):
            raise ValueError("Missing artifact head")
        if self.head is not None and self.head not in self.versions:
            raise ValueError("Unknown artifact head")
        visited, visiting = set(), set()

        def visit(key):
            if key in visiting:
                raise ValueError("Artifact version cycle")
            if key in visited:
                return
            if key not in self.versions:
                raise ValueError("Missing parent artifact version")
            visiting.add(key)
            node = self.versions[key]
            for parent in node["parents"]:
                visit(parent)
            for logical, version in node["figures"].items():
                if version not in self.figures or self.figures[version].M["figure_id"] != logical:
                    raise ValueError("Missing or mismatched figure version")
            for link in node["links"]:
                if link["source"] not in node["figures"] or link["target"] not in node["figures"]:
                    raise ValueError("Dangling coordination link")
                if link["source"] == link["target"] or link["dimensions"] != ["pickup_hour", "pickup_borough"]:
                    raise ValueError("Invalid coordination rule")
            visiting.remove(key)
            visited.add(key)

        for key in self.versions:
            visit(key)
        for key, figure in self.figures.items():
            if figure.M["version_id"] != key or figure.M["artifact_id"] != self.artifact_id:
                raise ValueError("Mismatched figure metadata")
            node = self.versions.get(figure.M["artifact_version"])
            if node is None or node["figures"].get(figure.M["figure_id"]) != key:
                raise ValueError("Invalid figure artifact link")

    def save(self, path: str | Path) -> None:
        self.validate()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n")
        temporary.replace(path)

    @classmethod
    def load(cls, path: str | Path) -> Artifact:
        try:
            value = json.loads(Path(path).read_text())
            if not value.get("dataset_hash"):
                raise ValueError("Missing dataset checksum")
            value["figures"] = {k: Figure.from_dict(v) for k, v in value["figures"].items()}
            artifact = cls(**value)
            artifact.validate()
            return artifact
        except (KeyError, TypeError, RecursionError) as error:
            raise ValueError("Malformed artifact ledger") from error
