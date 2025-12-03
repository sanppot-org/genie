-- TimescaleDB 초기화 스크립트

-- TimescaleDB 확장 활성화
CREATE
EXTENSION IF NOT EXISTS timescaledb;

-- 기본 테이블 생성은 SQLAlchemy가 수행
-- 하이퍼테이블 변환은 애플리케이션 시작 후 수동 또는 마이그레이션으로 처리

-- 예시: 캔들 데이터 하이퍼테이블 변환 (테이블 생성 후 실행)
-- SELECT create_hypertable('candle_data', 'timestamp', if_not_exists => TRUE);

-- 압축 정책 설정 (선택사항)
-- ALTER TABLE candle_data SET (
--     timescaledb.compress,
--     timescaledb.compress_segmentby = 'ticker, interval',
--     timescaledb.compress_orderby = 'timestamp DESC'
-- );

-- 7일 이전 데이터 자동 압축 (선택사항)
-- SELECT add_compression_policy('candle_data', INTERVAL '7 days', if_not_exists => TRUE);

-- 데이터 보관 정책 (선택사항)
-- 1년 이전 데이터 자동 삭제
-- SELECT add_retention_policy('candle_data', INTERVAL '1 year', if_not_exists => TRUE);

-- 연속 집계 (Continuous Aggregates) 예시
-- 1시간봉을 1일봉으로 자동 집계
-- CREATE MATERIALIZED VIEW candle_data_daily
-- WITH (timescaledb.continuous) AS
-- SELECT
--     time_bucket('1 day', timestamp) AS day,
--     ticker,
--     first(open, timestamp) AS open,
--     max(high) AS high,
--     min(low) AS low,
--     last(close, timestamp) AS close,
--     sum(volume) AS volume
-- FROM candle_data
-- WHERE interval = '1h'
-- GROUP BY day, ticker;

-- 자동 갱신 정책
-- SELECT add_continuous_aggregate_policy('candle_data_daily',
--     start_offset => INTERVAL '3 days',
--     end_offset => INTERVAL '1 hour',
--     schedule_interval => INTERVAL '1 hour');

-- 초기화 완료 메시지
DO
$$
BEGIN
    RAISE
NOTICE 'TimescaleDB initialized successfully!';
    RAISE
NOTICE 'Run hypertable conversion after table creation.';
END $$;
