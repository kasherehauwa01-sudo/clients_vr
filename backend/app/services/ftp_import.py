from datetime import datetime
from ftplib import FTP, error_perm
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from time import monotonic, sleep
import traceback

from pydantic import BaseModel, Field

from app.db.session import SessionLocal
from app.models.entities import FtpImportEvent
from app.services.import_tasks import import_process_lock
from app.services.importer import import_files

logger = logging.getLogger("clients.import")
_state_lock = Lock()
_run_lock = Lock()
_state = {
    "running": False, "connection_status": "unknown", "stage": "Ожидание",
    "last_successful_check": None, "last_successful_import": None,
    "found_files": 0, "processed_files": 0, "successful_files": 0,
    "failed_files": 0, "last_error": None, "next_run": None,
}


class FtpSettings(BaseModel):
    host: str = ""
    port: int = 21
    user: str = ""
    password: str = ""
    directory: str = "/xml/clients"
    run_time: str = "23:59"
    retry_minutes: int = Field(30, ge=1, le=1440)
    max_attempts: int = Field(10, ge=1, le=100)


ENV_KEYS = {
    "host": "FTP_HOST", "port": "FTP_PORT", "user": "FTP_USER",
    "password": "FTP_PASSWORD", "directory": "FTP_DIRECTORY",
    "run_time": "FTP_RUN_TIME", "retry_minutes": "FTP_RETRY_MINUTES",
    "max_attempts": "FTP_MAX_ATTEMPTS",
}


def get_ftp_settings() -> FtpSettings:
    values = {field: os.getenv(key) for field, key in ENV_KEYS.items()}
    return FtpSettings(**{key: value for key, value in values.items() if value not in (None, "")})


def save_ftp_settings(values: dict) -> FtpSettings:
    current = get_ftp_settings().model_dump()
    for key, value in values.items():
        if key in current and not (key == "password" and value == ""):
            current[key] = value
    settings = FtpSettings(**current)
    env_path = Path(os.getenv("CLIENTS_ENV_FILE", ".env"))
    existing = env_path.read_text("utf-8").splitlines() if env_path.exists() else []
    replacements = {ENV_KEYS[key]: str(value) for key, value in settings.model_dump().items()}
    output, written = [], set()
    for line in existing:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in replacements:
            output.append(f"{key}={replacements[key]}")
            written.add(key)
        else:
            output.append(line)
    output.extend(f"{key}={value}" for key, value in replacements.items() if key not in written)
    env_path.write_text("\n".join(output) + "\n", "utf-8")
    for key, value in replacements.items():
        os.environ[key] = value
    return settings


def _set_state(**values) -> None:
    with _state_lock:
        _state.update(values)


def get_ftp_status() -> dict:
    with _state_lock:
        return dict(_state)


def mark_ftp_pending() -> None:
    _set_state(running=True, stage="Проверка подключения…", last_error=None)


def set_next_run(value: datetime | None) -> None:
    _set_state(next_run=value.isoformat() if value else None)


def _connect(settings: FtpSettings) -> tuple[FTP, str]:
    if not settings.host or not settings.user:
        raise ValueError("Параметры FTP не настроены")
    logger.info("FTP: подключение к %s:%s", settings.host, settings.port)
    ftp = FTP()
    ftp.connect(settings.host, settings.port, timeout=30)
    ftp.login(settings.user, settings.password)
    logger.info("FTP: авторизация успешна, пользователь=%s", settings.user)
    directory = settings.directory
    try:
        ftp.cwd(directory)
    except error_perm:
        if directory == "/xml/clients":
            directory = "/xml"
            ftp.cwd(directory)
            logger.warning("FTP: /xml/clients отсутствует, используется /xml")
        else:
            raise
    ftp.voidcmd("TYPE I")
    return ftp, directory


def select_xls_files(names: list[str]) -> list[str]:
    """Возвращает только необработанные XLS в стабильном последовательном порядке."""
    return sorted(
        name for name in names
        if Path(name).name.lower().endswith(".xls") and not Path(name).name.lower().startswith("error_")
    )


def test_connection() -> dict:
    started = monotonic()
    _set_state(connection_status="checking", stage="Проверка подключения…", last_error=None)
    ftp = None
    try:
        ftp, directory = _connect(get_ftp_settings())
        names = ftp.nlst()
        files = select_xls_files(names)
        now = datetime.utcnow().isoformat()
        _set_state(connection_status="connected", stage="Ожидание", last_successful_check=now, found_files=len(files))
        return {"status": "connected", "directory": directory, "found_files": len(files), "checked_at": now}
    except error_perm as error:
        full_error = traceback.format_exc()
        logger.exception("FTP: ошибка авторизации при проверке подключения")
        _set_state(connection_status="auth_error", stage="Ошибка авторизации", last_error=str(error))
        _record_event("Проверка FTP", 0, "Ошибка", started, error=full_error)
        raise
    except Exception as error:
        full_error = traceback.format_exc()
        logger.exception("FTP: ошибка проверки подключения")
        _set_state(connection_status="unavailable", stage="FTP недоступен", last_error=str(error))
        _record_event("Проверка FTP", 0, "Ошибка", started, error=full_error)
        raise
    finally:
        if ftp:
            try:
                ftp.quit()
            except Exception:
                ftp.close()


def _record_event(filename: str, size: int, status: str, started: float, result=None, error: str | None = None) -> None:
    with SessionLocal() as db:
        db.add(FtpImportEvent(
            file_name=filename, file_size=size, status=status,
            added_count=result.added if result else 0, updated_count=result.updated if result else 0,
            skipped_count=result.skipped if result else 0,
            duration_seconds=round(monotonic() - started), error=error,
        ))
        db.commit()


def _process_file(ftp: FTP, filename: str) -> bool:
    started = monotonic()
    size = 0
    try:
        try:
            size = ftp.size(filename) or 0
        except error_perm:
            # Некоторые FTP-серверы запрещают SIZE, целостность в этом случае
            # дополнительно подтверждается успешным завершением RETR.
            logger.warning("FTP: сервер не вернул размер файла %s", filename)
        _set_state(stage=f"Скачивание файла {filename}…")
        logger.info("FTP: скачивание %s, размер=%s", filename, size)
        with TemporaryDirectory(prefix="clients-ftp-") as directory:
            path = Path(directory) / Path(filename).name
            with path.open("wb") as target:
                ftp.retrbinary(f"RETR {filename}", target.write)
            downloaded = path.stat().st_size
            if size and downloaded != size:
                raise IOError(f"Файл скачан не полностью: ожидалось {size}, получено {downloaded}")
            _set_state(stage=f"Импорт файла {filename}…")
            logger.info("FTP: запуск импорта %s", filename)
            with SessionLocal() as db:
                result = import_files(db, [(Path(filename).name, path.read_bytes())])
            if result.errors:
                raise RuntimeError(f"Импорт завершён с ошибками: {result.errors}")
        ftp.delete(filename)
        logger.info("FTP: файл удалён после успешного импорта: %s", filename)
        _record_event(filename, size, "Успешно", started, result=result)
        return True
    except Exception:
        full_error = traceback.format_exc()
        logger.exception("FTP: ошибка обработки %s", filename)
        if not Path(filename).name.lower().startswith("error_"):
            source = Path(filename)
            failed_name = str(source.with_name(f"error_{source.name}")).replace("\\", "/")
            try:
                ftp.rename(filename, failed_name)
                logger.info("FTP: файл переименован %s -> %s", filename, failed_name)
            except Exception:
                logger.exception("FTP: не удалось переименовать %s", filename)
        _record_event(filename, size, "Ошибка", started, error=full_error)
        return False


def run_ftp_import(*, retry_when_empty: bool = False) -> dict:
    if not _run_lock.acquire(blocking=False):
        raise RuntimeError("Проверка FTP уже выполняется")
    settings = get_ftp_settings()
    _set_state(running=True, stage="Проверка подключения…", processed_files=0, successful_files=0, failed_files=0, last_error=None)
    try:
        for attempt in range(1, settings.max_attempts + 1):
            attempt_started = monotonic()
            ftp = None
            try:
                logger.info("FTP: попытка поиска %s/%s", attempt, settings.max_attempts)
                ftp, _ = _connect(settings)
                _set_state(connection_status="connected", last_successful_check=datetime.utcnow().isoformat(), stage="Поиск файлов…")
                names = ftp.nlst()
                files = select_xls_files(names)
                _set_state(found_files=len(files), stage=f"Найдено файлов: {len(files)}")
                logger.info("FTP: найдено XLS-файлов: %s", len(files))
                if files:
                    if not import_process_lock.acquire(blocking=False):
                        raise RuntimeError("Другой импорт уже выполняется")
                    success = failed = 0
                    try:
                        for index, filename in enumerate(files, start=1):
                            ok = _process_file(ftp, filename)
                            success += int(ok); failed += int(not ok)
                            _set_state(processed_files=index, successful_files=success, failed_files=failed)
                    finally:
                        import_process_lock.release()
                    if success:
                        _set_state(last_successful_import=datetime.utcnow().isoformat())
                    return {"processed_files": len(files), "successful_files": success, "failed_files": failed}
                _record_event(
                    "Проверка FTP", 0, "Ожидание", attempt_started,
                    error=f"XLS-файлы не найдены. Попытка {attempt}/{settings.max_attempts}.",
                )
            except Exception as error:
                full_error = traceback.format_exc()
                logger.exception("FTP: ошибка попытки %s", attempt)
                connection_status = "auth_error" if isinstance(error, error_perm) and str(error).startswith("530") else "unavailable"
                _set_state(connection_status=connection_status, last_error=full_error)
                _record_event("Проверка FTP", 0, "Ошибка", attempt_started, error=full_error)
            finally:
                if ftp:
                    try:
                        ftp.quit()
                    except Exception:
                        ftp.close()
            if not retry_when_empty or attempt == settings.max_attempts:
                break
            _set_state(stage=f"Файлы не найдены. Попытка {attempt}/{settings.max_attempts}; ожидание {settings.retry_minutes} мин.")
            sleep(settings.retry_minutes * 60)
        return {"processed_files": 0, "successful_files": 0, "failed_files": 0}
    finally:
        _set_state(running=False, stage="Готово")
        _run_lock.release()
