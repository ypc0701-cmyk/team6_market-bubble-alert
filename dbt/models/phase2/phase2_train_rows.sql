{{ config(materialized='view') }}

-- Phase 2 training-only rows.
-- The upstream view already excludes our original speculative basket.
-- Validation and test rows must never enter model training.

select
    label_drop_20pct_60d,
    drawdown_252,
    ret_20d,
    ret_60d,
    ret_120d,
    vol_60d,
    volume_ratio_60d,
    beta_spx_120d,
    beta_arkk_120d,
    days_listed_capped,
    spx_distance,
    credit_distance,
    universe_breadth

from {{ ref('phase2_training_input') }}

where split = 'train'
