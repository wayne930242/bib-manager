import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException

from services import database as db

router = APIRouter(prefix="/cli", tags=["cli"])

# Project root (phd-essay)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent


@router.post("/sync")
def sync_bibliography():
    """
    Sync bibliography:
    1. Run convert-zotero (if JSON exists)
    2. Run fix-bib
    3. Rebuild database from BibTeX
    """
    results = {"steps": []}

    # Step 1: Convert Zotero (if JSON exists)
    zotero_json = PROJECT_ROOT / "references" / "Exported Items.json"
    if zotero_json.exists():
        try:
            result = subprocess.run(
                ["uv", "run", "convert-zotero"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=60
            )
            results["steps"].append({
                "name": "convert-zotero",
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None
            })
        except subprocess.TimeoutExpired:
            results["steps"].append({
                "name": "convert-zotero",
                "success": False,
                "error": "Timeout"
            })
    else:
        results["steps"].append({
            "name": "convert-zotero",
            "success": True,
            "output": "Skipped (no Zotero JSON found)"
        })

    # Step 2: Fix bibliography
    try:
        result = subprocess.run(
            ["uv", "run", "fix-bib"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60
        )
        results["steps"].append({
            "name": "fix-bib",
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        })
    except subprocess.TimeoutExpired:
        results["steps"].append({
            "name": "fix-bib",
            "success": False,
            "error": "Timeout"
        })

    # Step 3: Sync database
    try:
        count = db.sync_from_bibtex()
        results["steps"].append({
            "name": "sync-database",
            "success": True,
            "output": f"Synced {count} entries to database"
        })
    except Exception as e:
        results["steps"].append({
            "name": "sync-database",
            "success": False,
            "error": str(e)
        })

    # Overall success
    results["success"] = all(step["success"] for step in results["steps"])

    return results


@router.post("/fix")
def fix_bibliography():
    """Run fix-bib only."""
    try:
        result = subprocess.run(
            ["uv", "run", "fix-bib"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Command timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebuild-db")
def rebuild_database():
    """Rebuild database from current BibTeX file."""
    try:
        count = db.sync_from_bibtex()
        return {
            "success": True,
            "entries_synced": count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
