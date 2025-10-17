"""데이터 저장소

Recent20DaysHalfDayCandles 데이터를 JSON 파일로 저장하고 로드합니다.
시그널 데이터를 JSON 파일로 저장하고 로드합니다.
"""

import json
import logging
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from src import constants
from src.config import PROJECT_ROOT
from src.strategy.data.models import HalfDayCandle, Recent20DaysHalfDayCandles

logger = logging.getLogger(__name__)

base_filepath = str(PROJECT_ROOT / "data" / "candles") + "/"

T = TypeVar("T", bound=BaseModel)


def save(candles: Recent20DaysHalfDayCandles, filename: str) -> None:
    """
    Recent20DaysHalfDayCandles를 JSON 파일로 저장

    Args:
        candles: 저장할 Recent20DaysHalfDayCandles 객체
        filename: 저장할 파일명
    """
    filepath = base_filepath + filename

    try:
        # 디렉토리가 없으면 생성
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        # JSON 형태로 변환
        data = [candle.to_dict() for candle in candles.candles]

        # 파일에 저장
        with open(filepath, "w", encoding=constants.UTF_8) as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    except Exception:
        logger.exception(f"데이터 저장 실패: {filepath}")
        raise


def load(filename: str) -> Recent20DaysHalfDayCandles | None:
    """
    JSON 파일에서 Recent20DaysHalfDayCandles 로드

    Args:
        filename: 로드할 파일명

    Returns:
        Recent20DaysHalfDayCandles 객체 (40개), 실패 시 또는 40개가 아니면 None
    """
    filepath = base_filepath + filename

    try:
        # 파일이 없으면 None 반환
        if not Path(filepath).exists():
            logger.warning(f"파일이 존재하지 않음: {filepath}")
            return None

        # 파일에서 읽기
        with open(filepath, encoding=constants.UTF_8) as f:
            data = json.load(f)

        # HalfDayCandle 객체로 변환
        candles = [HalfDayCandle.from_dict(item) for item in data]

        # 40개가 아니면 None 반환
        if len(candles) != 40:
            logger.warning(f"데이터 개수 불일치: {filepath} ({len(candles)}개, 40개 필요)")
            return None

        logger.info(f"데이터 로드 완료: {filepath} ({len(candles)}개)")
        return Recent20DaysHalfDayCandles(candles=candles)

    except json.JSONDecodeError:
        logger.exception(f"JSON 파싱 실패: {filepath}")
        return None

    except Exception:
        logger.exception(f"데이터 로드 실패: {filepath}")
        return None


def save_signal(signal: BaseModel, filename: str, base_dir: str = "signals") -> None:
    """
    시그널을 JSON 파일로 저장

    Args:
        signal: 저장할 시그널 객체 (Pydantic BaseModel)
        filename: 저장할 파일명
        base_dir: 기본 디렉토리 (data/ 하위, 기본값: 'signals')
    """
    filepath = str(PROJECT_ROOT / "data" / base_dir / filename)

    try:
        # 디렉토리가 없으면 생성
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        # JSON 형태로 변환
        data = signal.model_dump(mode="json")

        # 파일에 저장
        with open(filepath, "w", encoding=constants.UTF_8) as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    except Exception:
        logger.exception(f"시그널 저장 실패: {filepath}")
        raise


def load_signal[T: BaseModel](model_class: type[T], filename: str, base_dir: str = "signals") -> T | None:
    """
    JSON 파일에서 시그널 로드

    Args:
        model_class: 시그널 모델 클래스 (Pydantic BaseModel)
        filename: 로드할 파일명
        base_dir: 기본 디렉토리 (data/ 하위, 기본값: 'signals')

    Returns:
        시그널 객체, 실패 시 None
    """
    filepath = str(PROJECT_ROOT / "data" / base_dir / filename)

    try:
        # 파일이 없으면 None 반환
        if not Path(filepath).exists():
            logger.warning(f"파일이 존재하지 않음: {filepath}")
            return None

        # 파일에서 읽기
        with open(filepath, encoding=constants.UTF_8) as f:
            data = json.load(f)

        # 모델 객체로 변환
        signal = model_class.model_validate(data)
        logger.info(f"시그널 로드 완료: {filepath}")
        return signal

    except json.JSONDecodeError:
        logger.exception(f"JSON 파싱 실패: {filepath}")
        return None

    except ValidationError:
        logger.exception(f"데이터 검증 실패: {filepath}")
        return None

    except Exception:
        logger.exception(f"시그널 로드 실패: {filepath}")
        return None
