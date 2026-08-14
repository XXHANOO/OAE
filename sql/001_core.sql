CREATE SCHEMA IF NOT EXISTS meta;
CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE meta.raw_file_manifest (
    raw_file_id VARCHAR PRIMARY KEY,
    source VARCHAR NOT NULL,
    source_file_name VARCHAR NOT NULL,
    ingested_at_utc TIMESTAMPTZ NOT NULL,
    sha256 VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    min_event_ts TIMESTAMPTZ,
    max_event_ts TIMESTAMPTZ,
    row_count BIGINT NOT NULL
);

CREATE TABLE core.trading_sessions (
    session_date_et DATE PRIMARY KEY,
    session_seq INTEGER NOT NULL,
    open_ts_utc TIMESTAMPTZ NOT NULL,
    regular_close_ts_utc TIMESTAMPTZ NOT NULL,
    is_trading_day BOOLEAN NOT NULL,
    is_full_session BOOLEAN NOT NULL,
    is_half_day BOOLEAN NOT NULL,
    xsp_0dte_exists BOOLEAN NOT NULL
);

CREATE TABLE core.index_bars_1m (
    symbol VARCHAR NOT NULL,
    session_date_et DATE NOT NULL,
    bar_start_ts_utc TIMESTAMPTZ NOT NULL,
    bar_end_ts_utc TIMESTAMPTZ NOT NULL,
    open DECIMAL(18,6) NOT NULL,
    high DECIMAL(18,6) NOT NULL,
    low DECIMAL(18,6) NOT NULL,
    close DECIMAL(18,6) NOT NULL,
    observation_count INTEGER NOT NULL,
    source VARCHAR NOT NULL,
    raw_file_id VARCHAR NOT NULL,
    quality_status VARCHAR NOT NULL,

    PRIMARY KEY(symbol, bar_end_ts_utc)
);

CREATE TABLE core.option_contracts (
    contract_id VARCHAR PRIMARY KEY,
    vendor_symbol VARCHAR NOT NULL,
    product VARCHAR NOT NULL,
    root_symbol VARCHAR NOT NULL,
    underlying VARCHAR NOT NULL,
    option_type VARCHAR NOT NULL CHECK(option_type IN ('C','P')),
    strike DECIMAL(18,4) NOT NULL,
    expiration_date DATE NOT NULL,
    settlement_style VARCHAR NOT NULL CHECK(settlement_style IN ('AM','PM')),
    exercise_style VARCHAR NOT NULL,
    multiplier INTEGER NOT NULL,
    series_type VARCHAR,
    expiration_ts_utc TIMESTAMPTZ NOT NULL,
    first_seen_date DATE NOT NULL,
    last_seen_date DATE NOT NULL,
    source VARCHAR NOT NULL
);

CREATE TABLE core.option_nbbo (
    contract_id VARCHAR NOT NULL,
    quote_ts_utc TIMESTAMPTZ NOT NULL,
    session_date_et DATE NOT NULL,
    bid_px DECIMAL(18,6) NOT NULL,
    ask_px DECIMAL(18,6) NOT NULL,
    bid_size INTEGER NOT NULL,
    ask_size INTEGER NOT NULL,
    bid_exchange VARCHAR,
    ask_exchange VARCHAR,
    quote_condition VARCHAR,
    sequence_no BIGINT,
    source VARCHAR NOT NULL,
    raw_file_id VARCHAR NOT NULL
);

CREATE TABLE core.option_settlements (
    product VARCHAR NOT NULL,
    expiration_date DATE NOT NULL,
    settlement_style VARCHAR NOT NULL,
    settlement_value DECIMAL(18,6) NOT NULL,
    effective_ts_utc TIMESTAMPTZ NOT NULL,
    published_ts_utc TIMESTAMPTZ,
    source VARCHAR NOT NULL,
    raw_file_id VARCHAR NOT NULL,

    PRIMARY KEY(product, expiration_date, settlement_style)
);
