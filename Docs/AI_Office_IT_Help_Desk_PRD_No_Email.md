# AI Office IT Help Desk --- Product Requirements Document (PRD)

**Version:** 2.0\
**Product Stage:** College Project with Production-Ready Product
Ambition

## 1. Product Overview

AI Office IT Help Desk is an AI-powered IT case management platform for
organizations. Employees can report IT problems or service requests,
while IT teams can understand, assign, investigate, track, escalate, and
resolve cases.

The product is not just a basic ticketing system. AI is embedded into
the workflow for triage, summarization, missing-information detection,
related/duplicate detection, assignment recommendations, risk analysis,
communication drafting, and operational insights.

Humans remain responsible for important decisions.

## 2. Target Domain

The system is designed for Office IT Support.

Typical cases: - Laptop not working - Wi-Fi/network problems - Printer
problems - Email problems - Software installation - Account/access
requests - VPN problems - Monitor/display problems - Hardware issues -
Internal application problems

## 3. Target Users and RBAC

### Requester / Employee

-   Create cases
-   Upload screenshots/photos/documents
-   View own cases
-   Respond to questions
-   Receive updates
-   Confirm or reject resolution

### Operator / IT Support

-   View and handle cases
-   Review AI analysis
-   Accept/edit/reject AI recommendations
-   Assign cases
-   Communicate with requester
-   Add internal notes
-   Create tasks
-   Investigate
-   Update status
-   Submit resolution
-   Monitor SLA risks

### Team Lead

-   Monitor team workload
-   Review at-risk cases
-   Review escalations
-   Monitor operator workload
-   Intervene or reassign work

### Manager

-   Organization-wide dashboard
-   Trends
-   SLA performance
-   Escalations
-   Workload/performance
-   Operational insights

### Admin

-   Users
-   Teams
-   Categories
-   SLA/policies
-   Organization settings
-   Audit history

Roles: `REQUESTER`, `OPERATOR`, `TEAM_LEAD`, `MANAGER`, `ADMIN`

RBAC must be enforced by the FastAPI backend, not only by Flutter UI
visibility.

## 4. Core Case

A case may contain: - Original report - Additional information -
Attachments/evidence - AI analysis and recommendations - Assignment -
Conversations - Internal notes - Tasks - Investigation updates -
SLA/deadline information - Risk information - Escalations - Resolution -
Requester confirmation - Complete timeline - Audit history

## 5. Case Lifecycle

**Reported → Understood → Assigned → Investigating → Action Taken →
Resolution Proposed → Confirmed → Closed**

Temporary states: - Waiting for Information - Escalated - Duplicate -
Reopened - Cancelled

Backend business rules control valid state transitions.

## 6. Case Creation

Requester provides: - Title - Description - Optional category -
Office/location - Attachments/evidence

The system generates a unique case number such as `IT-10482`.

## 7. AI and Automation Features

### 7.1 Automatic AI Case Analysis

Analyze newly created cases and identify: - Likely category - Severity -
Priority - Missing information - Related cases - Suggested team -
Recommended next action

### 7.2 Automatic Case Summarization

Maintain an AI-generated summary as the case history grows: - What was
reported - What happened - What was confirmed - What remains
unresolved - Current blocker

### 7.3 Automatic Missing Information Detection

Detect information required to proceed and suggest questions for the
Operator to send.

### 7.4 Automatic Related/Duplicate Case Detection

Compare new cases with existing cases and identify potentially related
or duplicate cases. Final decision remains with the human Operator.
Cases must not be automatically merged.

### 7.5 Smart Assignment Recommendation

Analyze issue type, team responsibility, workload, availability,
location, and previous cases to recommend a team/person. Operator or
Team Lead can override it.

### 7.6 Automatic SLA and Risk Detection

Consider: - Inactivity - Repeated follow-ups - Reassignments - Missing
information - Approaching deadlines - Reopening - Unusually long
resolution time

Risk warnings should explain their reason.

### 7.7 Escalation Automation

Identify cases requiring higher-level attention because of
approaching/missed deadlines, serious issues, repeated unresolved
complaints, operator requests, or high risk.

### 7.8 AI-Generated Communication

Generate drafts for: - Information requests - Progress updates -
Resolution messages - Escalation summaries

The Operator reviews and edits before sending.

### 7.9 Automated Notifications

Important events: - New case - Assignment - Requester response - New
task - SLA warning - Escalation - Resolution - Reopening

Channels: - In-app notifications - Push notifications

### 7.10 Automatic Timeline and Audit Logging

Automatically record: - Creation - Assignment/reassignment -
Priority/status changes - AI recommendations - AI overrides -
Information requests - Task events - Escalations - Resolution -
Reopening - Closure

### 7.11 AI-Powered Operational Insights

Analyze multiple cases for patterns and trends, such as repeated
network/printer issues, location trends, unusually long resolution
times, and repeated escalations.

## 8. Human Control and AI Trust

AI assists users; it does not control the entire workflow.

Users must be able to accept, edit, reject, or override important AI
recommendations.

AI must distinguish recommendations from confirmed facts and communicate
uncertainty when appropriate.

If AI is unavailable, the core application must continue to support: -
Case creation - Case viewing - Assignment - Updates - Communication -
Investigation - Resolution

## 9. Communication, Investigation and Tasks

Requester and Operator communication stays attached to the case.

Internal notes must never be visible to Requesters.

Operators can record observations, actions, findings, evidence, and
follow-up requirements.

Cases can contain multiple tasks with a responsible person and status.

## 10. Resolution

Operator submits: - What was done - What was found - Evidence -
Remaining issues

Requester can confirm resolution or report that the problem is not
resolved. Rejected resolutions reopen the case while preserving history.

## 11. Dashboards

### Requester

Active cases, waiting-for-requester cases, recent updates, resolved
cases, notifications, create-case action.

### Operator

New, assigned, high-priority, at-risk, waiting-for-information,
escalated cases, recent updates, pending tasks.

### Team Lead

Team workload, priorities, at-risk cases, escalations, unassigned cases,
deadlines, operator workload, resolution performance.

### Manager

Total/active/resolved cases, SLA performance, average resolution time,
escalations, reopened cases, trends, team/category performance,
operational insights.

### Admin

Users, teams, categories, SLA/policies, organization settings, audit
logs.

## 12. File Storage

Support case evidence such as images, screenshots, and documents.

Files must respect RBAC. Large binary files should be stored in
object/file storage rather than directly in PostgreSQL.

## 13. Technical Stack

### Frontend

**Flutter** --- primary mobile application.

### Backend

**Python + FastAPI** --- main backend/API.

FastAPI owns: - REST APIs - Authentication - RBAC - Business logic -
Case workflow - AI integration - SLA engine - Escalation rules -
Notifications - Audit logging - Lightweight scheduling - Validation -
Error handling

### Database

**PostgreSQL**, with **Supabase PostgreSQL** as the preferred low-cost
production option.

### File Storage

Suitable external object/file storage.

### AI

External AI APIs accessed only through FastAPI. AI secrets must never be
exposed in Flutter.

## 14. Architecture

``` text
Flutter Mobile App
        |
      HTTPS
        |
        v
FastAPI Backend
        |
        +-- Authentication / RBAC
        +-- Case Management
        +-- Business Logic
        +-- AI Integration
        +-- SLA / Escalation
        +-- Notifications
        +-- Audit Trail
        +-- Lightweight Scheduler
        |
        +--------> PostgreSQL / Supabase
        |
        +--------> File Storage

External Services
        +--------> AI API
            +--------> Push Notification Service
```

## 15. Important Architecture Constraint --- No Worker Architecture

This project does **not** contain heavy background processing,
long-running tasks, or heavy queued jobs.

Therefore Version 1 must **not** use: - Separate Worker Service -
Message Queue - n8n - Redis job queue - Dedicated background-processing
infrastructure

Normal FastAPI API requests, lightweight asynchronous operations, and
lightweight scheduling are sufficient.

A separate worker architecture may only be considered in a future
version if genuinely heavy/long-running workloads appear.

## 16. Lightweight Scheduling

Time-based operations such as: - SLA checks - Risk checks - Deadline
warnings - Lightweight notification triggers

may use a lightweight scheduler compatible with the FastAPI application.

The scheduler must remain lightweight and must not block API requests.

Where useful for free-tier deployment, scheduled HTTP/API triggers may
be used instead.

## 17. Authentication and Security

Requirements: - Secure authentication - Password hashing - Token-based
authentication - Backend authorization - RBAC - Protected APIs - Secure
file access - Input validation - Error handling - Secrets outside source
code

Flutter must never contain private server credentials or AI API keys.

## 18. Environment Variables and Secrets

Provide `.env.example`.

Store configuration such as: - Database URL - Auth/JWT secrets - AI API
keys - Storage credentials - Push notification credentials

Never commit real secrets to Git.

## 19. Error Handling and Reliability

Provide: - Centralized FastAPI exception handling - Request validation -
Consistent API error format - Logging - Suitable retry handling -
Timeout handling - AI failure handling - Database error handling

External-service failures must not unnecessarily break core case
management.

## 20. Logging and Monitoring

Log important technical events including: - Authentication failures -
API errors - AI failures - Notification failures - Scheduler execution -
SLA processing errors - Database errors - Important system events

Never log passwords, tokens, API keys, or sensitive credentials.

Provide: `GET /api/health`

## 21. Testing

### Unit Tests

Business logic, SLA calculations, escalation rules, validation,
permissions.

### API/Integration Tests

Authentication, RBAC, case creation, assignment, communication, tasks,
investigation, resolution, reopening, notifications, audit logging.

### AI Integration Tests

Successful response, invalid response, timeout, service unavailable.

Core case functionality must continue if AI fails.

### End-to-End Tests

Use separate real accounts for Requester, Operator, Team Lead, Manager,
and Admin.

## 22. Real Multi-User End-to-End Test

1.  Requester creates an IT case.
2.  Uploads evidence.
3.  AI analysis is generated.
4.  Operator reviews recommendations.
5.  Operator accepts/edits/rejects them.
6.  Operator requests missing information.
7.  Requester responds.
8.  Operator creates investigation task.
9.  Investigation is completed.
10. Findings are recorded.
11. SLA/risk condition is tested.
12. Team Lead reviews/intervenes.
13. Operator submits resolution.
14. Requester confirms or rejects.
15. Manager reviews operational data.
16. Admin reviews audit trail.

All actions must use real backend state and persistent database data.

## 23. Recommended Demo Scenario --- Office Wi-Fi Issue

Employee reports:

> "My laptop is connected to Wi-Fi but I cannot access the internet."

Flow: 1. Requester creates case. 2. Screenshot uploaded. 3. AI analyzes
the case. 4. AI suggests Network Support. 5. Operator reviews it. 6. AI
identifies missing office/location information. 7. Operator asks
Requester. 8. Requester responds. 9. Operator creates investigation
task. 10. Investigation is performed. 11. Findings are recorded. 12.
SLA/risk monitoring runs. 13. Team Lead intervenes if required. 14.
Issue is fixed. 15. Resolution evidence is uploaded. 16. Requester
confirms. 17. Case closes. 18. Manager reviews analytics. 19. Admin
reviews audit history.

## 24. Local Development First

Development order:

**Build locally → Test locally → Complete E2E workflow → Prepare
production configuration → Deploy**

The complete system must work locally before production deployment.

## 25. Production Deployment

Use free/low-cost services where practical: - Flutter production build -
Compatible low-cost/free backend hosting - Supabase PostgreSQL -
Suitable file storage - External AI API - Push notification service

The architecture must account for free-tier limitations from the
beginning.

## 26. Free/Low-Cost Deployment Constraints

Do not depend on: - Dedicated worker hosting - Heavy message queues -
Long-running background jobs - Paid infrastructure for core
functionality

If AI is unavailable, core case management must continue.

## 27. Data and Business Logic

Use real persistent data.

Do not use: - Hardcoded cases - Fake dashboard numbers - Fake login
behavior - Static AI responses presented as real AI - Disconnected
screens - UI-only role permissions - Fake notifications

FastAPI must own the real business logic.

User actions must create real database/business-state changes visible to
authorized users.

## 28. Audit Trail

Audit records should capture appropriate information such as: -
Actor/user - Action - Entity/case - Previous value where appropriate -
New value where appropriate - Timestamp - Relevant context

Normal users must not be able to casually edit or delete audit records.

## 29. MVP

### Authentication

Registration, login, RBAC, profile.

### Requester

Create case, upload evidence, view cases, answer questions, receive
updates, confirm/reject resolution.

### Operator

View cases, AI analysis, assignment, communication, internal notes,
tasks, investigation, status updates, resolution.

### Team Lead

Team workload, at-risk cases, escalations, intervention.

### Manager

Operational dashboard, trends, performance, important cases, operational
insights.

### Admin

Users, teams, categories, SLA/policies, settings, audit history.

### AI

Case analysis, classification, priority/severity, summary, missing
information, related/duplicate detection, assignment recommendation,
next action, risk analysis, communication drafting, operational
insights.

### Workflow

Case lifecycle, SLA awareness, escalation, notifications, resolution
confirmation, reopening, timeline, audit history.

## 30. Future Enhancements

-   Voice-based case reporting
-   Advanced document understanding
-   Semantic search
-   Predictive workload management
-   Organization-specific AI knowledge
-   Advanced analytics
-   Custom workflows
-   Additional communication channels
-   Automated reports
-   Mobile field operations
-   Multi-organization SaaS
-   Subscription/billing

Worker architecture, queues, or workflow automation platforms may only
be considered later if genuinely required by future workload.

## 31. Product Quality Bar

The final product should have: - Coherent UX - Clear role-based
journeys - Real persistent data - Meaningful AI - Complete case
lifecycle - Loading/error/empty states - Useful notifications -
Traceable actions - Consistent terminology - Professional UI - Real
multi-user behavior - Proper FastAPI business logic - Secure
configuration - Basic monitoring - Reliable error handling - Tested
workflows

A feature is not complete simply because its screen exists. Meaningful
actions must produce real effects throughout the system.

## 32. Product Success Criteria

The project should demonstrate that it can: 1. Capture a real IT
problem. 2. Preserve complete case history. 3. Allow multiple roles to
collaborate. 4. Use AI meaningfully. 5. Identify what needs to happen
next. 6. Detect cases requiring attention. 7. Keep employees informed.
8. Reduce forgotten cases. 9. Allow human override of AI. 10. Provide
accountability. 11. Confirm actual resolution. 12. Provide operational
visibility. 13. Continue when AI is unavailable. 14. Operate without a
separate worker architecture. 15. Complete a real multi-user E2E
workflow. 16. Run locally before production. 17. Deploy using
free/low-cost infrastructure where practical.

## 33. Final Product Definition

**AI Office IT Help Desk** manages the complete lifecycle of office IT
problems and service requests.

**Employee → Case → Evidence → AI Understanding → Assignment →
Communication → Investigation → Tasks → SLA → Risk → Escalation →
Resolution → Confirmation → Analytics → Audit**

The defining principle is:

> **The system manages the case.\
> AI helps people understand and move the case forward.\
> Humans remain responsible for important decisions.**

## 34. Implementation Principle

Keep Version 1 simple, realistic, maintainable, and production-minded.

Use:

**Flutter + Python FastAPI + PostgreSQL/Supabase + File Storage + AI
APIs + Lightweight Scheduler + Notification/Email Services**

Build locally first, validate with real multi-user end-to-end testing,
and then deploy.

**No separate Worker Architecture is required for Version 1.**
