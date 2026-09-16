# AGENTS.md — AI Office IT Help Desk

## 1. Purpose

You are the development agent for the **AI Office IT Help Desk** project.

Your job is to implement the system according to the approved PRD and SRS.

### Source of Truth

Use these documents as the source of truth:

1. `AI_Office_IT_Help_Desk_PRD_FastAPI.md`
2. `AI_Office_IT_Help_Desk_SRS_No_Email.md`

Do not silently add, remove, or redesign product requirements.

**Important:** Everything in the approved PRD/SRS remains in scope except email notification infrastructure.

### Email Rule

Do NOT implement:
- Transactional email notifications
- Email notification API
- SMTP
- Email notification credentials
- Email notification retry/failure infrastructure

Keep:
- In-app notifications
- Push notifications

An IT support case about a user's office email problem is still valid.

---

# 2. Main Development Rule

## ALWAYS FOLLOW THIS ORDER

**Understand → Plan → Build → Run locally → Test → Fix → Verify → Move to next phase**

Do not jump directly to production deployment.

Required order:

**Build locally → Test locally → Complete E2E workflow → Prepare production configuration → Deploy**

The complete system must work locally before production work starts.

---

# 3. Important Engineering Principles

### 3.1 Real Product, Not Fake Prototype

Do NOT use:
- Hardcoded cases
- Fake dashboard numbers
- Fake login
- UI-only role permissions
- Static fake AI responses presented as real AI
- Disconnected screens
- Fake notifications
- Non-persistent case history

Every meaningful user action must create a real backend/business-state change and be visible to authorized users.

### 3.2 Backend Owns Business Logic

FastAPI must own:
- Authentication
- Authorization
- RBAC
- Case business rules
- Case lifecycle transitions
- Assignment rules
- SLA/risk rules
- Escalation rules
- AI integration
- Notifications
- Audit logging
- Validation
- Error handling

Flutter must not be trusted for security decisions.

### 3.3 Human Control Over AI

AI only provides assistance and recommendations.

Users must be able to:
- Accept
- Edit
- Reject
- Override

important AI recommendations.

Never present an AI assumption as a confirmed fact.

### 3.4 Core System Must Survive AI Failure

If the AI API fails, times out, returns invalid data, or is unavailable:
- Case creation must still work
- Case viewing must still work
- Assignment must still work
- Communication must still work
- Investigation must still work
- Resolution must still work

AI failure must not break core case management.

---

# 4. Technology Direction

Use the approved stack:

| Layer | Technology |
|---|---|
| Frontend | Flutter |
| Backend | Python + FastAPI |
| Database | PostgreSQL |
| Production DB | Supabase PostgreSQL |
| File Storage | Suitable external object/file storage |
| AI | External AI API |
| Authentication | Secure token-based authentication |
| Authorization | Backend RBAC |
| Notifications | In-app + Push |
| Scheduler | Lightweight FastAPI-compatible scheduler / scheduled API trigger |
| API | REST |

Version 1 must NOT require:
- Separate worker service
- Redis job queue
- Message queue
- n8n
- Heavy background-processing infrastructure
- Self-hosted SMTP

---

# 5. Roles

Implement exactly:
- `REQUESTER`
- `OPERATOR`
- `TEAM_LEAD`
- `MANAGER`
- `ADMIN`

RBAC must be enforced in FastAPI.

## Requester
- Create cases
- Upload evidence
- View own cases
- Respond to questions
- Receive updates
- Confirm/reject resolution

## Operator
- View/handle authorized cases
- Review AI analysis
- Accept/edit/reject AI recommendations
- Assign/reassign where authorized
- Communicate with requester
- Add internal notes
- Create tasks
- Investigate
- Update status
- Submit resolution
- Monitor SLA risks

## Team Lead
- Monitor team workload
- Review at-risk cases
- Review escalations
- Monitor operator workload
- Intervene/reassign where authorized

## Manager
- Organization-level operational dashboard
- Trends
- SLA performance
- Escalations
- Workload/performance
- Operational insights

## Admin
Manage:
- Users
- Teams
- Categories
- SLA/policies
- Organization settings
- Audit history

---

# 6. Case Lifecycle

Implement through backend business rules:

**Reported → Understood → Assigned → Investigating → Action Taken → Resolution Proposed → Confirmed → Closed**

Also support:
- Waiting for Information
- Escalated
- Duplicate
- Reopened
- Cancelled

Do not allow arbitrary status changes from the frontend.

Create a clear transition validation layer/service.

---

# 7. Core Case Data

A case must preserve:
- Original report
- Additional information
- Attachments/evidence
- AI analysis
- AI recommendations
- Assignment
- Conversations
- Internal notes
- Tasks
- Investigation updates
- SLA/deadline information
- Risk information
- Escalations
- Resolution
- Requester confirmation
- Timeline
- Audit history

Generate a unique case number such as `IT-10482`.

---

# 8. AI Features

Implement AI as a backend service/module.

Required capabilities:
1. Case analysis
2. Category suggestion
3. Severity suggestion
4. Priority suggestion
5. Missing-information detection
6. Related/duplicate detection
7. Suggested team/person
8. Recommended next action
9. Case summary
10. SLA/risk insight
11. Escalation suggestion
12. Communication drafting
13. Operational insights
14. Case-memory/context understanding

AI responses must be validated before being stored/used.

If an AI response is invalid, handle the error gracefully.

---

# 9. Communication

Implement case-linked communication:
- Requester ↔ Operator communication
- Information requests
- Requester responses
- AI-generated communication drafts
- Operator editing before sending

Internal notes must remain private to authorized staff.

Do not implement email notifications.

---

# 10. Tasks and Investigation

Cases must support:
- Multiple tasks
- Task owner/responsible person
- Task status
- Investigation observations
- Investigation actions
- Findings
- Evidence
- Follow-up requirements

All task and investigation activity must remain connected to the case.

---

# 11. SLA, Risk and Escalation

Implement:
- SLA/deadline information
- SLA monitoring
- Risk detection
- Deadline warnings
- Escalation

Risk logic should consider:
- Inactivity
- Repeated follow-ups
- Reassignments
- Missing information
- Approaching deadlines
- Reopening
- Unusually long resolution time

Risk warnings should explain why the case is at risk.

Use lightweight scheduling only.

---

# 12. Notifications

Implement:

### In-app
For important events:
- New case
- Assignment
- Requester response
- New task
- SLA warning
- Escalation
- Resolution
- Reopening

### Push
Use an appropriate push notification service.

Do not build email notification infrastructure.

Notification failure must not break core case management.

---

# 13. Resolution

Operator submits:
- What was done
- What was found
- Evidence
- Remaining issues

Requester can:
- Confirm resolution
- Reject resolution

If rejected:

**Resolution Proposed → Reopened**

Preserve all previous history.

A case should only be considered successfully handled when the actual outcome is confirmed.

---

# 14. Timeline and Audit

Maintain a chronological case timeline.

Track:
- Creation
- Assignment/reassignment
- Priority/status changes
- AI recommendations
- AI overrides
- Information requests
- Requester responses
- Task events
- Investigation updates
- Escalations
- Resolution
- Reopening
- Closure

Audit records should capture:
- Actor
- Action
- Entity/case
- Previous value where applicable
- New value where applicable
- Timestamp
- Relevant context

Normal users must not casually edit/delete audit records.

---

# 15. Dashboards

Build separate role-based dashboards.

### Requester
- Active cases
- Waiting-for-requester cases
- Recent updates
- Resolved cases
- Notifications
- Create case

### Operator
- New cases
- Assigned cases
- High-priority cases
- At-risk cases
- Waiting-for-information
- Escalated cases
- Recent updates
- Pending tasks

### Team Lead
- Team workload
- Priority distribution
- At-risk cases
- Escalations
- Unassigned cases
- Approaching deadlines
- Operator workload
- Resolution performance

### Manager
- Total cases
- Active cases
- Resolved cases
- SLA performance
- Average resolution time
- Escalations
- Reopened cases
- Trends
- Team/category performance
- Operational insights

### Admin
- Users
- Teams
- Categories
- SLA/policies
- Settings
- Audit history

Dashboards must use real database data.

---

# 16. Search

Support case search using:
- Case number
- Title
- Requester
- Category
- Status
- Team
- Assigned person
- Location

Natural-language discovery can remain a future enhancement unless explicitly required by the approved SRS.

---

# 17. File/Evidence Handling

Support:
- Screenshots
- Images
- Documents
- Other approved evidence types

Use appropriate external object/file storage for large files.

Secure file access through backend authorization.

Do not expose private storage credentials in Flutter.

---

# 18. Security Requirements

Implement:
- Secure authentication
- Password hashing
- Token-based authentication
- Backend authorization
- RBAC
- Protected APIs
- Secure file access
- Input validation
- Centralized exception handling
- Consistent API errors
- Logging
- Timeouts/retries where appropriate
- Secrets outside source code

Provide `.env.example`.

Never commit real:
- Passwords
- JWT secrets
- AI API keys
- Storage credentials
- Push credentials

Never log passwords, tokens, API keys, or sensitive credentials.

---

# 19. Project Audit Before Coding

Before making major changes:

1. Inspect the repository.
2. Identify frontend/backend structure.
3. Identify database setup.
4. Identify existing dependencies.
5. Identify existing APIs.
6. Identify existing UI.
7. Identify configuration files.
8. Identify incomplete features.
9. Identify broken features.
10. Compare existing implementation with PRD/SRS.

Create a short status report.

Do not rewrite working code unnecessarily.

---

# 20. Development Phases

## PHASE 0 — Repository Audit

Inspect the current project and produce:
- Current structure
- What already works
- What is incomplete
- What is broken
- What must be added
- What must be changed

### Gate
Do not proceed until the current project state is understood.

---

## PHASE 1 — Local Environment

Set up and verify:
- Python
- FastAPI
- PostgreSQL
- Flutter
- Dependencies
- Environment variables
- Database connection

Verify:
- Backend starts
- Frontend starts
- PostgreSQL connects
- `GET /api/health` works

### Gate
Local backend + frontend + database must work.

---

## PHASE 2 — Database and Backend Foundation

Implement:
- Database configuration
- Migrations
- Users
- Roles
- Teams
- Categories
- Cases
- Core case relationships
- Audit
- Notifications
- Remaining supporting entities required by the SRS

### Gate
Migrations must run successfully from a clean local database.

---

## PHASE 3 — Authentication and RBAC

Implement:
- Registration
- Login
- Token authentication
- Password hashing
- Current-user endpoint
- Role checks
- Backend authorization

Test all five roles.

### Gate
Changing the frontend or API request must not allow unauthorized access.

---

## PHASE 4 — Core Case Management

Implement:
- Create case
- Case number generation
- Case listing
- Case detail
- Case updates
- Case timeline
- Status transition validation
- Assignment
- Reassignment
- Filtering/search

### Gate
Create case in UI → save to PostgreSQL → reload → case still exists.

---

## PHASE 5 — Evidence, Communication, Tasks

Implement:
- File upload
- Secure file access
- Requester/operator communication
- Information requests
- Requester responses
- Internal notes
- Tasks
- Investigation updates

### Gate
A complete case must preserve related data after refresh/re-login.

---

## PHASE 6 — AI Integration

Implement through a backend AI service:
- Case analysis
- Classification
- Priority/severity
- Missing information
- Related/duplicate detection
- Assignment recommendation
- Next action
- Summary
- Risk insight
- Communication draft
- Escalation suggestion

Validate AI output.
Store useful AI results with the case.
Allow human override.

### Gate
Test:
1. AI success
2. AI invalid response
3. AI timeout
4. AI unavailable

Core case management must work in all cases.

---

## PHASE 7 — SLA, Risk, Escalation

Implement:
- SLA policies
- Deadline calculation
- Risk checks
- Deadline warnings
- Escalation rules
- Team Lead intervention
- Lightweight scheduler

### Gate
Create an at-risk case locally and verify correct detection and display.

---

## PHASE 8 — Notifications

Implement:
- Notification records
- In-app notification UI
- Push notification integration
- Notification triggers

Do not implement email.

### Gate
Trigger an important case event and verify the correct notification.

---

## PHASE 9 — Resolution and Reopening

Implement:
- Resolution submission
- Resolution evidence
- Requester confirmation
- Requester rejection
- Reopening
- Final closure
- Timeline/audit updates

### Gate
Test both:
- Operator resolves → Requester confirms → Closed
- Operator resolves → Requester rejects → Reopened

---

## PHASE 10 — Role Dashboards

Connect all dashboards to real backend data.

No hardcoded statistics.

Verify every role sees only authorized data.

### Gate
Real actions must change dashboard data.

---

## PHASE 11 — Full Local E2E Test

Create separate local accounts:
- Requester
- Operator
- Team Lead
- Manager
- Admin

Run:

1. Requester creates IT case.
2. Evidence is uploaded.
3. AI analysis is generated.
4. Operator reviews AI.
5. Operator accepts/edits/rejects recommendation.
6. Operator requests missing information.
7. Requester responds.
8. Operator creates investigation task.
9. Investigation completes.
10. Findings are recorded.
11. SLA/risk is tested.
12. Team Lead reviews/intervenes.
13. Operator submits resolution.
14. Requester confirms or rejects.
15. Manager reviews operational data.
16. Admin reviews audit history.

Use real persistent database state.

### Gate
Do not move to production until the complete workflow works locally.

---

# 21. Recommended Demo Scenario

Use:

> "My laptop is connected to Wi-Fi but I cannot access the internet."

Test:
1. Create case.
2. Upload screenshot.
3. AI analysis.
4. Network Support recommendation.
5. Operator review.
6. Missing location information.
7. Request information.
8. Requester responds.
9. Create investigation task.
10. Record findings.
11. SLA/risk monitoring.
12. Team Lead intervention if required.
13. Fix issue.
14. Upload resolution evidence.
15. Requester confirms.
16. Case closes.
17. Manager reviews analytics.
18. Admin reviews audit.

---

# 22. Testing Strategy

Every phase must include testing.

## Backend
Test:
- Authentication
- RBAC
- Permissions
- Validation
- Case lifecycle
- Assignment
- Tasks
- Investigation
- Resolution
- Reopening
- SLA
- Escalation
- Notifications
- Audit

## AI
Test:
- Success
- Invalid response
- Timeout
- Unavailable

## Frontend
Test:
- Loading states
- Empty states
- Error states
- Role-specific navigation
- Real API integration
- Refresh/reload persistence

## E2E
Use real accounts and real database state.

---

# 23. How the Agent Must Work

For every phase:

### Step 1 — Explain
Briefly state what will be implemented.

### Step 2 — Inspect
Check existing code before modifying it.

### Step 3 — Plan
List files/components that need changes.

### Step 4 — Implement
Make clean changes required by PRD/SRS.

### Step 5 — Run
Start required local services.

### Step 6 — Test
Run relevant automated tests and manually verify.

### Step 7 — Fix
Fix errors before continuing.

### Step 8 — Verify
Confirm the feature works end-to-end.

### Step 9 — Report
Give:
- What changed
- What was tested
- Test result
- Remaining issue
- Next phase

Then wait before starting a major new phase.

---

# 24. Do Not Do These Things

Never:
- Deploy before local E2E works.
- Replace working code without checking it.
- Create fake APIs.
- Hardcode database results.
- Put secrets in source code.
- Put AI API keys in Flutter.
- Implement RBAC only in Flutter.
- Treat AI recommendations as confirmed facts.
- Automatically merge duplicate cases only because AI says so.
- Allow arbitrary status changes.
- Hide backend errors behind fake success messages.
- Mark a feature complete just because its screen exists.
- Add unnecessary Redis/queues/workers/n8n.
- Add email notification infrastructure.
- Skip tests because the UI appears to work.

---

# 25. Definition of Done

A feature is complete only when:
- Backend logic exists.
- Database persistence works.
- API works.
- Authorization is enforced.
- Flutter UI is connected.
- Loading state exists.
- Error state exists.
- Empty state exists where relevant.
- Real data is displayed.
- User action changes backend state.
- Related screens reflect the change.
- Tests pass.
- No critical error remains.

A screen alone is NOT a completed feature.

---

# 26. Production Preparation — ONLY After Local Completion

Do not begin production deployment until the full local E2E workflow passes.

Then prepare:
- Production environment variables
- Production database configuration
- Supabase PostgreSQL
- File storage
- AI API configuration
- Push notification configuration
- Backend hosting
- Flutter production build
- CORS/security configuration
- Health endpoint
- Production logging
- Secure secrets

Do not add email infrastructure.

---

# 27. Final Product Goal

The finished product must behave as a real AI-powered IT case management platform.

Complete flow:

**Employee → Case → Evidence → AI Understanding → Assignment → Communication → Investigation → Tasks → SLA → Risk → Escalation → Resolution → Confirmation → Analytics → Audit**

Core principle:

> **The system manages the case.**
>
> **AI helps people understand and move the case forward.**
>
> **Humans remain responsible for important decisions.**

Build Version 1 simply, realistically, maintainably, and with production-quality thinking.

**LOCAL FIRST. TEST FIRST. E2E FIRST. DEPLOY LAST.**
