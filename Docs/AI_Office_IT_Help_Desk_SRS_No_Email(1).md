# AI Office IT Help Desk --- Software Requirements Specification (SRS)

**Version:** 1.0\
**Based On:** AI Office IT Help Desk PRD --- No Email\
**Product Stage:** College Project with Production-Ready Product
Ambition

------------------------------------------------------------------------

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification (SRS) defines the functional,
technical, security, data, workflow, testing, and quality requirements
for the **AI Office IT Help Desk**.

The system is an AI-powered IT case management platform for
organizations. Employees can report IT problems or service requests,
while IT teams can understand, assign, investigate, track, escalate, and
resolve cases.

This SRS preserves the scope of the corresponding PRD. The system
includes **in-app and push notifications only**. Email notification
infrastructure, transactional email APIs, SMTP, and email-service
credentials are out of scope.

### 1.2 Product Scope

The product manages the complete lifecycle of office IT problems and
service requests:

**Employee → Case → Evidence → AI Understanding → Assignment →
Communication → Investigation → Tasks → SLA → Risk → Escalation →
Resolution → Confirmation → Analytics → Audit**

The product is not only a basic ticketing system. AI is embedded into
the workflow to assist with triage, summarization, missing-information
detection, related/duplicate detection, assignment recommendations, risk
analysis, communication drafting, and operational insights.

Humans remain responsible for important decisions.

### 1.3 Target Domain

The system is designed for Office IT Support.

Typical cases include:

-   Laptop not working
-   Wi-Fi/network problems
-   Printer problems
-   Email problems
-   Software installation
-   Account/access requests
-   VPN problems
-   Monitor/display problems
-   Hardware issues
-   Internal application problems

"Email problems" above refers to an office IT support issue and is not
an email notification feature.

### 1.4 Definitions

  -----------------------------------------------------------------------
  Term                                Meaning
  ----------------------------------- -----------------------------------
  Case                                A tracked IT problem or service
                                      request

  Requester                           Employee who creates or owns a case

  Operator                            IT support user handling cases

  Team Lead                           User responsible for monitoring and
                                      intervening in team work

  Manager                             User with organization-level
                                      operational visibility

  Admin                               User responsible for system and
                                      organization configuration

  RBAC                                Role-Based Access Control

  SLA                                 Service Level Agreement /
                                      configured service deadline rules

  Risk                                A condition indicating that a case
                                      may require attention

  Escalation                          Raising a case for higher-level
                                      attention

  AI Recommendation                   A suggestion produced by AI and not
                                      automatically treated as a
                                      confirmed fact

  Timeline                            Chronological case story and
                                      meaningful events

  Audit Trail                         Traceable record of important
                                      actions and changes
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 2. Overall System Description

## 2.1 Product Perspective

The application consists of a Flutter mobile client, a FastAPI backend,
PostgreSQL database storage, external file/object storage, external AI
APIs, push notification support, and lightweight scheduling.

The FastAPI backend is the owner of business rules and persistent system
state.

## 2.2 System Architecture

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

## 2.3 User Roles

The system shall support the following roles:

`REQUESTER`, `OPERATOR`, `TEAM_LEAD`, `MANAGER`, `ADMIN`

### Requester / Employee

The Requester shall be able to:

-   Create cases
-   Upload screenshots, photos, and documents
-   View authorized own cases
-   Respond to information requests
-   Receive updates through supported notifications
-   Confirm or reject a proposed resolution

### Operator / IT Support

The Operator shall be able to:

-   View and handle authorized cases
-   Review AI analysis
-   Accept, edit, reject, or override AI recommendations
-   Assign or reassign cases according to permissions
-   Communicate with Requesters
-   Add internal notes
-   Create and update tasks
-   Record investigation activity and findings
-   Update case status through valid workflow transitions
-   Submit resolutions
-   Monitor SLA and risk information

### Team Lead

The Team Lead shall be able to:

-   Monitor team workload
-   Review at-risk cases
-   Review escalations
-   Monitor operator workload
-   Intervene or reassign work according to authorization

### Manager

The Manager shall have organization-level operational visibility for:

-   Total, active, and resolved cases
-   Trends
-   SLA performance
-   Escalations
-   Workload and performance
-   Operational insights

### Admin

The Admin shall manage:

-   Users
-   Teams
-   Categories
-   SLA/policies
-   Organization settings
-   Audit history

------------------------------------------------------------------------

# 3. Functional Requirements

## 3.1 Authentication and Authorization

### FR-AUTH-001 Registration and Login

The system shall provide secure user authentication for supported users.

### FR-AUTH-002 Password Security

Passwords shall not be stored as plain text. Password handling shall use
secure password hashing.

### FR-AUTH-003 Token-Based Authentication

The backend shall use token-based authentication for protected API
access.

### FR-AUTH-004 Protected APIs

Protected backend endpoints shall require valid authentication.

### FR-AUTH-005 Backend-Enforced RBAC

Authorization shall be enforced by the FastAPI backend. Hiding a feature
in the Flutter UI shall not be treated as authorization.

### FR-AUTH-006 Role Access

The backend shall verify that the authenticated user has permission
before allowing access to protected resources or actions.

### FR-AUTH-007 Profile

Authenticated users shall have access to their authorized profile
information.

------------------------------------------------------------------------

## 3.2 Case Management

### FR-CASE-001 Create Case

A Requester shall be able to create a case containing:

-   Title
-   Description
-   Optional category
-   Office/location
-   Optional attachments/evidence

### FR-CASE-002 Unique Case Number

The system shall generate a unique case identifier, such as `IT-10482`.

### FR-CASE-003 Persistent Case State

Created cases shall be stored using persistent backend/database state
and shall not exist only in the client UI.

### FR-CASE-004 Case Information

A case shall support relevant information including:

-   Original report
-   Additional information
-   Attachments/evidence
-   AI analysis and recommendations
-   Assignment
-   Conversations
-   Internal notes
-   Tasks
-   Investigation updates
-   SLA/deadline information
-   Risk information
-   Escalations
-   Resolution
-   Requester confirmation
-   Complete timeline
-   Audit history

### FR-CASE-005 Authorized Case Visibility

The backend shall return case information only to users authorized to
access it.

------------------------------------------------------------------------

## 3.3 Case Lifecycle

### FR-LIFE-001 Primary Lifecycle

The system shall support the following primary case journey:

**Reported → Understood → Assigned → Investigating → Action Taken →
Resolution Proposed → Confirmed → Closed**

### FR-LIFE-002 Temporary or Alternate States

The system shall support relevant states including:

-   Waiting for Information
-   Escalated
-   Duplicate
-   Reopened
-   Cancelled

### FR-LIFE-003 Valid State Transitions

Backend business rules shall control valid case state transitions.

### FR-LIFE-004 Reopening

A rejected resolution shall reopen the case while preserving previous
case history.

### FR-LIFE-005 History Preservation

Status changes shall not destroy the historical story of the case.

------------------------------------------------------------------------

## 3.4 AI and Automation

### FR-AI-001 Automatic Case Analysis

For a newly created case, the system shall support AI analysis for:

-   Likely category
-   Severity
-   Priority
-   Missing information
-   Related cases
-   Suggested team
-   Recommended next action

### FR-AI-002 Case Summary

The system shall support an AI-generated summary as case history grows,
covering:

-   What was reported
-   What happened
-   What was confirmed
-   What remains unresolved
-   Current blocker

### FR-AI-003 Missing Information Detection

The system shall support detection of information required to proceed
and suggested questions for the Operator.

### FR-AI-004 Related and Duplicate Detection

The system shall support identification of potentially related or
duplicate cases.

The system shall not automatically merge cases based only on an AI
recommendation. The final decision shall remain with the human Operator.

### FR-AI-005 Assignment Recommendation

The system shall support AI-assisted assignment recommendations based on
relevant available factors such as:

-   Issue type
-   Team responsibility
-   Workload
-   Availability
-   Location
-   Previous cases

An Operator or Team Lead shall be able to override a recommendation.

### FR-AI-006 Risk Analysis

The system shall support AI/system analysis of conditions such as:

-   Inactivity
-   Repeated follow-ups
-   Reassignments
-   Missing information
-   Approaching deadlines
-   Reopening
-   Unusually long resolution time

Risk warnings shall explain the relevant reason.

### FR-AI-007 Communication Drafting

The system shall support AI-generated drafts for:

-   Information requests
-   Progress updates
-   Resolution messages
-   Escalation summaries

The Operator shall review and may edit the draft before sending.

### FR-AI-008 Operational Insights

The system shall support analysis of multiple cases to identify patterns
and trends, including examples such as:

-   Repeated network or printer issues
-   Location trends
-   Unusually long resolution times
-   Repeated escalations

### FR-AI-009 Human Control

Important AI recommendations shall support human acceptance, editing,
rejection, or override.

### FR-AI-010 Recommendation vs Confirmed Fact

The system shall distinguish AI recommendations from confirmed facts.

### FR-AI-011 AI Unavailability

If the AI service is unavailable, the core application shall continue to
support:

-   Case creation
-   Case viewing
-   Assignment
-   Updates
-   Communication
-   Investigation
-   Resolution

AI failure shall not unnecessarily make core case management
unavailable.

------------------------------------------------------------------------

## 3.5 Communication and Internal Notes

### FR-COMM-001 Case-Linked Communication

Requester and Operator communication shall remain attached to the
relevant case.

### FR-COMM-002 Information Requests

An Operator shall be able to request missing or additional information
from the Requester.

### FR-COMM-003 Requester Responses

A Requester shall be able to respond to case-related questions through
the application.

### FR-COMM-004 Internal Notes

Authorized staff shall be able to create internal notes.

### FR-COMM-005 Internal Note Privacy

Internal notes shall never be visible to Requesters.

------------------------------------------------------------------------

## 3.6 Investigation and Tasks

### FR-TASK-001 Investigation Records

Operators shall be able to record:

-   Observations
-   Actions
-   Findings
-   Evidence
-   Follow-up requirements

### FR-TASK-002 Multiple Tasks

A case shall support multiple tasks.

### FR-TASK-003 Task Responsibility

Each task shall support a responsible person where applicable.

### FR-TASK-004 Task Status

Each task shall support status tracking.

### FR-TASK-005 Case Relationship

Tasks and investigation activity shall remain associated with the
relevant case.

------------------------------------------------------------------------

## 3.7 Assignment

### FR-ASSIGN-001 Assignment

Authorized users shall be able to assign cases according to backend
permissions.

### FR-ASSIGN-002 Reassignment

Authorized users shall be able to reassign cases.

### FR-ASSIGN-003 Assignment Traceability

Assignment and reassignment events shall be represented in appropriate
case history and audit information.

------------------------------------------------------------------------

## 3.8 SLA, Risk, and Escalation

### FR-SLA-001 SLA Information

The system shall support SLA/deadline information associated with cases
according to configured policies.

### FR-SLA-002 SLA Monitoring

The system shall support time-based SLA checks.

### FR-SLA-003 Risk Monitoring

The system shall support risk checks and risk warnings.

### FR-SLA-004 Deadline Warnings

The system shall support deadline warnings.

### FR-SLA-005 Escalation

The system shall support escalation based on relevant conditions,
including:

-   Approaching or missed deadlines
-   Serious issues
-   Repeated unresolved complaints
-   Operator requests
-   High-risk conditions

### FR-SLA-006 Human Intervention

Team Leads shall be able to review and intervene in authorized escalated
or at-risk cases.

### FR-SLA-007 Lightweight Scheduling

Time-based checks may use a lightweight scheduler compatible with the
FastAPI application.

The scheduler shall remain lightweight and shall not block normal API
requests.

Scheduled HTTP/API triggers may be used where useful for free-tier
deployment.

------------------------------------------------------------------------

## 3.9 Notifications

### FR-NOTIF-001 Notification Events

The system shall support notifications for important events including:

-   New case
-   Assignment
-   Requester response
-   New task
-   SLA warning
-   Escalation
-   Resolution
-   Reopening

### FR-NOTIF-002 Supported Channels

Version 1 notification channels shall include:

-   In-app notifications
-   Push notifications

### FR-NOTIF-003 Notification Reliability

Notification failures shall be handled without unnecessarily breaking
core case management.

### FR-NOTIF-004 No Email Notification Requirement

Version 1 shall not require transactional email notifications, an email
API, or SMTP infrastructure.

------------------------------------------------------------------------

## 3.10 Resolution and Confirmation

### FR-RES-001 Resolution Submission

The Operator shall be able to submit:

-   What was done
-   What was found
-   Evidence
-   Remaining issues

### FR-RES-002 Requester Confirmation

The Requester shall be able to confirm the proposed resolution.

### FR-RES-003 Resolution Rejection

The Requester shall be able to report that the problem is not resolved.

### FR-RES-004 Reopen on Rejection

A rejected resolution shall reopen the case while preserving its
previous history.

### FR-RES-005 Closure

A case shall support closure after the applicable resolution and
confirmation workflow.

------------------------------------------------------------------------

## 3.11 Timeline

### FR-TIME-001 Case Story

The system shall maintain a chronological representation of meaningful
case activity.

### FR-TIME-002 Recorded Events

The timeline shall support relevant events including:

-   Case creation
-   Assignment/reassignment
-   Priority/status changes
-   AI recommendations
-   AI overrides
-   Information requests
-   Requester responses
-   Task events
-   Investigation updates
-   Escalations
-   Resolution
-   Reopening
-   Closure

------------------------------------------------------------------------

## 3.12 Audit Trail

### FR-AUDIT-001 Audit Records

The system shall record appropriate audit information including:

-   Actor/user
-   Action
-   Entity/case
-   Previous value where appropriate
-   New value where appropriate
-   Timestamp
-   Relevant context

### FR-AUDIT-002 AI Decision Traceability

Where appropriate, audit information shall support traceability of AI
recommendations and human overrides.

### FR-AUDIT-003 Audit Protection

Normal users shall not be able to casually edit or delete audit records.

### FR-AUDIT-004 Admin Access

Admins shall have access to authorized audit history.

------------------------------------------------------------------------

## 3.13 Dashboards

### FR-DASH-001 Requester Dashboard

The Requester dashboard shall support:

-   Active cases
-   Waiting-for-requester cases
-   Recent updates
-   Resolved cases
-   Notifications
-   Create-case action

### FR-DASH-002 Operator Dashboard

The Operator dashboard shall support:

-   New cases
-   Assigned cases
-   High-priority cases
-   At-risk cases
-   Waiting-for-information cases
-   Escalated cases
-   Recent updates
-   Pending tasks

### FR-DASH-003 Team Lead Dashboard

The Team Lead dashboard shall support:

-   Team workload
-   Priorities
-   At-risk cases
-   Escalations
-   Unassigned cases
-   Deadlines
-   Operator workload
-   Resolution performance

### FR-DASH-004 Manager Dashboard

The Manager dashboard shall support:

-   Total cases
-   Active cases
-   Resolved cases
-   SLA performance
-   Average resolution time
-   Escalations
-   Reopened cases
-   Trends
-   Team/category performance
-   Operational insights

### FR-DASH-005 Admin Dashboard

The Admin dashboard shall support access to:

-   Users
-   Teams
-   Categories
-   SLA/policies
-   Organization settings
-   Audit logs

Dashboard information shall use real persistent backend data rather than
hardcoded demonstration values.

------------------------------------------------------------------------

## 3.14 File Storage

### FR-FILE-001 Supported Evidence

The system shall support case evidence including:

-   Images
-   Screenshots
-   Documents

### FR-FILE-002 File Access Control

File access shall respect backend authorization and RBAC.

### FR-FILE-003 Storage Strategy

Large binary files shall be stored in suitable object/file storage
rather than directly in PostgreSQL where appropriate.

### FR-FILE-004 Evidence Association

Uploaded evidence shall remain associated with the relevant case or
relevant case activity.

------------------------------------------------------------------------

# 4. Data Requirements

## 4.1 Persistent Data

The system shall use real persistent data for core application
functionality.

The implementation shall not depend on:

-   Hardcoded cases
-   Fake dashboard numbers
-   Fake login behavior
-   Static AI responses presented as real AI
-   Disconnected screens
-   UI-only role permissions
-   Fake notifications

## 4.2 Core Logical Entities

The exact database schema shall be designed during implementation, but
the system shall support logical data for:

-   Users
-   Roles
-   Teams
-   Cases
-   Categories
-   Assignments
-   Conversations
-   Internal Notes
-   Tasks
-   Investigation Updates
-   Attachments/Evidence
-   AI Analyses
-   AI Recommendations
-   SLA/Policy Information
-   Risk Records
-   Escalations
-   Resolutions
-   Requester Confirmations
-   Notifications
-   Timeline Events
-   Audit Records
-   Organization Settings

## 4.3 Data Relationships

The system shall preserve meaningful relationships between case data. A
case may be associated with multiple communications, notes, tasks,
investigation updates, attachments, AI analyses, timeline events,
notifications, and audit records.

## 4.4 Data Ownership and Visibility

Data access shall be controlled by backend authorization rules.
Requesters shall not gain access to internal notes or other protected
information simply by modifying client-side requests.

------------------------------------------------------------------------

# 5. External Interface Requirements

## 5.1 Mobile Application Interface

The primary user application shall be built using Flutter.

The application shall provide coherent role-based user journeys and
appropriate:

-   Loading states
-   Error states
-   Empty states
-   Professional UI
-   Consistent terminology

## 5.2 Backend API Interface

The FastAPI backend shall expose REST APIs required for the product.

The backend shall own:

-   Authentication
-   RBAC
-   Business logic
-   Case workflow
-   AI integration
-   SLA engine
-   Escalation rules
-   Notifications
-   Audit logging
-   Lightweight scheduling
-   Validation
-   Error handling

## 5.3 Health Interface

The backend shall provide:

`GET /api/health`

## 5.4 AI Interface

External AI APIs shall be accessed through FastAPI.

AI API keys and private AI credentials shall not be exposed in the
Flutter application.

## 5.5 Push Notification Interface

The system may integrate with a suitable push notification service for
supported push notification delivery.

------------------------------------------------------------------------

# 6. Non-Functional Requirements

## 6.1 Security

### NFR-SEC-001

The system shall provide secure authentication and backend
authorization.

### NFR-SEC-002

Passwords shall use secure hashing.

### NFR-SEC-003

Protected APIs shall require valid authentication and authorization.

### NFR-SEC-004

RBAC shall be enforced by the backend.

### NFR-SEC-005

File access shall be secured according to authorization requirements.

### NFR-SEC-006

Input validation shall be performed by the backend.

### NFR-SEC-007

Private server credentials and AI API keys shall not be stored in
Flutter.

### NFR-SEC-008

Secrets shall not be committed to Git.

------------------------------------------------------------------------

## 6.2 Environment Configuration

The project shall provide a `.env.example`.

Configuration may include:

-   Database URL
-   Authentication/JWT secrets
-   AI API keys
-   Storage credentials
-   Push notification credentials

Real secrets shall not be committed to source control.

------------------------------------------------------------------------

## 6.3 Reliability and Error Handling

The backend shall provide:

-   Centralized FastAPI exception handling
-   Request validation
-   Consistent API error format
-   Logging
-   Suitable retry handling where applicable
-   Timeout handling
-   AI failure handling
-   Notification failure handling
-   Database error handling

Failures of external services shall not unnecessarily break core case
management.

------------------------------------------------------------------------

## 6.4 Logging and Monitoring

The system shall log important technical events including:

-   Authentication failures
-   API errors
-   AI failures
-   Notification failures
-   Scheduler execution
-   SLA processing errors
-   Database errors
-   Important system events

The system shall never log:

-   Passwords
-   Authentication tokens
-   API keys
-   Sensitive credentials

------------------------------------------------------------------------

## 6.5 Maintainability

Version 1 shall remain simple, realistic, maintainable, and
production-minded.

The implementation should avoid unnecessary infrastructure that does not
support the stated Version 1 requirements.

------------------------------------------------------------------------

# 7. Technology Requirements

  -----------------------------------------------------------------------
  Layer                               Required Technology / Direction
  ----------------------------------- -----------------------------------
  Frontend                            Flutter

  Backend                             Python + FastAPI

  Database                            PostgreSQL

  Preferred low-cost production       Supabase PostgreSQL
  database                            

  File storage                        Suitable external object/file
                                      storage

  AI                                  External AI APIs accessed through
                                      FastAPI

  Authentication                      Secure token-based authentication

  Authorization                       FastAPI backend-enforced RBAC

  Notifications                       In-app notifications and push
                                      notifications

  Scheduling                          Lightweight FastAPI-compatible
                                      scheduler or suitable scheduled
                                      HTTP/API triggers

  API style                           REST APIs

  Version 1 architecture              No separate worker architecture
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 8. Architecture Constraints

## 8.1 No Separate Worker Architecture

Version 1 shall not use unnecessary heavy background-processing
infrastructure.

The project shall not require:

-   Separate Worker Service
-   Message Queue
-   n8n
-   Redis job queue
-   Dedicated background-processing infrastructure

Normal FastAPI API requests, lightweight asynchronous operations, and
lightweight scheduling are sufficient for Version 1.

A separate worker architecture may only be considered in a future
version if genuinely heavy or long-running workloads require it.

## 8.2 Free/Low-Cost Deployment Constraints

The architecture shall account for practical free-tier limitations.

The system shall not depend on:

-   Dedicated worker hosting
-   Self-hosted SMTP
-   Heavy message queues
-   Long-running background jobs
-   Paid infrastructure for core functionality

The system shall support in-app and push notifications without requiring
email notification infrastructure.

## 8.3 AI Service Independence

The application shall continue core case management when AI is
unavailable.

------------------------------------------------------------------------

# 9. Testing Requirements

## 9.1 Unit Testing

Unit tests shall cover relevant business logic including:

-   SLA calculations
-   Escalation rules
-   Validation
-   Permissions

## 9.2 API and Integration Testing

API/integration tests shall cover:

-   Authentication
-   RBAC
-   Case creation
-   Assignment
-   Communication
-   Tasks
-   Investigation
-   Resolution
-   Reopening
-   Notifications
-   Audit logging

## 9.3 AI Integration Testing

AI integration testing shall cover:

-   Successful response
-   Invalid response
-   Timeout
-   Service unavailable

Core case functionality shall continue when AI fails.

## 9.4 End-to-End Testing

End-to-end testing shall use separate real accounts for:

-   Requester
-   Operator
-   Team Lead
-   Manager
-   Admin

All tested actions shall use real backend state and persistent database
data.

------------------------------------------------------------------------

# 10. Required End-to-End Workflow

The system shall support validation of the following connected workflow:

1.  Requester creates an IT case.
2.  Requester uploads evidence.
3.  AI analysis is generated when available.
4.  Operator reviews AI recommendations.
5.  Operator accepts, edits, rejects, or overrides recommendations as
    appropriate.
6.  Operator requests missing information.
7.  Requester responds.
8.  Operator creates an investigation task.
9.  Investigation is completed.
10. Findings are recorded.
11. SLA/risk condition is tested.
12. Team Lead reviews or intervenes when required.
13. Operator submits a resolution.
14. Requester confirms or rejects the resolution.
15. Manager reviews operational data.
16. Admin reviews the audit trail.

The workflow shall represent connected system behavior. A feature shall
not be considered complete merely because its screen exists.

------------------------------------------------------------------------

# 11. Recommended Demonstration Scenario

## Office Wi-Fi Issue

The Requester reports:

> "My laptop is connected to Wi-Fi but I cannot access the internet."

The demonstration workflow shall support:

1.  Requester creates the case.
2.  Screenshot or evidence is uploaded.
3.  AI analyzes the case.
4.  AI suggests Network Support.
5.  Operator reviews the recommendation.
6.  Missing office/location information is identified.
7.  Operator requests the information.
8.  Requester responds.
9.  Operator creates an investigation task.
10. Investigation is performed.
11. Findings are recorded.
12. SLA/risk monitoring runs.
13. Team Lead intervenes if required.
14. The issue is fixed.
15. Resolution evidence is uploaded.
16. Requester confirms the resolution.
17. The case closes.
18. Manager reviews analytics.
19. Admin reviews audit history.

------------------------------------------------------------------------

# 12. Local Development and Deployment Requirements

## 12.1 Development Order

The required development order is:

**Build locally → Test locally → Complete E2E workflow → Prepare
production configuration → Deploy**

The complete system shall work locally before production deployment.

## 12.2 Production Direction

Production deployment may use compatible free or low-cost services where
practical for:

-   Flutter production build
-   Backend hosting
-   Supabase PostgreSQL
-   File storage
-   External AI API
-   Push notification service

Production deployment shall not add unnecessary infrastructure beyond
the Version 1 requirements.

------------------------------------------------------------------------

# 13. MVP Scope

## 13.1 Authentication

-   Registration
-   Login
-   RBAC
-   Profile

## 13.2 Requester

-   Create case
-   Upload evidence
-   View authorized cases
-   Answer questions
-   Receive supported updates
-   Confirm or reject resolution

## 13.3 Operator

-   View cases
-   Review AI analysis
-   Assignment
-   Communication
-   Internal notes
-   Tasks
-   Investigation
-   Status updates
-   Resolution

## 13.4 Team Lead

-   Team workload
-   At-risk cases
-   Escalations
-   Intervention

## 13.5 Manager

-   Operational dashboard
-   Trends
-   Performance
-   Important cases
-   Operational insights

## 13.6 Admin

-   Users
-   Teams
-   Categories
-   SLA/policies
-   Settings
-   Audit history

## 13.7 AI

-   Case analysis
-   Classification
-   Priority/severity
-   Summary
-   Missing information
-   Related/duplicate detection
-   Assignment recommendation
-   Next action
-   Risk analysis
-   Communication drafting
-   Operational insights

## 13.8 Workflow

-   Case lifecycle
-   SLA awareness
-   Escalation
-   In-app notifications
-   Push notifications
-   Resolution confirmation
-   Reopening
-   Timeline
-   Audit history

Email notifications, transactional email APIs, and SMTP are not part of
the MVP.

------------------------------------------------------------------------

# 14. Future Enhancements

Potential future enhancements include:

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

------------------------------------------------------------------------

# 15. Product Quality Requirements

The final product shall demonstrate:

-   Coherent UX
-   Clear role-based journeys
-   Real persistent data
-   Meaningful AI
-   Complete case lifecycle
-   Loading, error, and empty states
-   Useful supported notifications
-   Traceable actions
-   Consistent terminology
-   Professional UI
-   Real multi-user behavior
-   Proper FastAPI business logic
-   Secure configuration
-   Basic monitoring
-   Reliable error handling
-   Tested workflows

A feature is not complete simply because its screen exists. Meaningful
actions shall produce real effects throughout the system.

------------------------------------------------------------------------

# 16. Product Success Criteria

The completed system should demonstrate that it can:

1.  Capture a real IT problem.
2.  Preserve complete case history.
3.  Allow multiple roles to collaborate.
4.  Use AI meaningfully.
5.  Identify what needs to happen next.
6.  Detect cases requiring attention.
7.  Keep employees informed through supported application notifications.
8.  Reduce forgotten cases.
9.  Allow human override of AI.
10. Provide accountability.
11. Confirm actual resolution.
12. Provide operational visibility.
13. Continue when AI is unavailable.
14. Operate without a separate worker architecture.
15. Complete a real multi-user E2E workflow.
16. Run locally before production.
17. Deploy using free/low-cost infrastructure where practical.

------------------------------------------------------------------------

# 17. Final System Definition

**AI Office IT Help Desk** is a multi-user, AI-powered case management
system for office IT problems and service requests.

The complete workflow is:

**Employee → Case → Evidence → AI Understanding → Assignment →
Communication → Investigation → Tasks → SLA → Risk → Escalation →
Resolution → Confirmation → Analytics → Audit**

The defining principle is:

> **The system manages the case.**
>
> **AI helps people understand and move the case forward.**
>
> **Humans remain responsible for important decisions.**

Version 1 shall remain simple, realistic, maintainable, and
production-minded.

The implementation direction is:

**Flutter + Python FastAPI + PostgreSQL/Supabase + File Storage + AI
APIs + Lightweight Scheduler + In-App/Push Notifications**

**Build locally first, validate with real multi-user end-to-end testing,
and then deploy.**

**No separate Worker Architecture is required for Version 1.**
