"""Explicit DB-first import/export operations for local workflows."""

from fastapi import APIRouter, HTTPException

from services import database as db

router = APIRouter(prefix="/cli", tags=["cli"])


@router.post("/export")
def export_bibliography():
    """Generate the shared Typst BibTeX file from the canonical DB."""
    try:
        content = db.export_bibtex(output_path=db.BIB_PATH)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return {
        "success": True,
        "direction": "database-to-bibtex",
        "output": str(db.BIB_PATH),
        "entries_exported": content.count("\n@") + bool(content),
    }


@router.post("/sync", deprecated=True)
def legacy_sync_alias():
    """Backward-compatible alias; sync now only exports DB to BibTeX."""
    return export_bibliography()


@router.post("/import-legacy")
def import_legacy_bibliography(replace: bool = False):
    """Explicit one-way migration from the legacy BibTeX file into the DB."""
    try:
        count = db.import_bibtex(db.BIB_PATH, replace=replace)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {
        "success": True,
        "direction": "bibtex-to-database",
        "entries_imported": count,
        "replace": replace,
    }
