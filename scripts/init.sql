-- genie 데이터베이스 초기화 스크립트

-- 데이터베이스 생성은 POSTGRES_DB 환경변수로 자동 생성됨

-- 확장 기능 활성화 (선택사항)
-- CREATE EXTENSION IF NOT EXISTS pg_stat_statements;  -- 쿼리 성능 분석
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- 텍스트 검색 최적화

-- 기본 테이블 생성 (SQLAlchemy가 자동 생성하므로 주석 처리)
-- 필요시 여기에 추가 설정

-- 인덱스 최적화 설정
-- ALTER TABLE candle_data SET (fillfactor = 90);  -- 업데이트가 많을 때 유용

-- 시간대 설정 확인
SELECT current_setting('TIMEZONE') as timezone;

-- 초기화 완료 메시지
DO
$$
BEGIN
    RAISE
NOTICE 'Genie trading database initialized successfully!';
END $$;
