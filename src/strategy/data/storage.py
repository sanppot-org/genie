"""데이터 저장소

HalfDayCandle 데이터를 JSON 파일로 저장하고 로드합니다.
"""

import json
import logging
from pathlib import Path

import constants
from config import PROJECT_ROOT
from src.strategy.data.models import HalfDayCandle

logger = logging.getLogger(__name__)

base_filepath = str(PROJECT_ROOT / 'data' / 'candles') + '/'


def save(candles: list[HalfDayCandle], filename: str) -> None:
    """
    HalfDayCandle 리스트를 JSON 파일로 저장

    Args:
        candles: 저장할 HalfDayCandle 리스트
        filename: 저장할 파일명
    """
    filepath = base_filepath + filename

    try:
        # 디렉토리가 없으면 생성
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        # JSON 형태로 변환
        data = [candle.to_dict() for candle in candles]

        # 파일에 저장
        with open(filepath, 'w', encoding=constants.UTF_8) as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"데이터 저장 실패: {filepath}")
        raise


def load(filename: str) -> list[HalfDayCandle]:
    """
    JSON 파일에서 HalfDayCandle 리스트 로드

    Args:
        filename: 로드할 파일명

    Returns:
        HalfDayCandle 리스트, 실패 시 빈 리스트
    """
    filepath = base_filepath + filename

    try:
        # 파일이 없으면 빈 리스트 반환
        if not Path(filepath).exists():
            logger.warning(f"파일이 존재하지 않음: {filepath}")
            return []

        # 파일에서 읽기
        with open(filepath, 'r', encoding=constants.UTF_8) as f:
            data = json.load(f)

        # HalfDayCandle 객체로 변환
        candles = [HalfDayCandle.from_dict(item) for item in data]

        logger.info(f"데이터 로드 완료: {filepath} ({len(candles)}개)")
        return candles

    except json.JSONDecodeError:
        logger.exception(f"JSON 파싱 실패: {filepath}")
        return []

    except Exception as e:
        logger.exception(f"데이터 로드 실패: {filepath}")
        return []


def append_and_keep_last(
        new_candles: list[HalfDayCandle],
        filename: str
) -> None:
    """
    새 데이터를 추가하고 최신 N개만 유지 (Rolling Window)

    기존 데이터를 로드하고 새 데이터를 추가한 후,
    최신 max_count개만 유지하여 저장합니다.

    Args:
        new_candles: 추가할 HalfDayCandle 리스트
        filename: 저장할 파일명
    """
    filepath = base_filepath + filename

    # 기존 데이터 로드
    existing = load(filepath)

    # 새 데이터 추가
    all_candles = existing + new_candles

    # 저장
    save(all_candles, filepath)

    logger.info(
        f"Rolling Window 저장 완료: "
        f"기존 {len(existing)}개 + 신규 {len(new_candles)}개 "
        f"→ 최신 {len(all_candles)}개 유지"
    )
