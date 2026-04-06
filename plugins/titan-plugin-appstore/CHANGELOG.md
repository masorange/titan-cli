# Changelog

All notable changes to the App Store Connect Plugin will be documented in this file.

## [Unreleased]

### Added

#### Version Analytics Workflow (2026-03-16)

New workflow to compare propagation and stability metrics between the latest 2 released versions.

**Files Added:**

1. **Services:**
   - `titan_plugin_appstore/clients/services/analytics_service.py` - Analytics API client
     - `get_app_versions_sorted()` - Fetch latest versions sorted by date
     - `create_analytics_report_request()` - Create analytics report request
     - `poll_report_status()` - Poll for report completion with retry logic
     - `download_report_data()` - Download gzipped CSV report
     - `parse_report_data()` - Parse CSV into structured format
     - `calculate_propagation_metrics()` - Calculate growth and adoption metrics
     - `calculate_stability_metrics()` - Calculate crash rate and retention

2. **Workflow Steps:**
   - `titan_plugin_appstore/steps/fetch_versions_step.py` - Retrieve latest 2 versions
   - `titan_plugin_appstore/steps/request_analytics_step.py` - Request and download analytics
   - `titan_plugin_appstore/steps/analyze_metrics_step.py` - Calculate metrics + generate charts
   - `titan_plugin_appstore/steps/generate_analytics_report.py` - Generate HTML report

3. **Workflow Definition:**
   - `workflows/version-analytics.yaml` - Complete workflow configuration

4. **Documentation:**
   - `docs/ANALYTICS_WORKFLOW.md` - Comprehensive usage guide
   - `examples/run_analytics.py` - Standalone Python script example

**Dependencies Added:**
- `pandas >= 2.0.0` - Data analysis and manipulation
- `matplotlib >= 3.7.0` - Chart generation

**Features:**

**Propagation Metrics:**
- Total sessions per version
- Daily growth rate (%)
- Active devices trend
- Average daily growth

**Stability Metrics:**
- Crash rate (crashes / sessions × 100)
- Total crashes and sessions
- Retention D1 (Day 1)
- Retention D7 (Day 7)

**Output:**
- 3 PNG charts:
  1. Sessions over time (line chart)
  2. Daily growth rate (line chart)
  3. Stability comparison (bar charts)
- HTML report with:
  - Summary cards
  - Comparison tables with winner highlights
  - Embedded charts (base64)
  - Auto-generated key insights

**API Endpoints Used:**
- `GET /v1/apps/{id}/appStoreVersions?sort=-createdDate` - Fetch versions
- `POST /v1/analyticsReportRequests` - Create report request
- `GET /v1/analyticsReportRequests/{id}` - Poll for completion
- Download report from returned URL

**Usage:**
```bash
# Via Titan CLI workflow
titan workflow run appstore:version-analytics

# Or run standalone script
python examples/run_analytics.py
```

**Error Handling:**
- Rate limit handling with exponential backoff
- Timeout protection (max 5 minutes per report)
- Graceful degradation if crash data unavailable
- Detailed error codes for debugging

**Output Directory:**
```
./analytics_reports/
├── propagation_sessions.png
├── propagation_growth.png
├── stability_comparison.png
└── analytics_report_YYYYMMDD_HHMMSS.html
```

---

## [1.0.0] - 2026-03-13

### Added
- Initial release
- App Store Connect API integration
- Version creation workflow
- Build selection and assignment
- Submission to App Review
- HTML report generation
- Setup wizard for credentials

### Features
- Multi-brand support
- What's New text preview
- Build validation
- Submission status tracking
- Comprehensive error handling

---

**Date Format:** YYYY-MM-DD
**Version Format:** [MAJOR.MINOR.PATCH]
