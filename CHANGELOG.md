# Changelog

## [Unreleased]

## [v2.4.0] - 2026-01-16
### Added
- **Excel User Onboarding**: Bulk upload users (SRH, DRSM, DO, FO) with hierarchy mapping using `RO_List.xlsx`.
- **Full Hierarchy Support**: Backend now supports and serves a 5-level hierarchy (SRH -> DRSM -> DO -> FO -> RO).
- **UserROMapping**: New database model for generic user-to-RO mapping.
- **Reject Option**: Added ability for Vendor, DO, and Superuser to reject feedback in the workflow.
- **Report Filters**: Optimized layout (2-row/5-column) for identical sizing and responsiveness.

### Changed
- **RBAC Logic**: Refactored `admin_portal.py` to use `UserROMapping` for precise access control.
- **Frontend UI**: Updated `UserManagement` with Upload/Hierarchy tabs and `Reports` with improved filters.
- **Workflow**: Updated assignment logic to leverage new mapping tables.

### Fixed
- **Login Issues**: Resolved test environment login failures.
- **Filter Truncation**: Fixed issue where long RO names were truncated in report filters.
