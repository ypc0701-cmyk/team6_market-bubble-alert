# Creates the "Phase 2" milestone and one GitHub issue per task in docs/phase2_plan.md.
# Requires GitHub CLI: winget install --id GitHub.cli ; then: gh auth login
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File .\create_phase2_issues.ps1
# Safe to re-run: issues whose title already exists in the milestone are skipped.
# Preview without creating anything:  add -DryRun

param([switch]$DryRun)

$Repo = "ypc0701-cmyk/team6_market-bubble-alert"
$Milestone = "Phase 2"

$L1 = "lane-1-ingestion"; $L2 = "lane-2-dbt"; $L3 = "lane-3-signal"; $L4 = "lane-4-dashboard"; $L5 = "lane-5-platform"
$Kean = "keann23"; $Ahrar = "ahrar11"; $Javier = "javierberain"; $Myhill = "paddington-L831"; $Chloe = "ypc0701-cmyk"

$Issues = @(
  # ---------------- Lane 1 ----------------
  @{ Title = "Extractor reads universe_members"; Labels = @($L1); Assignees = @($Kean); Body = @'
Due Nov 15. See docs/phase2_plan.md, Lane 1.
- [ ] Extractor reads its ticker list from `universe_members` instead of the hard-coded Phase 1 list
- [ ] Phase 1 tickers keep loading exactly as today
- [ ] Dry run on the frozen universe; per-ticker source (yfinance or Tiingo) logged
Depends on: `universe_members` seeded (Lane 2)
'@ },
  @{ Title = "Universe backfill to 2020"; Labels = @($L1); Assignees = @($Kean); Body = @'
Due Nov 16.
- [ ] Daily adjusted close and volume for every universe ticker back to Jan 2020 (or its listing date) in `raw.prices_raw`
- [ ] Idempotent: re-running does not duplicate rows
- [ ] yfinance rate limits checked for ~150 tickers; failures routed through the Tiingo fallback
Depends on: extractor universe mode
'@ },
  @{ Title = "Weekly Airflow tasks: features, retrain, score"; Labels = @($L1); Assignees = @($Kean); Body = @'
Due Nov 19.
- [ ] Tasks run Fridays after the close, after the daily `dbt build`: weekly features and labels, retrain, score, log to MLflow
- [ ] A failed weekly task alerts in Slack like the daily tasks
Depends on: training and scoring entry points (Lanes 2 and 5)
'@ },
  @{ Title = "First scheduled weekly run green"; Labels = @($L1); Assignees = @($Kean); Body = @'
Due Nov 20.
- [ ] One scheduled weekly run (features, retrain, score) green end to end
- [ ] Its MLflow run linked from the Astronomer logs
- [ ] Daily DAG still green, now covering the universe
'@ },
  @{ Title = "README: backfill a new universe ticker; universe refresh step"; Labels = @($L1, "documentation"); Assignees = @($Kean); Body = @'
Due Nov 22.
- [ ] How to backfill a single new universe ticker
- [ ] Manual, documented step to re-pull ETF holdings when Lane 3 asks (never automatic)
'@ },

  # ---------------- Lane 2 ----------------
  @{ Title = "Seed universe_members with tests"; Labels = @($L2); Assignees = @($Ahrar); Body = @'
Due Nov 15. Columns per schema contract v0.3.
- [ ] `universe_members` seed modeled on `basket_members` (ticker, source ETF, added_date, removed_date, reason)
- [ ] Seeded from the list Lane 3 freezes on Nov 14
- [ ] Tests: no overlap with our 11 speculative names, no overlapping spans, not-null keys
Depends on: frozen universe list (Lane 3)
'@ },
  @{ Title = "Weekly features table"; Labels = @($L2); Assignees = @($Ahrar); Body = @'
Due Nov 17.
- [ ] One row per ticker per Friday close, every feature column in contract v0.3
- [ ] Each feature uses only data available on that date
- [ ] Tests: not-null where required, ranges, one row per (ticker, week)
Depends on: universe backfill (Lane 1)
'@ },
  @{ Title = "Weekly labels table with leakage test"; Labels = @($L2); Assignees = @($Ahrar); Body = @'
Due Nov 17.
- [ ] Label exactly as written in the Lane 3 rules (default: lowest close in next 60 trading days at least 20% below the close on date t)
- [ ] NULL for the most recent 60 trading days
- [ ] dbt test proving no feature uses a price after its own date; a seeded future-dated row fails it (demo item)
'@ },
  @{ Title = "Training and scoring models; populate model_scores"; Labels = @($L2); Assignees = @($Ahrar); Body = @'
Due Nov 19.
- [ ] BigQuery ML: `CREATE MODEL` and `ML.PREDICT` as dbt models, or Python: training-set and scoring-input views (per the Nov 13 decision)
- [ ] Baselines and models trained on the agreed time split
- [ ] Scores land in `marts.model_scores` with model version and as-of date
Depends on: features and labels; MLflow server (Lane 5)
'@ },
  @{ Title = "dbt lineage graph extended to Phase 2"; Labels = @($L2, "documentation"); Assignees = @($Ahrar); Body = @'
Due Nov 22.
- [ ] Lineage shows prices -> weekly features and labels -> model_scores
- [ ] `dbt build` passes with the Phase 2 models and tests on the daily schedule
'@ },

  # ---------------- Lane 3 ----------------
  @{ Title = "Draft Phase 2 rules and schema contract v0.3"; Labels = @($L3); Assignees = @($Javier); Body = @'
Due Nov 12. Circulate for comments by Nov 13.
- [ ] Universe rules in the decision log before any ticker is selected: which AI-themed ETFs, price > $2, avg daily trading > $5M, 60+ trading days, snapshot date
- [ ] Our 11 excluded by rule from training rows and from basket-level features
- [ ] Label (20% / 60 trading days, draft) and time split with 60-trading-day gaps
- [ ] Feature list available for all of 2020-2026 (official dial level replaced by larger-basket breadth)
- [ ] Contract v0.3 columns and dummy rows: universe_members, weekly_features, weekly_labels, model_scores
'@ },
  @{ Title = "Freeze Phase 2 rules and contract v0.3; fix universe list"; Labels = @($L3); Assignees = @($Javier); Body = @'
Due Nov 14. The Phase 2 chokepoint.
- [ ] Comments from Lanes 1, 2, 4, 5 resolved
- [ ] Rules and contract committed and marked frozen
- [ ] Universe list generated from the logged rules and handed to Lane 2
'@ },
  @{ Title = "Label base rate and baselines"; Labels = @($L3); Assignees = @($Javier); Body = @'
Due Nov 18.
- [ ] Share of positive labels by year; adjust the 20% / 60-day threshold if it is far too loose or tight (logged)
- [ ] Baseline A (drawdown only) and Baseline B (60-day volatility only) on the test period
Depends on: weekly features and labels (Lane 2)
'@ },
  @{ Title = "Evaluation report: models versus baselines"; Labels = @($L3); Assignees = @($Javier); Body = @'
Due Nov 20.
- [ ] AUC, precision of the top 10% of scores and calibration on the test period, versus base rate and both baselines
- [ ] Block-bootstrap error bars (weekly rows share overlapping 60-day labels)
- [ ] Plain statement of whether ML beats the simple rules
Depends on: trained models (Lane 2)
'@ },
  @{ Title = "Score our 11 out of sample; larger-basket dial"; Labels = @($L3); Assignees = @($Javier); Body = @'
Due Nov 21.
- [ ] Our 11 scored out of sample: are our picks riskier than the typical AI stock?
- [ ] Phase 1 dial logic run on the universe, reusing the Phase 1 marts, queryable with one SELECT next to the official dial
'@ },
  @{ Title = "Known limits measured; Phase 2 decision log entries"; Labels = @($L3, "documentation"); Assignees = @($Javier); Body = @'
Due Nov 22.
- [ ] Effect of the hindsight universe (today's ETF holdings) and survivorship on results, written next to every number
- [ ] Decision log entries for every Phase 2 rule, dated before training
'@ },

  # ---------------- Lane 4 ----------------
  @{ Title = "Phase 2 dashboard panels on dummy rows"; Labels = @($L4); Assignees = @($Myhill); Body = @'
Due Nov 15. Built against contract v0.3 dummy rows.
- [ ] Risk panel: our 11 with drop probability, rank in universe, change since last week, universe distribution
- [ ] Robustness panel: larger-basket dial next to the official dial, one sentence on how to read it
- [ ] Model card: model version, last-trained date, test AUC and the baseline it beat (or did not)
'@ },
  @{ Title = "Phase 2 panels on real scores"; Labels = @($L4); Assignees = @($Myhill); Body = @'
Due Nov 21.
- [ ] Panels read live `model_scores` and the larger-basket dial with no layout changes
- [ ] Read scores through the Cloud Run API where practical, BigQuery fallback if the API is down
Depends on: scores (Lane 2), larger-basket dial (Lane 3), API (Lane 5)
'@ },
  @{ Title = "Dashboard polish freeze and redeploy"; Labels = @($L4); Assignees = @($Myhill); Body = @'
Due Nov 22.
- [ ] Cloud Run redeploy verified; zero manual steps
- [ ] A stranger can tell whether our 11 are riskier than the typical AI stock in ten seconds
'@ },

  # ---------------- Lane 5 ----------------
  @{ Title = "MLflow tracking server live"; Labels = @($L5); Assignees = @($Chloe); Body = @'
Hosting decision Nov 12; server live Nov 16.
- [ ] MLflow on Cloud Run with artifacts in GCS (Terraform where practical)
- [ ] Reachable by the training job and by every member
- [ ] Every training run logs parameters, metrics, universe snapshot date and model version
'@ },
  @{ Title = "Cloud Run model API"; Labels = @($L5); Assignees = @($Chloe); Body = @'
Skeleton on dummy rows Nov 16; real scores Nov 20.
- [ ] `GET /risk?ticker=` and `GET /basket` reading the latest weekly scores from BigQuery (fields per docs/phase2_proposal.md)
- [ ] Read-only service account, like the dashboard's
'@ },
  @{ Title = "IAM and cost check for Phase 2"; Labels = @($L5); Assignees = @($Chloe); Body = @'
Due Nov 16.
- [ ] Permissions for the training job (BigQuery ML or Vertex/Python)
- [ ] Budget check for the larger universe, MLflow and the API
'@ },
  @{ Title = "Monitoring: accuracy, calibration, drift, API health"; Labels = @($L5, $L3); Assignees = @($Chloe, $Javier); Body = @'
Due Nov 22. Definitions from Lane 3, plumbing from Lane 5.
- [ ] Rolling AUC and calibration on predictions whose 60-day outcome is known
- [ ] Weekly feature drift check
- [ ] API errors and latency; data freshness
'@ },
  @{ Title = "Phase 2 integration check and punch list"; Labels = @($L5, "punch-list"); Assignees = @($Chloe); Body = @'
Due Nov 22.
- [ ] End-to-end check: prices -> features -> scores -> API -> dashboard
- [ ] Written punch list; items closed before the Nov 23 freeze
'@ },
  @{ Title = "AI log current for Phase 2"; Labels = @($L5, "documentation"); Assignees = @($Chloe); Body = @'
Due Nov 23.
- [ ] Every lane's Phase 2 AI use logged in docs/ai_log.md
'@ },

  # ---------------- Cross-lane decisions ----------------
  @{ Title = "Decide training engine: BigQuery ML or Python"; Labels = @($L2, $L3, $L5, "question"); Assignees = @($Ahrar, $Javier, $Chloe); Body = @'
Due Nov 13.
- [ ] Decision recorded in the decision log with the reason
- [ ] Consequences noted for Lane 1 (Airflow tasks) and Lane 5 (MLflow logging)
'@ },
  @{ Title = "Confirm Phase 2 due date and presentation format with the professor"; Labels = @($L5, "question"); Assignees = @($Chloe); Body = @'
Due next class.
- [ ] Due date and whether Phase 2 is presented separately or with Phase 3 on Dec 8
- [ ] Plan dates in docs/phase2_plan.md updated if needed
'@ }
)

# --- Milestone ---
$existing = gh api "repos/$Repo/milestones?state=all&per_page=100" | ConvertFrom-Json
if (-not ($existing | Where-Object { $_.title -eq $Milestone })) {
  Write-Host "Creating milestone '$Milestone'"
  if (-not $DryRun) {
    gh api "repos/$Repo/milestones" -f title="$Milestone" -f due_on="2026-11-23T23:59:59Z" -f description="MLOps phase: see docs/phase2_plan.md" | Out-Null
  }
}

# --- Issues ---
$have = @()
if (-not $DryRun) {
  $have = (gh issue list --repo $Repo --milestone $Milestone --state all --limit 200 --json title | ConvertFrom-Json).title
}
foreach ($i in $Issues) {
  if ($have -contains $i.Title) { Write-Host "Skip (exists): $($i.Title)"; continue }
  Write-Host "Create: $($i.Title)  [$($i.Labels -join ', ')]  -> $($i.Assignees -join ', ')"
  if ($DryRun) { continue }
  # Body goes through a temp file: Windows PowerShell mangles quotes in long native arguments.
  $tmp = New-TemporaryFile
  Set-Content -Path $tmp -Value $i.Body -Encoding UTF8
  $ghArgs = @("issue", "create", "--repo", $Repo, "--title", $i.Title, "--body-file", $tmp.FullName, "--milestone", $Milestone)
  foreach ($l in $i.Labels) { $ghArgs += @("--label", $l) }
  foreach ($a in $i.Assignees) { $ghArgs += @("--assignee", $a) }
  & gh @ghArgs
  Remove-Item $tmp
}
Write-Host "Done."
