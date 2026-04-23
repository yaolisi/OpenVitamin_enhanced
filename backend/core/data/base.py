"""
数据库连接与 Session 管理
优化并发控制：
1. WAL 模式支持更好的并发读写
2. 忙时重试机制
3. 超时控制
4. 线程安全配置
"""
from pathlib import Path
from typing import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.exc import OperationalError

from config.settings import settings
from log import logger

Base = declarative_base()
metadata = MetaData()


def get_db_path() -> Path:
    """获取数据库路径"""
    if settings.db_path:
        return Path(settings.db_path)
    root = Path(__file__).resolve().parents[3]
    return root / "backend" / "data" / "platform.db"


def get_database_url() -> str:
    """获取数据库 URL：优先使用 database_url（可切 PostgreSQL），否则回落 SQLite 文件。"""
    raw = (getattr(settings, "database_url", "") or "").strip()
    if raw:
        return raw
    db_path = get_db_path()
    return f"sqlite:///{db_path}"


def _is_sqlite_url(db_url: str) -> bool:
    return db_url.startswith("sqlite:")


def _ensure_common_indexes(engine: Engine) -> None:
    """为高频查询补齐索引（兼容存量库）。"""
    statements = [
        "CREATE INDEX IF NOT EXISTS idx_agent_sessions_user_created ON agent_sessions (user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow_created ON workflow_executions (workflow_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_workflow_executions_state_created ON workflow_executions (state, created_at)",
    ]
    try:
        with engine.connect() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
            conn.commit()
    except Exception as e:
        logger.warning(f"[Data] Failed to ensure common indexes: {e}")


def create_engine_instance() -> Engine:
    """创建数据库引擎（优化并发配置）"""
    db_url = get_database_url()
    connect_args = {}
    if _is_sqlite_url(db_url):
        db_path = get_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connect_args = {
            "check_same_thread": False,  # 允许多线程访问
            "timeout": 30.0,  # 锁等待超时（秒）
        }

    engine = create_engine(
        db_url,
        connect_args=connect_args,
        echo=False,
        pool_pre_ping=True,  # 连接前健康检查
        pool_recycle=max(60, int(getattr(settings, "db_pool_recycle_seconds", 1800))),
        max_overflow=max(0, int(getattr(settings, "db_max_overflow", 20))),
        pool_size=max(1, int(getattr(settings, "db_pool_size", 10))),
    )

    if _is_sqlite_url(db_url):
        # 启用 WAL 模式以提升并发性能
        try:
            with engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.execute(text("PRAGMA synchronous=NORMAL"))
                conn.execute(text("PRAGMA busy_timeout=30000"))  # 30 秒忙等待
                conn.execute(text("PRAGMA cache_size=-64000"))  # 64MB 缓存
                conn.commit()
            logger.info("[Data] SQLite concurrency optimizations enabled (WAL mode)")
        except Exception as e:
            logger.warning(f"[Data] Failed to enable WAL mode: {e}")

    _ensure_common_indexes(engine)
    return engine


_engine = create_engine_instance()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=_engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话（依赖注入）。用法：FastAPI Depends(get_db)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session(retry_count: int = 3, retry_delay: float = 0.1) -> Iterator[Session]:
    """
    获取数据库会话（非 FastAPI，带重试机制）
    
    Args:
        retry_count: 重试次数（遇到 OperationalError 时）
        retry_delay: 重试延迟（秒）
    
    Usage:
        with db_session() as db:
            # 执行数据库操作
            pass
    """
    # 注意：@contextmanager 只能 yield 一次。旧实现的 while-retry 会在 commit 失败后再次 yield，
    # 导致 "generator didn't stop"。这里改为单次事务，依赖 SQLite busy_timeout/WAL 处理锁等待。
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except OperationalError as e:
        logger.error(f"[Data] Database operational error: {e}")
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"[Data] Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """初始化数据库（创建所有已注册的 ORM 表）"""
    Base.metadata.create_all(bind=_engine)
    logger.info("[Data] Database tables created")


def get_engine() -> Engine:
    """获取引擎（用于 Alembic、迁移脚本等）"""
    return _engine
