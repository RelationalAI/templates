CREATE SCHEMA IF NOT EXISTS BERTOLANI.TELCO_PLAN_EVALUATION;

CREATE OR REPLACE TABLE BERTOLANI.TELCO_PLAN_EVALUATION.CANDIDATE_UPGRADES AS
WITH
raw_perf AS (
  SELECT
    tower_id,
    AVG(latency_ms) AS avg_latency_ms,
    AVG(packet_loss_pct) AS avg_packet_loss_pct,
    AVG(bandwidth_utilization_pct) AS avg_bandwidth_utilization_pct,
    AVG(error_rate) AS avg_error_rate,
    AVG(active_connections) AS avg_active_connections
  FROM BERTOLANI.TELCO_DEMO_COCO.NETWORK_PERFORMANCE
  GROUP BY tower_id
),
raw_calls AS (
  SELECT
    tower_id,
    COUNT(*) AS call_count,
    COUNT(DISTINCT caller_sub_id) + COUNT(DISTINCT callee_sub_id) AS subscriber_touch_count,
    AVG(call_quality_score) AS avg_call_quality_score
  FROM BERTOLANI.TELCO_DEMO_COCO.CALL_DETAIL_RECORDS
  GROUP BY tower_id
),
raw_equip AS (
  SELECT
    ne.tower_id,
    COUNT(*) AS equipment_count,
    AVG(eh.health_score) AS avg_equipment_health_score,
    AVG(eh.failure_rate) AS avg_equipment_failure_rate
  FROM BERTOLANI.TELCO_DEMO_COCO.NETWORK_EQUIPMENT ne
  LEFT JOIN BERTOLANI.TELCO_DEMO_COCO.EQUIPMENT_HEALTH eh
    ON ne.equipment_id = eh.equipment_id
  GROUP BY ne.tower_id
),
raw_options AS (
  SELECT
    tower_id,
    upgrade_tier,
    capacity_increase_gbps,
    cost_usd,
    install_weeks,
    ROW_NUMBER() OVER (
      PARTITION BY tower_id
      ORDER BY cost_usd, install_weeks, capacity_increase_gbps DESC
    ) AS option_rank
  FROM BERTOLANI.TELCO_DEMO_COCO.TOWER_UPGRADE_OPTIONS
),
raw_ranked AS (
  SELECT
    'COCO_RAW_HEURISTIC' AS plan_id,
    'COCO_RAW' AS plan_source,
    t.tower_id,
    o.upgrade_tier AS tier,
    t.region,
    o.capacity_increase_gbps,
    o.cost_usd,
    o.install_weeks,
    (
      CASE t.status WHEN 'DEGRADED' THEN 100 WHEN 'MAINTENANCE' THEN 40 ELSE 0 END
      + COALESCE(p.avg_latency_ms, 0) * 0.30
      + COALESCE(p.avg_packet_loss_pct, 0) * 8
      + (1 - COALESCE(e.avg_equipment_health_score, 0.5)) * 50
      + COALESCE(c.call_count, 0) * 0.02
    ) AS candidate_score,
    'Raw-table heuristic: status, latency, packet loss, equipment health, and call volume; cheapest valid tier per tower.' AS selection_reason
  FROM BERTOLANI.TELCO_DEMO_COCO.CELL_TOWERS t
  LEFT JOIN raw_perf p ON t.tower_id = p.tower_id
  LEFT JOIN raw_calls c ON t.tower_id = c.tower_id
  LEFT JOIN raw_equip e ON t.tower_id = e.tower_id
  JOIN raw_options o ON t.tower_id = o.tower_id AND o.option_rank = 1
),
raw_plan AS (
  SELECT *
  FROM (
    SELECT
      r.*,
      ROW_NUMBER() OVER (ORDER BY candidate_score DESC, tower_id) AS plan_rank,
      SUM(cost_usd) OVER (ORDER BY candidate_score DESC, tower_id) AS cumulative_cost,
      SUM(install_weeks) OVER (ORDER BY candidate_score DESC, tower_id) AS cumulative_install_weeks
    FROM raw_ranked r
  )
  WHERE cumulative_cost <= 5000000 AND cumulative_install_weeks <= 200
),
semantic_options AS (
  SELECT
    tower_id,
    upgrade_tier,
    capacity_increase_gbps,
    cost_usd,
    install_weeks,
    ROW_NUMBER() OVER (
      PARTITION BY tower_id
      ORDER BY cost_usd, install_weeks, capacity_increase_gbps DESC
    ) AS option_rank
  FROM BERTOLANI.TELCO_DEMO_SEMANTIC.TOWER_UPGRADE_OPTIONS
),
semantic_ranked AS (
  SELECT
    'COCO_SEMANTIC_HEURISTIC' AS plan_id,
    'COCO_SEMANTIC' AS plan_source,
    m.tower_id,
    o.upgrade_tier AS tier,
    m.region,
    o.capacity_increase_gbps,
    o.cost_usd,
    o.install_weeks,
    (
      COALESCE(m.avg_latency_ms, 0) * 0.35
      + COALESCE(m.avg_packet_loss_pct, 0) * 10
      + COALESCE(m.avg_bandwidth_utilization_pct, 0) * 0.40
      + COALESCE(m.subscriber_touch_count, 0) * 0.10
    ) AS candidate_score,
    'Source-only semantic heuristic: governed tower metrics ranked by latency, packet loss, utilization, and subscriber touches; cheapest valid tier per tower.' AS selection_reason
  FROM BERTOLANI.TELCO_DEMO_SEMANTIC.TELCO_SOURCE_TOWER_METRICS m
  JOIN semantic_options o ON m.tower_id = o.tower_id AND o.option_rank = 1
),
semantic_plan AS (
  SELECT *
  FROM (
    SELECT
      r.*,
      ROW_NUMBER() OVER (ORDER BY candidate_score DESC, tower_id) AS plan_rank,
      SUM(cost_usd) OVER (ORDER BY candidate_score DESC, tower_id) AS cumulative_cost,
      SUM(install_weeks) OVER (ORDER BY candidate_score DESC, tower_id) AS cumulative_install_weeks
    FROM semantic_ranked r
  )
  WHERE cumulative_cost <= 5000000 AND cumulative_install_weeks <= 200
),
rai_plan AS (
  SELECT
    'RAI_OPTIMAL' AS plan_id,
    'COCO_SEMANTIC_RAI' AS plan_source,
    tower_id,
    tier,
    region,
    capacity_gbps AS capacity_increase_gbps,
    cost AS cost_usd,
    install_weeks,
    capacity_gbps * failure_intensity * weighted_impact AS candidate_score,
    ROW_NUMBER() OVER (ORDER BY candidate_score DESC, tower_id) AS plan_rank,
    SUM(cost) OVER (ORDER BY candidate_score DESC, tower_id) AS cumulative_cost,
    SUM(install_weeks) OVER (ORDER BY candidate_score DESC, tower_id) AS cumulative_install_weeks,
    'RelationalAI optimal plan: selected by prescriptive optimization using predicted failure risk and graph-derived customer impact under budget and install-week constraints.' AS selection_reason
  FROM BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.SELECTED_UPGRADES
)
SELECT
  plan_id,
  plan_source,
  tower_id,
  tier,
  region,
  capacity_increase_gbps,
  cost_usd,
  install_weeks,
  candidate_score,
  plan_rank,
  cumulative_cost,
  cumulative_install_weeks,
  selection_reason
FROM raw_plan
UNION ALL
SELECT
  plan_id,
  plan_source,
  tower_id,
  tier,
  region,
  capacity_increase_gbps,
  cost_usd,
  install_weeks,
  candidate_score,
  plan_rank,
  cumulative_cost,
  cumulative_install_weeks,
  selection_reason
FROM semantic_plan
UNION ALL
SELECT
  plan_id,
  plan_source,
  tower_id,
  tier,
  region,
  capacity_increase_gbps,
  cost_usd,
  install_weeks,
  candidate_score,
  plan_rank,
  cumulative_cost,
  cumulative_install_weeks,
  selection_reason
FROM rai_plan;

CREATE OR REPLACE VIEW BERTOLANI.TELCO_PLAN_EVALUATION.CANDIDATE_UPGRADES_SCORED AS
SELECT
  c.plan_id,
  c.plan_source,
  c.plan_rank,
  c.tower_id,
  c.tier,
  c.region,
  c.capacity_increase_gbps,
  c.cost_usd,
  c.install_weeks,
  c.candidate_score AS source_candidate_score,
  COALESCE(f.failure_intensity, 0) AS failure_intensity,
  COALESCE(i.weighted_impact, 0) AS weighted_impact,
  COALESCE(i.impact_count, 0) AS impact_count,
  c.capacity_increase_gbps
    * COALESCE(f.failure_intensity, 0)
    * COALESCE(i.weighted_impact, 0) AS governed_objective_contribution,
  IFF(f.failure_intensity IS NOT NULL, TRUE, FALSE) AS has_predicted_failure_signal,
  IFF(i.weighted_impact IS NOT NULL, TRUE, FALSE) AS has_graph_customer_impact,
  c.selection_reason
FROM BERTOLANI.TELCO_PLAN_EVALUATION.CANDIDATE_UPGRADES c
LEFT JOIN BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.TOWER_FAILURE_SCORE f
  ON c.tower_id = f.tower_id
LEFT JOIN BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.TOWER_CUSTOMER_IMPACT i
  ON c.tower_id = i.tower_id;

CREATE OR REPLACE TABLE BERTOLANI.TELCO_PLAN_EVALUATION.PLAN_SCORECARD AS
WITH plan_scores AS (
  SELECT
    plan_id,
    plan_source,
    COUNT(*) AS towers_selected,
    SUM(cost_usd) AS total_cost_usd,
    SUM(install_weeks) AS total_install_weeks,
    SUM(capacity_increase_gbps) AS capacity_restored_gbps,
    COUNT_IF(tier = 'GOLD') AS gold_count,
    COUNT_IF(tier = 'SILVER') AS silver_count,
    COUNT_IF(tier = 'BRONZE') AS bronze_count,
    SUM(governed_objective_contribution) AS governed_objective_value,
    COUNT_IF(has_predicted_failure_signal) AS towers_with_failure_signal,
    COUNT_IF(has_graph_customer_impact) AS towers_with_customer_impact,
    COUNT_IF(NOT has_predicted_failure_signal OR NOT has_graph_customer_impact) AS towers_missing_reasoner_context
  FROM BERTOLANI.TELCO_PLAN_EVALUATION.CANDIDATE_UPGRADES_SCORED
  GROUP BY plan_id, plan_source
),
rai AS (
  SELECT governed_objective_value AS rai_objective
  FROM plan_scores
  WHERE plan_id = 'RAI_OPTIMAL'
)
SELECT
  p.*,
  ROUND(100 * p.governed_objective_value / NULLIF(r.rai_objective, 0), 2) AS pct_of_rai_objective,
  CASE
    WHEN p.towers_selected = 0 THEN 'INCOMPLETE'
    WHEN p.total_cost_usd > 5000000 OR p.total_install_weeks > 200 THEN 'INFEASIBLE'
    WHEN p.plan_id = 'RAI_OPTIMAL' THEN 'OPTIMAL'
    ELSE 'FEASIBLE_SUBOPTIMAL'
  END AS evaluation_status,
  CASE
    WHEN p.total_cost_usd >= 5000000 * 0.995 THEN 'budget'
    WHEN p.total_install_weeks >= 199 THEN 'install_weeks'
    ELSE 'none'
  END AS binding_constraint
FROM plan_scores p
CROSS JOIN rai r;

CREATE OR REPLACE TABLE BERTOLANI.TELCO_PLAN_EVALUATION.MISSED_RAI_TOWERS AS
SELECT
  p.plan_id,
  p.plan_source,
  r.tower_id,
  r.tier AS rai_tier,
  r.region,
  r.capacity_gbps AS rai_capacity_gbps,
  r.cost AS rai_cost_usd,
  r.install_weeks AS rai_install_weeks,
  r.failure_intensity,
  r.weighted_impact,
  r.capacity_gbps * r.failure_intensity * r.weighted_impact AS rai_objective_contribution
FROM (
  SELECT DISTINCT plan_id, plan_source
  FROM BERTOLANI.TELCO_PLAN_EVALUATION.CANDIDATE_UPGRADES
  WHERE plan_id <> 'RAI_OPTIMAL'
) p
CROSS JOIN BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.SELECTED_UPGRADES r
LEFT JOIN BERTOLANI.TELCO_PLAN_EVALUATION.CANDIDATE_UPGRADES c
  ON c.plan_id = p.plan_id
 AND c.tower_id = r.tower_id
WHERE c.tower_id IS NULL;

CREATE OR REPLACE TABLE BERTOLANI.TELCO_PLAN_EVALUATION.PLAN_EXPLANATIONS AS
WITH s AS (
  SELECT * FROM BERTOLANI.TELCO_PLAN_EVALUATION.PLAN_SCORECARD
),
missed AS (
  SELECT
    plan_id,
    COUNT(*) AS missed_rai_towers,
    SUM(rai_objective_contribution) AS missed_rai_objective_value,
    LISTAGG(tower_id, ', ') WITHIN GROUP (ORDER BY rai_objective_contribution DESC) AS missed_towers
  FROM (
    SELECT
      plan_id,
      tower_id,
      rai_objective_contribution,
      ROW_NUMBER() OVER (PARTITION BY plan_id ORDER BY rai_objective_contribution DESC) AS rn
    FROM BERTOLANI.TELCO_PLAN_EVALUATION.MISSED_RAI_TOWERS
  )
  WHERE rn <= 5
  GROUP BY plan_id
)
SELECT
  s.plan_id,
  s.plan_source,
  s.evaluation_status,
  CASE
    WHEN s.plan_id = 'RAI_OPTIMAL' THEN
      'Optimal governed plan: uses prediction, graph impact, rules, and prescriptive optimization to maximize governed objective under the budget and install-week constraints.'
    WHEN s.evaluation_status = 'FEASIBLE_SUBOPTIMAL' THEN
      'Feasible but suboptimal: the plan satisfies hard budget/install constraints, but it ranks observable source metrics and cheap tiers instead of optimizing upgrade tiers against predicted failure risk and graph-derived customer impact.'
    WHEN s.evaluation_status = 'INFEASIBLE' THEN
      'Infeasible: the selected tower/tier set violates the budget or install-week envelope.'
    ELSE
      'Incomplete: the output is not an executable tower/tier plan.'
  END AS summary_explanation,
  CASE
    WHEN s.plan_id = 'RAI_OPTIMAL' THEN
      'Budget is binding; install weeks have slack. This is the benchmark for plan quality.'
    ELSE
      'Compared with RAI optimal, this plan achieves ' || s.pct_of_rai_objective || '% of governed objective value, restores ' || s.capacity_restored_gbps || ' Gbps, and misses high-value RAI-selected towers including ' || COALESCE(m.missed_towers, 'none') || '.'
  END AS suboptimality_explanation
FROM s
LEFT JOIN missed m ON s.plan_id = m.plan_id;
