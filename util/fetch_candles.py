#!/usr/bin/env python3
"""
pyupbit를 이용해서 2017-10-01 8시부터 현재까지 60분봉 데이터를 수집하여 CSV로 저장하는 스크립트
"""
from datetime import datetime

import pyupbit


def fetch_and_save_candles(
        ticker: str = "KRW-BTC",
        interval: str = "minute60"
) -> None:
    """
    지정된 티커의 60분봉 데이터를 수집하여 CSV로 저장

    Args:
        ticker: 암호화폐 티커 (기본값: KRW-BTC)
        interval: 캔들 간격 (기본값: minute60)
        output_file: 저장할 CSV 파일명
    """
    print(f"📊 {ticker} 60분봉 데이터 수집 시작...")
    print("🕐 시작 시간: 2017-10-01 08:00")
    print(f"🕐 종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 2017-10-01부터 현재까지 약 8년 = 약 70,000시간
    # 여유있게 80,000개 요청
    count = 100000

    print(f"🔄 데이터 수집 중... (최대 {count}개 캔들)")
    df = pyupbit.get_ohlcv(ticker=ticker, interval=interval, count=count)

    if df is None or df.empty:
        print("❌ 데이터를 가져오지 못했습니다.")
        return

    start_date = df.index[0].strftime('%Y-%m-%d')
    end_date = df.index[-1].strftime('%Y-%m-%d')
    output_file = f"{ticker}_{interval}_candles_{start_date}_{end_date}.csv"

    # CSV로 저장
    df.to_csv(output_file)

    print("✅ 완료!")
    print(f"📁 저장 위치: {output_file}")
    print(f"📊 수집된 데이터: {len(df)}개 캔들")
    print(f"📅 기간: {df.index[0]} ~ {df.index[-1]}")
    print("\n데이터 미리보기:")
    print(df.head())
    print(f"\n컬럼: {list(df.columns)}")


if __name__ == "__main__":
    fetch_and_save_candles(ticker="KRW-TRON")
