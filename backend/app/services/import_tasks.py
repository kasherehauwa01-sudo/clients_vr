from copy import deepcopy
from threading import Lock
from time import monotonic
from uuid import uuid4

from app.db.session import SessionLocal
from app.services.importer import ImportSummary, import_files


_tasks: dict[str, dict] = {}
_lock = Lock()
import_process_lock = Lock()


def create_import_task(files: list[tuple[str, bytes]]) -> str:
    task_id = uuid4().hex
    with _lock:
        _tasks[task_id] = {
            "task_id": task_id,
            "status": "accepted",
            "stage": "Подготовка файла…",
            "progress": 0,
            "processed": 0,
            "total": 0,
            "result": None,
            "error": None,
        }
    return task_id


def get_import_task(task_id: str) -> dict | None:
    with _lock:
        task = _tasks.get(task_id)
        return deepcopy(task) if task else None


def run_import_task(task_id: str, files: list[tuple[str, bytes]]) -> None:
    started = monotonic()

    def progress(stage: str, processed: int = 0, total: int = 0) -> None:
        percent = round(processed * 100 / total) if total else 0
        with _lock:
            _tasks[task_id].update(
                status="running", stage=stage, progress=min(percent, 99), processed=processed, total=total
            )

    if not import_process_lock.acquire(blocking=False):
        with _lock:
            _tasks[task_id].update(status="failed", stage="Ошибка", error="Другой импорт уже выполняется")
        return
    try:
        with SessionLocal() as db:
            result: ImportSummary = import_files(db, files, progress=progress)
        with _lock:
            _tasks[task_id].update(
                status="completed",
                stage="Готово",
                progress=100,
                result=result.model_dump(),
                duration=round(monotonic() - started, 3),
            )
    except Exception as error:
        with _lock:
            _tasks[task_id].update(
                status="failed",
                stage="Ошибка",
                error=str(error).strip() or error.__class__.__name__,
                duration=round(monotonic() - started, 3),
            )
    finally:
        import_process_lock.release()
