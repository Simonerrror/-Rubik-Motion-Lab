from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cubeanim.cards import repository
from cubeanim.cards.db import (
    DEFAULT_DB_ENV,
    connect,
    default_db_path,
    initialize_database,
    reset_runtime_state,
    repo_root_from_file,
)
from cubeanim.cards.recognizer import ensure_recognizer_assets
from cubeanim_domain.sandbox import build_sandbox_timeline


@dataclass
class CardsService:
    repo_root: Path
    db_path: Path

    @classmethod
    def create(
        cls,
        repo_root: Path | None = None,
        db_path: Path | None = None,
    ) -> "CardsService":
        root = repo_root or repo_root_from_file()
        path = db_path
        if path is None:
            import os

            env_path = os.environ.get(DEFAULT_DB_ENV, "").strip()
            path = Path(env_path) if env_path else default_db_path(root)
        initialize_database(repo_root=root, db_path=path)
        return cls(repo_root=root, db_path=path)

    def list_algorithms(self, group: str = "ALL") -> list[dict[str, Any]]:
        with connect(self.db_path) as conn:
            rows = repository.list_algorithms(conn, group=group)
            return [self._decorate_algorithm(row) for row in rows]

    def reset_runtime(self) -> dict[str, Any]:
        path = reset_runtime_state(repo_root=self.repo_root, db_path=self.db_path)
        self.db_path = path
        return {"db_path": str(path)}

    def list_categories(self, *, enabled_only: bool = True) -> list[dict[str, Any]]:
        with connect(self.db_path) as conn:
            return repository.list_categories(conn, enabled_only=enabled_only)

    def _known_category_codes(self) -> set[str]:
        return {item["code"] for item in self.list_categories(enabled_only=True)}

    @staticmethod
    def _normalize_group_name(value: str, field: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError(f"{field} must be non-empty")
        return normalized

    def list_reference_sets(self, category: str) -> list[dict[str, Any]]:
        normalized = self._normalize_group_name(category, "category")
        known_codes = self._known_category_codes()
        if normalized not in known_codes:
            raise ValueError(f"category must be one of {sorted(known_codes)}")
        with connect(self.db_path) as conn:
            return repository.list_reference_sets(conn, category=normalized)

    def list_cases(self, group: str) -> list[dict[str, Any]]:
        normalized = self._normalize_group_name(group, "group")
        known_codes = self._known_category_codes()
        if normalized not in known_codes:
            raise ValueError(f"group must be one of {sorted(known_codes)}")
        with connect(self.db_path) as conn:
            rows = repository.list_cases(conn, group=normalized)
            return [self._decorate_case(row) for row in rows]

    def get_case(self, case_id: int) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            row = repository.get_case(conn, case_id=case_id)
            if row is None:
                raise KeyError(f"case id {case_id} not found")
            row["algorithms"] = repository.list_case_alternatives(conn, case_id=case_id)
            return self._decorate_case(row)

    def list_alternatives(self, case_id: int) -> list[dict[str, Any]]:
        with connect(self.db_path) as conn:
            case_row = repository.get_case(conn, case_id=case_id)
            if case_row is None:
                raise KeyError(f"case id {case_id} not found")
            return repository.list_case_alternatives(conn, case_id=case_id)

    def activate_case_algorithm(self, case_id: int, algorithm_id: int) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            algorithm = repository.get_algorithm(conn, algorithm_id)
            if algorithm is None or int(algorithm.get("case_id") or -1) != case_id:
                raise KeyError("algorithm does not belong to case")
            self._validate_formula_for_group(
                formula=str(algorithm.get("formula") or ""),
                group=str(algorithm.get("group") or ""),
            )
            repository.set_case_selected_algorithm(conn, case_id=case_id, algorithm_id=algorithm_id)
            refreshed = repository.get_case(conn, case_id=case_id)
            if refreshed is None:
                raise KeyError(f"case id {case_id} not found")
            self._refresh_case_recognizer(conn, refreshed)
            updated = repository.get_case(conn, case_id=case_id)
            if updated is None:
                raise KeyError(f"case id {case_id} not found")
            updated["algorithms"] = repository.list_case_alternatives(conn, case_id=case_id)
            return self._decorate_case(updated)

    def activate_alternative(self, case_id: int, algorithm_id: int) -> dict[str, Any]:
        return self.activate_case_algorithm(case_id=case_id, algorithm_id=algorithm_id)

    def create_case_custom_algorithm(
        self,
        case_id: int,
        formula: str,
        name: str | None = None,
        activate: bool = True,
    ) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            case_row = repository.get_case(conn, case_id=case_id)
            if case_row is None:
                raise KeyError(f"case id {case_id} not found")
            self._validate_formula_for_group(
                formula=formula,
                group=str(case_row.get("group") or ""),
            )
            repository.create_custom_algorithm_for_case(
                conn,
                case_id=case_id,
                formula=formula,
                name=name,
                activate=activate,
            )
            refreshed = repository.get_case(conn, case_id=case_id)
            if refreshed is None:
                raise KeyError(f"case id {case_id} not found")
            self._refresh_case_recognizer(conn, refreshed)
            updated = repository.get_case(conn, case_id=case_id)
            if updated is None:
                raise KeyError(f"case id {case_id} not found")
            updated["algorithms"] = repository.list_case_alternatives(conn, case_id=case_id)
            return self._decorate_case(updated)

    def create_alternative(
        self,
        case_id: int,
        formula: str,
        name: str | None = None,
        activate: bool = True,
    ) -> dict[str, Any]:
        return self.create_case_custom_algorithm(
            case_id=case_id,
            formula=formula,
            name=name,
            activate=activate,
        )

    def delete_case_algorithm(
        self,
        case_id: int,
        algorithm_id: int,
    ) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            repository.delete_case_algorithm(
                conn,
                case_id=case_id,
                algorithm_id=algorithm_id,
            )
            refreshed = repository.get_case(conn, case_id=case_id)
            if refreshed is None:
                raise KeyError(f"case id {case_id} not found")
            self._refresh_case_recognizer(conn, refreshed)
            updated = repository.get_case(conn, case_id=case_id)
            if updated is None:
                raise KeyError(f"case id {case_id} not found")
            updated["algorithms"] = repository.list_case_alternatives(conn, case_id=case_id)
            return {
                "case": self._decorate_case(updated),
                "deleted_algorithm_id": algorithm_id,
            }

    def delete_alternative(self, case_id: int, algorithm_id: int) -> dict[str, Any]:
        return self.delete_case_algorithm(case_id=case_id, algorithm_id=algorithm_id)

    def get_algorithm(self, algorithm_id: int) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            row = repository.get_algorithm(conn, algorithm_id)
            if row is None:
                raise KeyError(f"algorithm id {algorithm_id} not found")
            return self._decorate_algorithm(row)

    def create_custom_algorithm(
        self,
        name: str,
        formula: str,
        group: str,
        case_code: str,
    ) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            self._validate_formula_for_group(formula=formula, group=group)
            created = repository.create_custom_algorithm(
                conn,
                name=name,
                formula=formula,
                group=group,
                case_code=case_code,
            )
            case_row = repository.get_case(conn, case_id=int(created["case_id"]))
            if case_row is not None:
                self._refresh_case_recognizer(conn, case_row)
            return self._decorate_algorithm(created)

    def set_progress(self, algorithm_id: int, status: str) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            repository.set_progress_status(conn, algorithm_id=algorithm_id, status=status)
            row = repository.get_algorithm(conn, algorithm_id)
            if row is None:
                raise KeyError(f"algorithm id {algorithm_id} not found")
            return self._decorate_algorithm(row)

    def set_case_progress(self, case_id: int, status: str) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            case_row = repository.get_case(conn, case_id=case_id)
            if case_row is None:
                raise KeyError(f"case id {case_id} not found")
            algorithm_id = case_row.get("active_algorithm_id")
            if algorithm_id is None:
                raise ValueError("Case has no active algorithm")
            repository.set_progress_status(conn, algorithm_id=int(algorithm_id), status=status)
            refreshed = repository.get_case(conn, case_id=case_id)
            if refreshed is None:
                raise KeyError(f"case id {case_id} not found")
            return self._decorate_case(refreshed)

    @staticmethod
    def _normalize_formula(formula: str) -> str:
        return " ".join(formula.split())

    @classmethod
    def _validate_formula_for_group(cls, formula: str, group: str) -> None:
        normalized_group = cls._normalize_group_name(group, "group")
        normalized_formula = cls._normalize_formula(formula)
        if not normalized_formula:
            raise ValueError("Formula is empty")
        build_sandbox_timeline(formula=normalized_formula, group=normalized_group)

    def _refresh_case_recognizer(self, conn, case_row: dict[str, Any]) -> None:
        case_id = int(case_row["id"])
        category = str(case_row["group"])
        case_code = str(case_row["case_code"])
        formula = str(case_row.get("active_formula") or "")
        assets = ensure_recognizer_assets(
            self.db_path.parent,
            category=category,
            case_code=case_code,
            formula=formula,
        )
        repository.update_case_recognizer_paths(
            conn,
            case_id=case_id,
            svg_rel_path=assets.svg_rel_path,
            png_rel_path=assets.png_rel_path,
        )

    @staticmethod
    def _decorate_algorithm(row: dict[str, Any]) -> dict[str, Any]:
        return dict(row)

    @staticmethod
    def _decorate_case(row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        algorithms = row.get("algorithms")
        if isinstance(algorithms, list):
            payload["algorithms"] = [
                {
                    **item,
                    "is_active": item["id"] == row.get("active_algorithm_id"),
                }
                for item in algorithms
            ]
        return payload
