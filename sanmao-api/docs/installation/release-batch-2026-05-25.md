# Release Batch: 2026-05-25

This document defines the recommended scope for the next release batch.

Purpose:

- keep the `Sanmao` branding/UI work together
- include the live routing/affinity safety fix
- exclude unrelated in-progress local changes

## Current production state

- Live host `sanmao.fun` is still running commit `ce4f27f`
- The local workspace contains additional uncommitted changes not yet present on the server

## Recommended release scope

### 1. Brand and UI

- `web/src/index.css`
- `web/src/pages/Home/index.jsx`
- `web/src/components/auth/LoginForm.jsx`
- `web/src/components/layout/headerbar/HeaderLogo.jsx`
- `web/src/components/layout/Footer.jsx`
- `web/src/components/dashboard/DashboardHeader.jsx`
- `web/src/components/layout/SiderBar.jsx`
- `web/src/pages/Pricing/index.jsx`
- `web/src/components/table/model-pricing/layout/PricingPage.jsx`
- `web/src/components/table/model-pricing/layout/header/PricingVendorIntro.jsx`
- `web/src/components/table/model-pricing/view/card/PricingCardView.jsx`
- `web/src/components/topup/index.jsx`
- `web/src/components/topup/RechargeCard.jsx`
- `web/src/components/topup/SubscriptionPlansCard.jsx`
- `web/src/components/topup/InvitationCard.jsx`
- `web/src/components/table/channels/index.jsx`
- `web/src/components/table/channels/ChannelsColumnDefs.jsx`
- `web/src/components/dashboard/index.jsx`
- `web/src/hooks/dashboard/useDashboardData.js`
- `web/src/hooks/dashboard/useDashboardStats.jsx`

### 2. Routing resilience

- `controller/relay.go`
- `service/channel_affinity.go`
- `service/channel_affinity_template_test.go`

### 3. Deployment and runbook

- `new-api.service`
- `scripts/export-server-state.sh`
- `docs/channel/claude-channel-routing.md`
- `docs/installation/server-state-2026-05-18.md`
- `docs/installation/migration-checklist.md`
- `docs/installation/cold-start-deployment.md`
- `docs/installation/database-verification.md`

## Explicitly exclude from this batch

These files appear to belong to other unfinished work and should not be mixed into this release without separate review:

- `.gitignore`
- `common/init.go`
- `controller/channel.go`
- `scripts/deploy-on-server.sh`
- `setting/ratio_setting/model_ratio.go`
- `web/src/components/settings/RatioSetting.jsx`
- `web/src/components/table/channels/modals/EditChannelModal.jsx`
- `web/src/components/table/channels/modals/ModelTestModal.jsx`
- `web/src/components/table/model-pricing/layout/PricingSidebar.jsx`
- `web/src/components/table/model-pricing/layout/header/SearchActions.jsx`
- `web/src/components/table/model-pricing/modal/PricingFilterModal.jsx`
- `web/src/hooks/channels/useChannelsData.jsx`
- `web/src/pages/Setting/Ratio/GroupRatioSettings.jsx`
- `web/src/pages/Setting/Ratio/ModelRatioSettings.jsx`
- `common/init_test.go`
- `controller/channel_fetch_models_test.go`
- `setting/ratio_setting/model_ratio_gemini_test.go`
- `tmp_update_gemini3_support.py`
- `.gocache-local/`
- `.gomodcache-local/`

## Release intent

This batch should produce:

- a more coherent `Sanmao` product identity across public pages and console
- a clearer pricing / billing / channel-operations story
- a safer Claude CLI routing experience after transport-layer upstream failures
- repo-local operational documentation sufficient for future machine rebuilds

