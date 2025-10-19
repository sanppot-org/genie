import logging
from pathlib import Path

from pydantic import BaseModel

from src import constants
from src.strategy.cache_models import DataCache, StrategyCache

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = ".cache"
DEFAULT_CACHE_FILE_NAME = "cache.json"


class CacheManager:
    """캐시를 파일로 저장하고 로드하는 범용 클래스

    DataCache와 StrategyCache를 구분하여 저장할 수 있습니다.
    """

    def __init__(self, cache_dir: str = DEFAULT_CACHE_DIR, file_suffix: str = "") -> None:
        """
        Args:
            cache_dir: 캐시 파일을 저장할 디렉토리 경로 (기본값: .cache)
            file_suffix: 파일명에 추가할 접미사 (예: "data", "strategy")
                        비어있으면 {ticker}_cache.json
                        있으면 {ticker}_{suffix}_cache.json
        """
        self._cache_dir = Path(cache_dir)
        self._file_suffix = file_suffix

    def get_cache_path(self, ticker: str) -> Path:
        """
        특정 ticker의 캐시 파일 경로를 반환

        Args:
            ticker: 종목 코드 (예: KRW-BTC)

        Returns:
            캐시 파일의 Path 객체
        """
        if self._file_suffix:
            filename = f"{ticker}_{self._file_suffix}_{DEFAULT_CACHE_FILE_NAME}"
        else:
            filename = f"{ticker}_{DEFAULT_CACHE_FILE_NAME}"
        return self._cache_dir / filename

    def _save_cache(self, ticker: str, cache: BaseModel) -> None:
        """
        캐시를 JSON 파일로 저장

        Args:
            ticker: 종목 코드
            cache: 저장할 캐시 객체 (DataCache 또는 StrategyCache)
        """
        # 디렉토리가 없으면 생성
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # 파일 경로 생성
        cache_path = self.get_cache_path(ticker)

        # JSON으로 직렬화하여 저장
        json_data = cache.model_dump_json(indent=2)
        cache_path.write_text(json_data, encoding=constants.UTF_8)

        logger.debug(f"캐시 저장 완료: {cache_path}")

    def _load_cache(self, ticker: str, model_class: type[BaseModel]) -> BaseModel | None:
        """
        JSON 파일에서 캐시를 로드

        Args:
            ticker: 종목 코드
            model_class: 로드할 캐시 모델 클래스 (DataCache 또는 StrategyCache)

        Returns:
            캐시 객체, 파일이 없으면 None
        """
        cache_path = self.get_cache_path(ticker)

        # 파일이 없으면 None 반환
        if not cache_path.exists():
            logger.debug(f"캐시 파일 없음: {cache_path}")
            return None

        try:
            # JSON 파일 읽기
            json_data = cache_path.read_text(encoding=constants.UTF_8)

            # Pydantic 모델로 역직렬화
            cache = model_class.model_validate_json(json_data)

            logger.debug(f"캐시 로드 완료: {cache_path}")
            return cache

        except Exception as e:
            logger.warning(f"캐시 로드 실패: {cache_path}, 에러: {e}")
            return None

    def save_data_cache(self, ticker: str, cache: DataCache) -> None:
        """
        DataCache를 JSON 파일로 저장

        Args:
            ticker: 종목 코드
            cache: 저장할 DataCache 객체
        """
        self._save_cache(ticker, cache)

    def load_data_cache(self, ticker: str) -> DataCache | None:
        """
        JSON 파일에서 DataCache를 로드

        Args:
            ticker: 종목 코드

        Returns:
            DataCache 객체, 파일이 없으면 None
        """
        return self._load_cache(ticker, DataCache)

    def save_strategy_cache(self, ticker: str, cache: StrategyCache) -> None:
        """
        StrategyCache를 JSON 파일로 저장

        Args:
            ticker: 종목 코드
            cache: 저장할 StrategyCache 객체
        """
        self._save_cache(ticker, cache)

    def load_strategy_cache(self, ticker: str) -> StrategyCache | None:
        """
        JSON 파일에서 StrategyCache를 로드

        Args:
            ticker: 종목 코드

        Returns:
            StrategyCache 객체, 파일이 없으면 None
        """
        return self._load_cache(ticker, StrategyCache)
