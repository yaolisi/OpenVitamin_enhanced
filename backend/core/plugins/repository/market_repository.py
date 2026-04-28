from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from core.data.base import db_session
from core.data.models.plugin_market import PluginInstallationORM, PluginPackageORM


class PluginMarketRepository:
    def upsert_package(self, payload: Dict[str, Any]) -> PluginPackageORM:
        package_id = str(payload["id"])
        with db_session() as db:
            row = db.query(PluginPackageORM).filter(PluginPackageORM.id == package_id).first()
            if row is None:
                row = PluginPackageORM(id=package_id)
                db.add(row)
            row.name = str(payload.get("name") or "")
            row.version = str(payload.get("version") or "")
            row.manifest_path = str(payload.get("manifest_path") or "")
            row.package_path = payload.get("package_path")
            row.description = payload.get("description")
            row.author = payload.get("author")
            row.source = str(payload.get("source") or "third_party")
            row.review_status = str(payload.get("review_status") or "pending")
            row.visibility = str(payload.get("visibility") or "private")
            row.signature = payload.get("signature")
            row.signature_digest = payload.get("signature_digest")
            row.compatible_gateway_versions = json.dumps(payload.get("compatible_gateway_versions") or [])
            row.permissions_json = json.dumps(payload.get("permissions") or [])
            row.metadata_json = json.dumps(payload.get("metadata") or {})
            db.flush()
            return row

    def get_package(self, package_id: str) -> Optional[PluginPackageORM]:
        with db_session() as db:
            return db.query(PluginPackageORM).filter(PluginPackageORM.id == package_id).first()

    def list_packages(self, review_status: Optional[str] = None) -> List[PluginPackageORM]:
        with db_session() as db:
            q = db.query(PluginPackageORM)
            if review_status:
                q = q.filter(PluginPackageORM.review_status == review_status)
            return q.order_by(PluginPackageORM.updated_at.desc()).all()

    def set_review_status(self, package_id: str, status: str) -> bool:
        with db_session() as db:
            row = db.query(PluginPackageORM).filter(PluginPackageORM.id == package_id).first()
            if row is None:
                return False
            row.review_status = status
            return True

    def set_visibility(self, package_id: str, visibility: str) -> bool:
        with db_session() as db:
            row = db.query(PluginPackageORM).filter(PluginPackageORM.id == package_id).first()
            if row is None:
                return False
            row.visibility = visibility
            return True

    def upsert_installation(
        self,
        *,
        package_id: str,
        name: str,
        version: str,
        manifest_path: str,
        enabled: bool,
        installed_by: Optional[str],
    ) -> PluginInstallationORM:
        with db_session() as db:
            row = (
                db.query(PluginInstallationORM)
                .filter(PluginInstallationORM.package_id == package_id)
                .first()
            )
            if row is None:
                row = PluginInstallationORM(package_id=package_id)
                db.add(row)
            row.name = name
            row.version = version
            row.manifest_path = manifest_path
            row.enabled = 1 if enabled else 0
            row.installed_by = installed_by
            db.flush()
            return row

    def get_installation(self, package_id: str) -> Optional[PluginInstallationORM]:
        with db_session() as db:
            return (
                db.query(PluginInstallationORM)
                .filter(PluginInstallationORM.package_id == package_id)
                .first()
            )

    def list_installations(self) -> List[PluginInstallationORM]:
        with db_session() as db:
            return db.query(PluginInstallationORM).order_by(PluginInstallationORM.updated_at.desc()).all()

    def set_installation_enabled(self, package_id: str, enabled: bool) -> bool:
        with db_session() as db:
            row = (
                db.query(PluginInstallationORM)
                .filter(PluginInstallationORM.package_id == package_id)
                .first()
            )
            if row is None:
                return False
            row.enabled = 1 if enabled else 0
            return True


_repo: Optional[PluginMarketRepository] = None


def get_plugin_market_repository() -> PluginMarketRepository:
    global _repo
    if _repo is None:
        _repo = PluginMarketRepository()
    return _repo
