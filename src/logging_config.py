"""
로깅 설정 모듈

Better Stack (Logtail)과 로컬 로깅을 함께 설정합니다.
"""

import atexit
import logging
import sys

from src.config import LogtailConfig

# Better Stack 핸들러 저장 (flush용)
_logtail_handler = None


def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    """
    로깅 시스템 설정

    Args:
        log_level: 로그 레벨 (기본: INFO)

    Returns:
        설정된 루트 로거
    """
    global _logtail_handler

    # 루트 로거 가져오기
    root_logger = logging.getLogger()

    # 이미 설정되어 있으면 중복 설정 방지
    if root_logger.handlers:
        return root_logger

    root_logger.setLevel(log_level)

    # 기본 포맷터 (로컬 로깅용)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 콘솔 핸들러 (로컬 로깅)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Better Stack (Logtail) 핸들러 (선택적)
    try:
        config = LogtailConfig()
        if config.logtail_source_token:
            from logtail import LogtailHandler  # type: ignore[import-untyped]

            # LogtailHandler는 기본 host='in.logs.betterstack.com'를 사용
            _logtail_handler = LogtailHandler(
                source_token=config.logtail_source_token,
                host=config.logtail_source_host,
            )
            _logtail_handler.setLevel(log_level)
            root_logger.addHandler(_logtail_handler)

            # 프로그램 종료 시 자동으로 flush
            atexit.register(flush_logs)

            root_logger.info("✅ Better Stack 로깅 활성화됨")
        else:
            root_logger.info("ℹ️  Better Stack 토큰 없음 - 로컬 로깅만 사용")
    except Exception as e:
        # Better Stack 설정 실패해도 로컬 로깅은 계속 동작
        root_logger.warning(f"⚠️  Better Stack 설정 실패 (로컬 로깅만 사용): {e}")

    return root_logger


def flush_logs() -> None:
    """
    Better Stack으로 모든 로그를 즉시 전송

    프로그램 종료 시 자동으로 호출됩니다.
    수동으로 호출하여 즉시 로그를 전송할 수도 있습니다.
    """
    global _logtail_handler

    if _logtail_handler:
        try:
            _logtail_handler.flush()
        except Exception:
            pass  # 종료 시 에러 무시
