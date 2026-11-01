# SRS route contract

Source MVP route contracts, translated by `src/features/navigation.tsx` into the approved portal routes. Includes 33 core SRS templates; public resources and notice administration are extensions.

| ID | Source route | Purpose |
|---|---|---|
| S01 | `/` | Public entry |
| S02 | `/login` | Unified login |
| S03 | `/reset-password` | Password recovery |
| S04 | `/notifications` | Scoped notifications |
| S05 | `/settings` | Account and preferences |
| I01 | `/institution/dashboard` | Institution overview |
| I02 | `/institution/applications` | Own applications |
| I03 | `/institution/applications/new` | Category/year selection |
| I04 | `/institution/applications/:id/details` | Institution/request details |
| I05 | `/institution/applications/:id/checklist` | Dynamic checklist |
| I06 | `/institution/applications/:id/documents` | Uploads and versions |
| I07 | `/institution/applications/:id/validation` | Pre-submission validation |
| I08 | `/institution/applications/:id/review-submit` | Review and submit |
| I09 | `/institution/applications/:id/status` | Publishable status |
| I10 | `/institution/history` | Approved-history timeline |
| I11 | `/institution/history/:recordId` | Historical snapshot |
| I12 | `/institution/deficiencies` | Clarification inbox |
| I13 | `/institution/deficiencies/:requestId` | Clarification response |
| O01 | `/officer/dashboard` | Assigned workload |
| O02 | `/officer/applications` | Case queue |
| O03 | `/officer/applications/:id/overview` | Case overview |
| O04 | `/officer/applications/:id/evidence` | Document/evidence viewer |
| O05 | `/officer/applications/:id/authenticity` | Source/provenance checks |
| O06 | `/officer/applications/:id/compliance` | Regulatory review |
| O07 | `/officer/applications/:id/inspection` | Infrastructure/inspection |
| O08 | `/officer/applications/:id/review` | Human review/actions |
| O09 | `/officer/verifications` | Verification tasks |
| O10 | `/officer/reports` | Report/export library |
| A01 | `/admin/users-roles` | Access management |
| A02 | `/admin/rules` | Versioned rule library |
| A03 | `/admin/integrations` | Connector health/mode |
| A04 | `/admin/audit` | Governance audit |
| A05 | `/admin/knowledge` | Approved knowledge sources |