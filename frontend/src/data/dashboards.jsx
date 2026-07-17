/* Standard dashboards — ported 1:1 from the design mock (ui/mock/index.html).
   These are the baked/offline renders; live values are overlaid from
   POST /api/dashboards/resolve when the backend is reachable. */

export const SECTION_META = {
  overview: { name: 'Overview', desc: 'A point-in-time read of the catalog — trust, quality, sensitivity, and coverage across all connected sources.' },
  system: { name: 'System', desc: 'Operational health of the catalog: profiling, scan freshness, and ingestion across sources.' },
  user: { name: 'User', desc: 'Stewardship and human activity — ownership, ratings, and recent changes across the catalog.' },
  governance: { name: 'Governance', desc: 'Business-glossary coverage and policy posture across catalog assets.' },
  quality: { name: 'Quality', desc: 'Data-quality scores and the dimensions behind them.' },
  sensitivity: { name: 'Sensitivity', desc: 'Privacy exposure — sensitivity levels and content-scan (PII) discoveries.' },
}

export const SECTIONS = Object.keys(SECTION_META)

export const pill = (t, c) => <span className={`pill ${c}`}>{t}</span>

const K = (label, val, dir, delta, col, ico, spark, tint) => ({
  kind: 'kpi', label, val, dir, delta, col, ico, spark, tint: tint || 'var(--brand-tint)',
})

const SENS = [
  { k: 'Low', v: 9180, c: 'var(--high)' },
  { k: 'Medium', v: 2458, c: 'var(--mid)' },
  { k: 'High', v: 842, c: 'var(--low)' },
]

export const SCORE = ['var(--low)', 'var(--mid)', 'var(--high)']

export const DASHBOARDS = {
  overview: [
    { id: 'catalog-health', name: 'Catalog health', desc: 'Trust, quality & coverage at a glance', panels: [
      K('Catalog assets', '12,480', 'up', '3.1% vs last wk', 'var(--brand)', '◳', [9, 10, 10, 11, 11, 12, 12.4]),
      K('Data sources', '18', 'flat', 'no change', 'var(--c2)', '⛁', [16, 16, 17, 17, 18, 18, 18], 'var(--c2-t)'),
      K('Glossary coverage', '61%', 'up', '+4 pts', 'var(--high)', '❏', [48, 52, 53, 55, 57, 59, 61], 'var(--high-t)'),
      K('High sensitivity', '842', 'down', '−18 unowned', 'var(--low)', '🔒', [60, 58, 55, 52, 50, 46, 42], 'var(--low-t)'),
      { kind: 'chart', title: 'Trust spectrum', sub: '8,214 scored assets', span: 2, chart: 'spectrum', q: 'trust_distribution',
        data: [{ k: 'Untrusted', v: 2104, r: '0–50' }, { k: 'Trusted', v: 3890, r: '51–75' }, { k: 'Highly Trusted', v: 2220, r: '76–100' }] },
      { kind: 'chart', title: 'Sensitivity mix', sub: 'all assets', span: 2, chart: 'donut', q: 'sensitivity_mix', data: SENS },
      { kind: 'chart', title: 'Quality by source', sub: 'mean quality score', span: 2, chart: 'bars', q: 'quality_by_source',
        data: [{ k: 'Snowflake', v: 86 }, { k: 'Postgres', v: 78 }, { k: 'S3-raw', v: 64 }, { k: 'Oracle', v: 81 }, { k: 'BigQuery', v: 73 }], opts: { h: 170, max: 100 } },
      { kind: 'chart', title: 'Glossary coverage trend', sub: '% with a term · 12 wk', span: 2, chart: 'line', q: 'coverage_trend',
        data: [48, 50, 51, 53, 53, 55, 56, 57, 58, 59, 60, 61], opts: { fmt: (v) => v + '%' } },
    ] },
    { id: 'risk-hotspots', name: 'Risk hotspots', desc: 'Where governance needs attention', panels: [
      K('Untrusted assets', '2,104', 'down', '−112', 'var(--low)', '▽', [2400, 2350, 2300, 2250, 2200, 2150, 2104], 'var(--low-t)'),
      K('Unowned · high sens', '63', 'down', '−12', 'var(--low)', '!', [90, 84, 80, 76, 72, 68, 63], 'var(--low-t)'),
      K('Untermed critical', '47', 'down', '−9', 'var(--mid)', '❏', [68, 64, 60, 56, 53, 50, 47], 'var(--mid-t)'),
      K('Failed scans', '12', 'down', '−5 today', 'var(--low)', '✕', [22, 20, 18, 17, 15, 14, 12], 'var(--low-t)'),
      { kind: 'chart', title: 'Highest-risk assets', chip: 'review', span: 2, chart: 'table', q: 'risk_assets',
        cols: ['Asset', 'Source', 'Issue'],
        rows: [
          ['customer_pii', 'Oracle', pill('Untermed + High', 'hi')],
          ['billing_export', 'S3-raw', pill('Unowned + High', 'hi')],
          ['invoices_2019', 'Oracle', pill('Quality 34', 'md')],
          ['meter_raw', 'S3-raw', pill('Scan failed', 'md')]] },
      { kind: 'chart', title: 'Trust by source', sub: 'bucket share', span: 2, chart: 'stacked', q: 'trust_by_source',
        data: [{ k: 'Snow', Untrusted: 300, Trusted: 600, High: 900 }, { k: 'S3', Untrusted: 700, Trusted: 400, High: 200 }, { k: 'PG', Untrusted: 200, Trusted: 700, High: 500 }, { k: 'Ora', Untrusted: 340, Trusted: 520, High: 410 }],
        keys: ['Untrusted', 'Trusted', 'High'], colors: SCORE },
      { kind: 'chart', title: 'Sensitivity mix', span: 2, chart: 'donut', q: 'sensitivity_mix', data: SENS },
      { kind: 'chart', title: 'Coverage gap by source', sub: '% untermed', span: 2, chart: 'bars', q: 'lineage_by_source',
        data: [{ k: 'S3-raw', v: 58, c: 'var(--low)' }, { k: 'Oracle', v: 41, c: 'var(--mid)' }, { k: 'BigQuery', v: 34, c: 'var(--mid)' }, { k: 'Postgres', v: 22, c: 'var(--high)' }], opts: { h: 170, max: 100 } },
    ] },
    { id: 'executive-scorecard', name: 'Executive scorecard', desc: 'Targets & posture on one page', panels: [
      K('Catalog assets', '12,480', 'up', '3.1% vs last wk', 'var(--brand)', '◳', [9, 10, 10, 11, 11, 12, 12.4]),
      K('Mean quality', '76', 'up', '+2', 'var(--c2)', '◈', [70, 72, 73, 74, 75, 75, 76], 'var(--c2-t)'),
      K('Term coverage', '61%', 'up', '+4 pts', 'var(--high)', '❏', [48, 52, 53, 55, 57, 59, 61], 'var(--high-t)'),
      K('Lineage verified', '73%', 'up', '+5 pts', 'var(--c4)', '⇄', [62, 65, 67, 69, 70, 72, 73], 'var(--c4-t)'),
      { kind: 'chart', title: 'Quality vs target', sub: 'by source · target 80', span: 2, chart: 'bullet', q: 'quality_by_source',
        data: [{ k: 'Snowflake', v: 86, t: 80 }, { k: 'Postgres', v: 78, t: 80 }, { k: 'Oracle', v: 81, t: 80 }, { k: 'S3-raw', v: 64, t: 80 }, { k: 'BigQuery', v: 73, t: 80 }] },
      { kind: 'chart', title: 'DQ dimensions', sub: 'mean across sources', span: 2, chart: 'radar', q: 'dq_dimensions',
        data: [{ k: 'Complete', v: 88 }, { k: 'Accurate', v: 79 }, { k: 'Valid', v: 82 }, { k: 'Unique', v: 71 }, { k: 'Consistent', v: 76 }] },
      { kind: 'chart', title: 'Term coverage', sub: '% of assets', span: 2, chart: 'gauge', q: 'term_coverage', val: 61 },
      { kind: 'chart', title: 'Watchlist', chip: 'review', span: 2, chart: 'table', q: 'risk_assets',
        cols: ['Asset', 'Source', 'Issue'],
        rows: [
          ['customer_pii', 'Oracle', pill('Untermed + High', 'hi')],
          ['billing_export', 'S3-raw', pill('Unowned + High', 'hi')],
          ['invoices_2019', 'Oracle', pill('Quality 34', 'md')],
          ['meter_raw', 'S3-raw', pill('Scan failed', 'md')]] },
    ] },
  ],
  system: [
    { id: 'profiling-health', name: 'Profiling health', desc: 'Scan & profile status', panels: [
      K('Profiled assets', '94.2%', 'up', '+1.4%', 'var(--brand)', '◉', [88, 90, 91, 92, 93, 94, 94.2]),
      K('Failed scans', '12', 'down', '−5 today', 'var(--low)', '✕', [22, 20, 18, 17, 15, 14, 12], 'var(--low-t)'),
      K('Avg scan time', '3.4m', 'flat', 'steady', 'var(--c2)', '◷', [3.5, 3.4, 3.6, 3.3, 3.4, 3.4, 3.4], 'var(--c2-t)'),
      K('Workers active', '6', 'up', '2 running', 'var(--high)', '⚙', [4, 5, 4, 6, 5, 6, 6], 'var(--high-t)'),
      { kind: 'chart', title: 'Profiling status', sub: 'last run', span: 2, chart: 'donut', q: 'profile_status',
        data: [{ k: 'Completed', v: 11760, c: 'var(--high)' }, { k: 'Skipped', v: 708, c: 'var(--mid)' }, { k: 'Failed', v: 12, c: 'var(--low)' }] },
      { kind: 'chart', title: 'Assets by data source', span: 2, chart: 'bars', q: 'assets_by_source',
        data: [{ k: 'Snowflake', v: 4210 }, { k: 'S3-raw', v: 3120 }, { k: 'Postgres', v: 2480 }, { k: 'Oracle', v: 1690 }, { k: 'BigQuery', v: 980 }], opts: { h: 170 } },
      { kind: 'chart', title: 'Scan & profile activity', sub: 'daily · last 24 wks', span: 4, chart: 'calendar', weeks: 24 },
      { kind: 'chart', title: 'Stale & failed assets', chip: '12 need attention', span: 4, chart: 'table', q: 'stale_failed',
        cols: ['Asset', 'Source', 'Status', 'Last attempt'],
        rows: [
          ['billing.invoices_2019', 'Oracle', pill('Failed', 'hi'), '2h ago'],
          ['meter_reads_raw', 'S3-raw', pill('Failed', 'hi'), '2h ago'],
          ['cust_archive', 'Snowflake', pill('Skipped', 'md'), '1d ago'],
          ['gis_parcels', 'Postgres', pill('Skipped', 'md'), '1d ago']] },
    ] },
    { id: 'source-inventory', name: 'Source inventory', desc: 'What is connected & how much', panels: [
      K('Connected sources', '18', 'flat', 'no change', 'var(--brand)', '⛁', [16, 16, 17, 17, 18, 18, 18]),
      K('Total assets', '12,480', 'up', '+380', 'var(--high)', '◳', [11.5, 11.8, 12, 12.1, 12.3, 12.4, 12.48], 'var(--high-t)'),
      K('Tables', '9,640', 'up', '+260', 'var(--c2)', '▤', [9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.64], 'var(--c2-t)'),
      K('Files', '2,840', 'up', '+120', 'var(--c4)', '❐', [2.5, 2.6, 2.7, 2.7, 2.8, 2.8, 2.84], 'var(--c4-t)'),
      { kind: 'chart', title: 'Assets by data source', span: 2, chart: 'bars', q: 'assets_by_source',
        data: [{ k: 'Snowflake', v: 4210 }, { k: 'S3-raw', v: 3120 }, { k: 'Postgres', v: 2480 }, { k: 'Oracle', v: 1690 }, { k: 'BigQuery', v: 980 }], opts: { h: 170 } },
      { kind: 'chart', title: 'Assets by type', span: 2, chart: 'donut', q: 'assets_by_type',
        data: [{ k: 'Table', v: 9640, c: 'var(--c1)' }, { k: 'File', v: 2840, c: 'var(--c2)' }] },
      { kind: 'chart', title: 'Sources', chip: '18 connected', span: 4, chart: 'table', q: 'source_inventory',
        cols: ['Source', 'Type', 'Assets', 'Last scan'],
        rows: [
          ['Snowflake-PROD', 'Warehouse', '4,210', '12 min ago'],
          ['S3-raw', 'Object store', '3,120', '1h ago'],
          ['Postgres-billing', 'Database', '2,480', '40 min ago'],
          ['Oracle-legacy', 'Database', '1,690', '3h ago']] },
    ] },
    { id: 'scan-operations', name: 'Scan operations', desc: 'Throughput, freshness & the fix queue', panels: [
      K('Scans · 14d', '420', 'up', '+38 vs prior', 'var(--brand)', '⟲', [310, 330, 350, 365, 385, 400, 420]),
      K('Profiled assets', '94.2%', 'up', '+1.4%', 'var(--high)', '◉', [88, 90, 91, 92, 93, 94, 94.2], 'var(--high-t)'),
      K('Workers active', '6', 'up', '2 running', 'var(--c2)', '⚙', [4, 5, 4, 6, 5, 6, 6], 'var(--c2-t)'),
      K('Failed scans', '12', 'down', '−5 today', 'var(--low)', '✕', [22, 20, 18, 17, 15, 14, 12], 'var(--low-t)'),
      { kind: 'chart', title: 'Daily scan volume', sub: 'assets scanned / day', span: 2, chart: 'line', q: 'scan_activity',
        data: [18, 22, 20, 26, 24, 30, 28, 34, 31, 36, 33, 38] },
      { kind: 'chart', title: 'Profiled assets', sub: '% of catalog', span: 2, chart: 'gauge', q: 'profile_status', val: 94 },
      { kind: 'chart', title: 'Fix queue', chip: '12 need attention', span: 4, chart: 'table', q: 'stale_failed',
        cols: ['Asset', 'Source', 'Status', 'Last attempt'],
        rows: [
          ['billing.invoices_2019', 'Oracle', pill('Failed', 'hi'), '2h ago'],
          ['meter_reads_raw', 'S3-raw', pill('Failed', 'hi'), '2h ago'],
          ['cust_archive', 'Snowflake', pill('Skipped', 'md'), '1d ago'],
          ['gis_parcels', 'Postgres', pill('Skipped', 'md'), '1d ago']] },
    ] },
  ],
  user: [
    { id: 'stewardship', name: 'Stewardship', desc: 'Ownership coverage & workload', panels: [
      K('Assets owned', '68%', 'up', '+6 pts', 'var(--high)', '☑', [55, 58, 60, 62, 64, 66, 68], 'var(--high-t)'),
      K('Active stewards', '14', 'up', '+2', 'var(--brand)', '☺', [10, 11, 12, 12, 13, 13, 14]),
      K('Unowned assets', '3,994', 'down', '−210', 'var(--mid)', '○', [46, 44, 42, 40, 38, 34, 32], 'var(--mid-t)'),
      K('Avg time to own', '4.2d', 'down', '−0.6d', 'var(--c2)', '◷', [6, 5.5, 5, 4.8, 4.5, 4.3, 4.2], 'var(--c2-t)'),
      { kind: 'chart', title: 'Owned vs unowned', sub: 'by source', span: 2, chart: 'stacked', q: 'owners_coverage',
        data: [{ k: 'Snowflake', Owned: 3100, Unowned: 1110 }, { k: 'S3-raw', Owned: 1500, Unowned: 1620 }, { k: 'Postgres', Owned: 1900, Unowned: 580 }, { k: 'Oracle', Owned: 1200, Unowned: 490 }],
        keys: ['Owned', 'Unowned'], colors: ['var(--brand)', 'var(--border-strong)'] },
      { kind: 'chart', title: 'Owner workload', sub: 'assets per steward', span: 2, chart: 'bars', q: 'owner_workload',
        data: [{ k: 'a.ruiz', v: 1240 }, { k: 'm.chen', v: 980 }, { k: 't.okafor', v: 870 }, { k: 's.patel', v: 640 }, { k: 'j.diaz', v: 520 }], opts: { h: 170 } },
      { kind: 'chart', title: 'Unowned · high value', chip: 'assign', span: 4, chart: 'table', q: 'unowned_high_value',
        cols: ['Asset', 'Source', 'Sensitivity', 'Trust'],
        rows: [
          ['customer_master', 'Snowflake', pill('High', 'hi'), '82'],
          ['payments_2024', 'Postgres', pill('High', 'hi'), '74'],
          ['meter_events', 'S3-raw', pill('Medium', 'md'), '61'],
          ['service_orders', 'Oracle', pill('Medium', 'md'), '58']] },
    ] },
    { id: 'activity-ratings', name: 'Activity & ratings', desc: 'Edits, ratings & freshness', panels: [
      K('Edits this week', '327', 'up', '+12%', 'var(--c4)', '✎', [240, 260, 280, 300, 290, 310, 327], 'var(--c4-t)'),
      K('Avg rating', '4.1', 'flat', 'of 5', 'var(--c3)', '★', [3.9, 4, 4, 4.1, 4, 4.1, 4.1], 'var(--mid-t)'),
      K('Assets rated', '58%', 'up', '+4 pts', 'var(--high)', '☆', [50, 52, 53, 55, 56, 57, 58], 'var(--high-t)'),
      K('Modified · 7d', '892', 'up', '+8%', 'var(--brand)', '⟳', [760, 800, 820, 840, 860, 880, 892]),
      { kind: 'chart', title: 'Ratings distribution', span: 2, chart: 'bars', q: 'ratings_distribution',
        data: [{ k: '5★', v: 3200, c: 'var(--high)' }, { k: '4★', v: 4100, c: 'var(--high)' }, { k: '3★', v: 2300, c: 'var(--mid)' }, { k: '2★', v: 900, c: 'var(--mid)' }, { k: '1★', v: 380, c: 'var(--low)' }], opts: { h: 170 } },
      { kind: 'chart', title: 'Recently modified', sub: 'assets / day', span: 2, chart: 'line', q: 'recently_modified',
        data: [40, 55, 48, 62, 70, 58, 75, 80, 72, 88, 84, 92], opts: { color: 'var(--c4)' } },
      { kind: 'chart', title: 'Edits by action', span: 2, chart: 'bars', q: 'edit_activity',
        data: [{ k: 'Term linked', v: 142 }, { k: 'Owner set', v: 98 }, { k: 'Rated', v: 54 }, { k: 'Tagged', v: 33 }], opts: { h: 160, color: 'var(--c4)' } },
      { kind: 'chart', title: 'Most active stewards', span: 2, chart: 'bars', q: 'owner_workload',
        data: [{ k: 'a.ruiz', v: 88 }, { k: 'm.chen', v: 71 }, { k: 't.okafor', v: 60 }, { k: 's.patel', v: 44 }], opts: { h: 160 } },
    ] },
    { id: 'contribution-pulse', name: 'Contribution pulse', desc: 'Daily edits & ownership momentum', panels: [
      K('Edits total', '5,340', 'up', '+9% this mo', 'var(--c4)', '✎', [4.4, 4.6, 4.8, 4.9, 5.1, 5.2, 5.34], 'var(--c4-t)'),
      K('Avg rating', '4.1', 'flat', 'of 5', 'var(--c3)', '★', [3.9, 4, 4, 4.1, 4, 4.1, 4.1], 'var(--mid-t)'),
      K('Assets owned', '68%', 'up', '+6 pts', 'var(--high)', '☑', [55, 58, 60, 62, 64, 66, 68], 'var(--high-t)'),
      K('Modified · 7d', '892', 'up', '+8%', 'var(--brand)', '⟳', [760, 800, 820, 840, 860, 880, 892]),
      { kind: 'chart', title: 'Edit activity', sub: 'daily · last 24 wks', span: 4, chart: 'calendar', weeks: 24 },
      { kind: 'chart', title: 'Edits by action', sub: 'what stewards change', span: 2, chart: 'donut', q: 'edit_activity',
        data: [{ k: 'Tagged', v: 1840 }, { k: 'Termed', v: 1260 }, { k: 'Owned', v: 980 }, { k: 'Rated', v: 720 }, { k: 'Described', v: 540 }] },
      { kind: 'chart', title: 'Assets owned', sub: '% with an owner', span: 2, chart: 'gauge', q: 'owners_coverage', val: 68 },
    ] },
  ],
  governance: [
    { id: 'glossary-coverage', name: 'Glossary coverage', desc: 'Term coverage & gaps', panels: [
      K('Terms defined', '412', 'up', '+28 this mo', 'var(--brand)', '❏', [360, 372, 384, 392, 400, 408, 412]),
      K('Term coverage', '61%', 'up', '+4 pts', 'var(--high)', '%', [52, 54, 56, 57, 59, 60, 61], 'var(--high-t)'),
      K('Critical untermed', '47', 'down', '−9', 'var(--low)', '!', [68, 64, 60, 56, 53, 50, 47], 'var(--low-t)'),
      K('Terms in review', '23', 'flat', 'pending', 'var(--mid)', '◷', [20, 22, 21, 23, 22, 23, 23], 'var(--mid-t)'),
      { kind: 'chart', title: 'Term coverage', sub: '% of assets', span: 2, chart: 'gauge', q: 'term_coverage', val: 61 },
      { kind: 'chart', title: 'Top business terms', span: 2, chart: 'bars', q: 'top_terms',
        data: [{ k: 'Customer', v: 1820 }, { k: 'Meter', v: 1340 }, { k: 'Invoice', v: 1100 }, { k: 'Parcel', v: 760 }, { k: 'Reading', v: 640 }], opts: { h: 170 } },
      { kind: 'chart', title: 'Coverage trend', sub: '% with a term · 12 wk', span: 2, chart: 'line', q: 'coverage_trend',
        data: [52, 54, 55, 56, 57, 58, 58, 59, 60, 60, 61, 61], opts: { fmt: (v) => v + '%' } },
      { kind: 'chart', title: 'Untermed critical elements', chip: 'action', span: 2, chart: 'table', q: 'untermed_critical',
        cols: ['Element', 'Source', 'Sensitivity'],
        rows: [
          ['ssn', 'Oracle', pill('High', 'hi')],
          ['account_no', 'Snowflake', pill('High', 'hi')],
          ['service_addr', 'Postgres', pill('Medium', 'md')],
          ['meter_id', 'S3-raw', pill('Low', 'lo')]] },
    ] },
    { id: 'policy-lineage', name: 'Policy & lineage', desc: 'Policy posture & lineage health', panels: [
      K('Lineage verified', '73%', 'up', '+5 pts', 'var(--brand)', '⇄', [62, 65, 67, 69, 70, 72, 73]),
      K('Policies applied', '9', 'up', '+1', 'var(--high)', '▤', [7, 7, 8, 8, 8, 9, 9], 'var(--high-t)'),
      K('Assets in policy', '71%', 'up', '+3 pts', 'var(--c2)', '◑', [64, 66, 67, 68, 69, 70, 71], 'var(--c2-t)'),
      K('Unverified lineage', '3,370', 'down', '−240', 'var(--mid)', '◌', [40, 38, 36, 34, 32, 30, 27], 'var(--mid-t)'),
      { kind: 'chart', title: 'Lineage verified', span: 2, chart: 'donut', q: 'lineage_status',
        data: [{ k: 'Verified', v: 9110, c: 'var(--high)' }, { k: 'Unverified', v: 3370, c: 'var(--border-strong)' }] },
      { kind: 'chart', title: 'Assets per policy', span: 2, chart: 'bars', q: 'policy_counts',
        data: [{ k: 'PII handling', v: 1840 }, { k: 'Retention', v: 1320 }, { k: 'Access tier', v: 980 }, { k: 'Residency', v: 540 }], opts: { h: 170 } },
      { kind: 'chart', title: 'Lineage coverage by source', span: 4, chart: 'stacked', q: 'lineage_by_source',
        data: [{ k: 'Snowflake', Verified: 3100, Unverified: 1110 }, { k: 'S3-raw', Verified: 1500, Unverified: 1620 }, { k: 'Postgres', Verified: 1900, Unverified: 580 }, { k: 'Oracle', Verified: 1200, Unverified: 490 }, { k: 'BigQuery', Verified: 610, Unverified: 370 }],
        keys: ['Verified', 'Unverified'], colors: ['var(--brand)', 'var(--border-strong)'] },
    ] },
    { id: 'governance-sla', name: 'Governance SLA', desc: 'Coverage targets, tracked like SLAs', panels: [
      K('Term coverage', '61%', 'up', '+4 pts', 'var(--high)', '%', [52, 54, 56, 57, 59, 60, 61], 'var(--high-t)'),
      K('Policy coverage', '68%', 'up', '+3 pts', 'var(--c2)', '▤', [60, 62, 63, 65, 66, 67, 68], 'var(--c2-t)'),
      K('Lineage verified', '73%', 'up', '+5 pts', 'var(--brand)', '⇄', [62, 65, 67, 69, 70, 72, 73]),
      K('Terms in review', '23', 'flat', 'pending', 'var(--mid)', '◷', [20, 22, 21, 23, 22, 23, 23], 'var(--mid-t)'),
      { kind: 'chart', title: 'Term coverage', sub: 'target 75', span: 2, chart: 'gauge', q: 'term_coverage', val: 61 },
      { kind: 'chart', title: 'Policy coverage', sub: 'assets under a policy', span: 2, chart: 'gauge', q: 'policy_coverage', val: 68 },
      { kind: 'chart', title: 'Lineage verified', sub: 'of scored assets', span: 2, chart: 'gauge', q: 'lineage_status', val: 73 },
      { kind: 'chart', title: 'Term coverage vs target', sub: 'by source · target 75', span: 2, chart: 'bullet', q: 'term_coverage',
        data: [{ k: 'Snowflake', v: 74, t: 75 }, { k: 'Postgres', v: 68, t: 75 }, { k: 'Oracle', v: 41, t: 75 }, { k: 'S3-raw', v: 34, t: 75 }, { k: 'BigQuery', v: 34, t: 75 }] },
    ] },
  ],
  quality: [
    { id: 'quality-scores', name: 'Quality scores', desc: 'Score distribution & laggards', panels: [
      K('Mean quality', '76', 'up', '+2', 'var(--brand)', '◈', [70, 72, 73, 74, 75, 75, 76]),
      K('Below target', '214', 'down', '−31 tables', 'var(--low)', '▽', [280, 270, 255, 245, 235, 224, 214], 'var(--low-t)'),
      K('Completeness', '88%', 'up', '+1%', 'var(--high)', '◔', [84, 85, 86, 86, 87, 87, 88], 'var(--high-t)'),
      K('Uniqueness', '71%', 'flat', 'steady', 'var(--c3)', '◑', [70, 71, 70, 71, 72, 71, 71], 'var(--mid-t)'),
      { kind: 'chart', title: 'Quality score distribution', span: 2, chart: 'histo', q: 'quality_distribution',
        data: [{ lo: 0, v: 120 }, { lo: 10, v: 180 }, { lo: 20, v: 260 }, { lo: 30, v: 420 }, { lo: 40, v: 680 }, { lo: 50, v: 1100 }, { lo: 60, v: 1640 }, { lo: 70, v: 2200 }, { lo: 80, v: 1800 }, { lo: 90, v: 980 }] },
      { kind: 'chart', title: 'Quality vs target', sub: 'by source · target 80', span: 2, chart: 'bullet', q: 'quality_by_source',
        data: [{ k: 'Snowflake', v: 86, t: 80 }, { k: 'Postgres', v: 78, t: 80 }, { k: 'Oracle', v: 81, t: 80 }, { k: 'S3-raw', v: 64, t: 80 }, { k: 'BigQuery', v: 73, t: 80 }] },
      { kind: 'chart', title: 'Lowest-scoring tables', span: 2, chart: 'bars', q: 'worst_tables',
        data: [{ k: 'invoices_2019', v: 34, c: 'var(--low)' }, { k: 'meter_raw', v: 41, c: 'var(--low)' }, { k: 'cust_arch', v: 48, c: 'var(--low)' }, { k: 'gis_old', v: 52, c: 'var(--mid)' }, { k: 'logs_2020', v: 55, c: 'var(--mid)' }], opts: { h: 170, max: 100 } },
      { kind: 'chart', title: 'Below-target tables', chip: 'remediate', span: 2, chart: 'table', q: 'worst_tables',
        cols: ['Table', 'Source', 'Score', 'Worst dim'],
        rows: [
          ['invoices_2019', 'Oracle', pill('34', 'hi'), 'Completeness'],
          ['meter_raw', 'S3-raw', pill('41', 'hi'), 'Validity'],
          ['cust_arch', 'Snowflake', pill('48', 'hi'), 'Uniqueness'],
          ['gis_old', 'Postgres', pill('52', 'md'), 'Accuracy']] },
    ] },
    { id: 'dq-dimensions', name: 'DQ dimensions', desc: 'The dimensions behind the score', panels: [
      K('Completeness', '88%', 'up', '+1%', 'var(--high)', '◔', [84, 85, 86, 86, 87, 87, 88], 'var(--high-t)'),
      K('Accuracy', '79%', 'up', '+2%', 'var(--brand)', '◎', [74, 75, 76, 77, 78, 78, 79]),
      K('Validity', '82%', 'flat', 'steady', 'var(--c2)', '◍', [81, 82, 81, 82, 83, 82, 82], 'var(--c2-t)'),
      K('Consistency', '76%', 'up', '+3%', 'var(--c4)', '◐', [70, 71, 72, 73, 74, 75, 76], 'var(--c4-t)'),
      { kind: 'chart', title: 'DQ dimensions', sub: 'mean across sources', span: 2, chart: 'radar', q: 'dq_dimensions',
        data: [{ k: 'Complete', v: 88 }, { k: 'Accurate', v: 79 }, { k: 'Valid', v: 82 }, { k: 'Unique', v: 71 }, { k: 'Consistent', v: 76 }] },
      { kind: 'chart', title: 'Dimension scores', span: 2, chart: 'bars', q: 'dq_dimensions',
        data: [{ k: 'Complete', v: 88 }, { k: 'Valid', v: 82 }, { k: 'Accurate', v: 79 }, { k: 'Consistent', v: 76 }, { k: 'Unique', v: 71 }], opts: { h: 170, max: 100 } },
      { kind: 'chart', title: 'Dimensions by source', span: 4, chart: 'stacked', q: 'dq_by_source',
        data: [{ k: 'Snowflake', Complete: 90, Valid: 88, Unique: 82 }, { k: 'Postgres', Complete: 86, Valid: 80, Unique: 70 }, { k: 'S3-raw', Complete: 74, Valid: 68, Unique: 55 }, { k: 'Oracle', Complete: 85, Valid: 84, Unique: 76 }],
        keys: ['Complete', 'Valid', 'Unique'], colors: ['var(--c1)', 'var(--c2)', 'var(--c6)'] },
    ] },
    { id: 'quality-posture', name: 'Quality posture', desc: 'The mean, the bands & the fix list', panels: [
      K('Mean quality', '76', 'up', '+2', 'var(--brand)', '◈', [70, 72, 73, 74, 75, 75, 76]),
      K('Lowest score', '34', 'up', '+3', 'var(--low)', '▽', [28, 29, 30, 31, 32, 33, 34], 'var(--low-t)'),
      K('Completeness', '88%', 'up', '+1%', 'var(--high)', '◔', [84, 85, 86, 86, 87, 87, 88], 'var(--high-t)'),
      K('Profiled assets', '94.2%', 'up', '+1.4%', 'var(--c2)', '◉', [88, 90, 91, 92, 93, 94, 94.2], 'var(--c2-t)'),
      { kind: 'chart', title: 'Mean quality score', sub: 'catalog-wide', span: 2, chart: 'gauge', q: 'quality_by_source', val: 76 },
      { kind: 'chart', title: 'Score bands', sub: 'assets per band', span: 2, chart: 'donut', q: 'quality_distribution',
        data: [{ k: '0–50', v: 980, c: 'var(--low)' }, { k: '51–70', v: 2740, c: 'var(--mid)' }, { k: '71–85', v: 5230, c: 'var(--high)' }, { k: '86–100', v: 3530, c: 'var(--brand)' }] },
      { kind: 'chart', title: 'Fix list', chip: 'remediate', span: 4, chart: 'table', q: 'worst_tables',
        cols: ['Table', 'Source', 'Score', 'Worst dim'],
        rows: [
          ['invoices_2019', 'Oracle', pill('34', 'hi'), 'Completeness'],
          ['meter_raw', 'S3-raw', pill('41', 'hi'), 'Validity'],
          ['cust_arch', 'Snowflake', pill('48', 'hi'), 'Uniqueness'],
          ['gis_old', 'Postgres', pill('52', 'md'), 'Accuracy']] },
    ] },
  ],
  sensitivity: [
    { id: 'exposure-overview', name: 'Exposure overview', desc: 'Sensitivity levels & exposure', panels: [
      K('High sensitivity', '842', 'down', '−18', 'var(--low)', '🔒', [60, 58, 55, 52, 50, 46, 42], 'var(--low-t)'),
      K('Unowned sensitive', '63', 'down', '−12', 'var(--low)', '!', [90, 84, 80, 76, 72, 68, 63], 'var(--low-t)'),
      K('Encrypted', '58%', 'up', '+7 pts', 'var(--high)', '✔', [44, 47, 50, 52, 54, 56, 58], 'var(--high-t)'),
      K('In residency policy', '81%', 'up', '+4 pts', 'var(--c2)', '▤', [72, 74, 76, 77, 79, 80, 81], 'var(--c2-t)'),
      { kind: 'chart', title: 'Sensitivity breakdown', span: 2, chart: 'donut', q: 'sensitivity_mix', data: SENS },
      { kind: 'chart', title: 'Sensitive by source', sub: 'High / Medium', span: 2, chart: 'stacked', q: 'sensitive_by_source',
        data: [{ k: 'Snowflake', High: 280, Medium: 640 }, { k: 'S3-raw', High: 310, Medium: 520 }, { k: 'Oracle', High: 160, Medium: 410 }, { k: 'Postgres', High: 92, Medium: 380 }],
        keys: ['High', 'Medium'], colors: ['var(--low)', 'var(--mid)'] },
      { kind: 'chart', title: 'High sensitivity · no owner', chip: 'risk', span: 4, chart: 'table', q: 'sensitive_unowned',
        cols: ['Asset', 'Source', 'PII', 'Trust'],
        rows: [
          ['customer_pii', 'Oracle', pill('SSN', 'hi'), '82'],
          ['billing_export', 'S3-raw', pill('Account', 'hi'), '74'],
          ['support_tickets', 'Snowflake', pill('Email', 'md'), '66'],
          ['field_notes', 'Postgres', pill('Phone', 'md'), '59']] },
    ] },
    { id: 'pii-discoveries', name: 'PII discoveries', desc: 'Content-scan findings', panels: [
      K('PII columns', '1,604', 'flat', 'tracked', 'var(--mid)', '⚑', [15, 16, 16, 16, 16, 16, 16], 'var(--mid-t)'),
      K('PII types', '5', 'flat', 'EMAIL, SSN…', 'var(--c5)', '⚑', [5, 5, 5, 5, 5, 5, 5], 'var(--c5-t)'),
      K('Masked', '62%', 'up', '+9 pts', 'var(--high)', '◑', [48, 51, 54, 56, 58, 60, 62], 'var(--high-t)'),
      K('In high-sens assets', '71%', 'down', '−4 pts', 'var(--low)', '▽', [80, 78, 76, 75, 74, 72, 71], 'var(--low-t)'),
      { kind: 'chart', title: 'Content-scan discoveries', sub: 'PII types', span: 2, chart: 'bars', q: 'pii_discoveries',
        data: [{ k: 'EMAIL', v: 1203 }, { k: 'PHONE', v: 980 }, { k: 'ADDRESS', v: 760 }, { k: 'DOB', v: 540 }, { k: 'SSN', v: 412 }], opts: { h: 170, color: 'var(--c5)' } },
      { kind: 'chart', title: 'PII by source', span: 2, chart: 'bars', q: 'sensitive_by_source',
        data: [{ k: 'Oracle', v: 980 }, { k: 'S3-raw', v: 840 }, { k: 'Snowflake', v: 620 }, { k: 'Postgres', v: 410 }], opts: { h: 170, color: 'var(--c5)' } },
      { kind: 'chart', title: 'Assets containing PII', chip: 'protect', span: 4, chart: 'table', q: 'pii_assets',
        cols: ['Asset', 'Source', 'PII types', 'Masked'],
        rows: [
          ['customer_pii', 'Oracle', pill('SSN · Email', 'hi'), 'No'],
          ['billing_export', 'S3-raw', pill('Account · DOB', 'hi'), 'Partial'],
          ['support_tickets', 'Snowflake', pill('Email · Phone', 'md'), 'Yes'],
          ['field_notes', 'Postgres', pill('Phone', 'md'), 'Yes']] },
    ] },
    { id: 'protection-controls', name: 'Protection controls', desc: 'Encryption & masking posture', panels: [
      K('Encrypted', '74%', 'up', '+7 pts', 'var(--high)', '✔', [58, 61, 64, 67, 70, 72, 74], 'var(--high-t)'),
      K('Masked', '61%', 'up', '+9 pts', 'var(--c2)', '◑', [47, 50, 53, 55, 58, 60, 61], 'var(--c2-t)'),
      K('High sensitivity', '842', 'down', '−18', 'var(--low)', '🔒', [60, 58, 55, 52, 50, 46, 42], 'var(--low-t)'),
      K('PII columns', '1,604', 'flat', 'tracked', 'var(--mid)', '⚑', [15, 16, 16, 16, 16, 16, 16], 'var(--mid-t)'),
      { kind: 'chart', title: 'Encryption coverage', sub: 'sensitive assets encrypted', span: 2, chart: 'gauge', q: 'encryption_status', val: 74 },
      { kind: 'chart', title: 'Masking coverage', sub: 'PII columns masked', span: 2, chart: 'gauge', q: 'masking_status', val: 61 },
      { kind: 'chart', title: 'PII protection status', chip: 'protect', span: 4, chart: 'table', q: 'pii_assets',
        cols: ['Asset', 'Source', 'PII types', 'Masked'],
        rows: [
          ['customer_pii', 'Oracle', pill('SSN · Email', 'hi'), 'No'],
          ['billing_export', 'S3-raw', pill('Account · DOB', 'hi'), 'Partial'],
          ['support_tickets', 'Snowflake', pill('Email · Phone', 'md'), 'Yes'],
          ['field_notes', 'Postgres', pill('Phone', 'md'), 'Yes']] },
    ] },
  ],
}

/* Headline KPI tiles whose meaning maps exactly to a resolver query, so they
   can show the real catalog value (live PDC or demo sample) instead of a
   baked one. */
export const KPI_QUERY = {
  'Catalog assets': 'asset_counts',
  'Data sources': 'source_counts',
  'Glossary coverage': 'term_coverage',
  'High sensitivity': 'sensitivity_mix',
  'Profiled assets': 'profile_status',
  'Mean quality': 'quality_by_source',
  'Term coverage': 'term_coverage',
  'Lineage verified': 'lineage_status',
  'Policy coverage': 'policy_coverage',
  'Assets owned': 'owners_coverage',
  'Encrypted': 'encryption_status',
  'Masked': 'masking_status',
}

export const TRUST_BANDS = { Untrusted: '0–50', Trusted: '51–75', 'Highly Trusted': '76–100' }

/* Designer: the query library shown in the left pane. */
export const LIB = [
  { g: 'Governance', items: [['trust_by_source', 'source, bucket, count'], ['term_coverage', 'source, pct'], ['top_terms', 'term, count'], ['lineage_status', 'status, count']] },
  { g: 'Quality', items: [['quality_by_source', 'source, score'], ['dq_dimensions', 'dimension, value'], ['worst_tables', 'table, score']] },
  { g: 'Sensitivity', items: [['sensitivity_mix', 'level, count'], ['pii_discoveries', 'pii_type, count, source']] },
  { g: 'System', items: [['profile_status', 'status, count'], ['assets_by_source', 'source, count']] },
]

export const CHART_ICONS = { bar: '▭', donut: '◑', line: '╱', stacked: '▣', table: '☰', gauge: '◔', radar: '✦', heatmap: '▦' }

/* Map a mock chart type -> the resolver kind/chartType that yields the right
   shape from POST /api/dashboards/resolve. */
export function resolverKind(chart) {
  if (chart === 'table') return { kind: 'table' }
  if (chart === 'gauge') return { kind: 'kpi' }
  if (chart === 'stacked') return { kind: 'chart', chartType: 'stackedBar' }
  if (chart === 'donut') return { kind: 'chart', chartType: 'donut' }
  if (chart === 'line') return { kind: 'chart', chartType: 'line' }
  return { kind: 'chart', chartType: 'bar' } // spectrum/bars/radar/histo/bullet read a series
}
