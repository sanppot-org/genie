"""Tests for PriceRepository."""

from datetime import UTC, datetime

from src.database.models import PriceData
from src.database.repositories import PriceRepository


def test_save_price(price_repo: PriceRepository) -> None:
    """가격 데이터 저장 테스트"""
    # Given
    timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    price_data = PriceData(
        timestamp=timestamp,
        symbol="USD-KRW",
        price=1300.5,
        source="yfinance",
    )

    # When
    saved = price_repo.save(price_data)

    # Then
    assert saved.id is not None
    assert saved.symbol == "USD-KRW"
    assert saved.price == 1300.5
    assert saved.source == "yfinance"
    # SQLite는 timezone 정보를 저장하지 않으므로 naive datetime으로 비교
    assert saved.timestamp.replace(tzinfo=UTC) == timestamp


def test_save_price_duplicate_updates(price_repo: PriceRepository) -> None:
    """중복 가격 저장시 업데이트 테스트"""
    # Given
    timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    # 첫 번째 저장
    first = price_repo.save(
        PriceData(
            timestamp=timestamp,
            symbol="USD-KRW",
            price=1300.0,
            source="yfinance",
        )
    )

    # When - 같은 timestamp, symbol, source로 다시 저장
    second = price_repo.save(
        PriceData(
            timestamp=timestamp,
            symbol="USD-KRW",
            price=1305.0,  # 다른 값
            source="yfinance",
        )
    )

    # Then - ID는 같고 값만 업데이트
    assert first.id == second.id
    assert second.price == 1305.0


def test_get_latest_price(price_repo: PriceRepository) -> None:
    """최신 가격 조회 테스트"""
    # Given - 여러 시간대 가격 저장
    for hour in [10, 11, 12]:
        price_repo.save(
            PriceData(
                timestamp=datetime(2024, 1, 1, hour, 0, 0, tzinfo=UTC),
                symbol="USD-KRW",
                price=1300.0 + hour,
                source="yfinance",
            )
        )

    # When
    latest = price_repo.get_latest_price(symbol="USD-KRW", source="yfinance")

    # Then - 12시 가격이 최신
    assert latest is not None
    assert latest.timestamp.hour == 12
    assert latest.price == 1312.0


def test_get_latest_price_not_found(price_repo: PriceRepository) -> None:
    """존재하지 않는 가격 조회 테스트"""
    # When
    latest = price_repo.get_latest_price(symbol="GOLD-KRW", source="hantu")

    # Then
    assert latest is None


def test_get_price_history(price_repo: PriceRepository) -> None:
    """기간별 가격 이력 조회 테스트"""
    # Given - 24시간 데이터 저장
    for hour in range(24):
        price_repo.save(
            PriceData(
                timestamp=datetime(2024, 1, 1, hour, 0, 0, tzinfo=UTC),
                symbol="USD-KRW",
                price=1300.0 + hour,
                source="yfinance",
            )
        )

    # When - 10시~15시 조회
    history = price_repo.get_price_history(
        symbol="USD-KRW",
        start_date=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        end_date=datetime(2024, 1, 1, 15, 0, 0, tzinfo=UTC),
    )

    # Then
    assert len(history) == 6  # 10, 11, 12, 13, 14, 15시 (6개)
    assert history[0].timestamp.hour == 10
    assert history[-1].timestamp.hour == 15


def test_get_price_history_with_source_filter(price_repo: PriceRepository) -> None:
    """소스 필터링 가격 이력 조회 테스트"""
    # Given - 같은 시간에 다른 소스 데이터 저장
    timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    price_repo.save(
        PriceData(
            timestamp=timestamp,
            symbol="GOLD-KRW",
            price=80000.0,
            source="hantu",
        )
    )

    price_repo.save(
        PriceData(
            timestamp=timestamp,
            symbol="GOLD-KRW",
            price=78000.0,
            source="fdr",
        )
    )

    # When - hantu 소스만 조회
    history = price_repo.get_price_history(
        symbol="GOLD-KRW",
        start_date=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        end_date=datetime(2024, 1, 1, 23, 59, 59, tzinfo=UTC),
        source="hantu",
    )

    # Then - hantu 데이터만 조회됨
    assert len(history) == 1
    assert history[0].source == "hantu"
    assert history[0].price == 80000.0


def test_get_price_history_without_source_filter(price_repo: PriceRepository) -> None:
    """소스 필터 없이 모든 가격 이력 조회 테스트"""
    # Given - 같은 시간에 다른 소스 데이터 저장
    timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    price_repo.save(
        PriceData(
            timestamp=timestamp,
            symbol="GOLD-KRW",
            price=80000.0,
            source="hantu",
        )
    )

    price_repo.save(
        PriceData(
            timestamp=timestamp,
            symbol="GOLD-KRW",
            price=78000.0,
            source="fdr",
        )
    )

    # When - 소스 필터 없이 조회
    history = price_repo.get_price_history(
        symbol="GOLD-KRW",
        start_date=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        end_date=datetime(2024, 1, 1, 23, 59, 59, tzinfo=UTC),
    )

    # Then - 모든 소스 데이터 조회됨
    assert len(history) == 2
    sources = {price.source for price in history}
    assert sources == {"hantu", "fdr"}
