import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai import AICaseAnalysis
from app.models.case import Case
from app.models.category import Category
from app.models.enums import CasePriority, CaseSeverity, CaseStatus
from app.models.user import Team, User
from app.schemas.ai import (
    AIDraftMessageResponse,
    AIDuplicateCheckResponse,
    AIDuplicateMatch,
)
from app.services.timeline_service import TimelineService

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"
        self._client = None
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client: {e}")
                self._client = None
        self.is_available: bool = self._client is not None and bool(self.api_key)

    async def analyze_case(
        self,
        case: Case,
        db: AsyncSession,
        actor: Optional[User] = None,
        timeout_seconds: float = 8.0,
    ) -> AICaseAnalysis:
        """
        Analyzes an IT Help Desk case using Gemini 2.5 Flash.
        Strict Resilience Guarantee:
        If AI is offline, invalid JSON, or times out, seamlessly falls back to rule-based triage.
        Core ticketing will never crash or fail.
        """
        # Fetch reference data from database for category/team resolution
        teams_stmt = select(Team)
        teams = (await db.execute(teams_stmt)).scalars().all()
        team_map = {t.name.lower(): t for t in teams}

        cats_stmt = select(Category)
        categories = (await db.execute(cats_stmt)).scalars().all()
        cat_map = {c.name.lower(): c for c in categories}

        # Query recent open cases for related case candidate detection
        recent_cases_stmt = (
            select(Case)
            .where(Case.id != case.id, Case.status.notin_([CaseStatus.CLOSED, CaseStatus.CANCELLED]))
            .order_by(Case.created_at.desc())
            .limit(10)
        )
        recent_cases = (await db.execute(recent_cases_stmt)).scalars().all()

        ai_data: Optional[Dict[str, Any]] = None

        if self.is_available:
            try:
                prompt = self._build_triage_prompt(case, categories, teams, recent_cases)
                # Call Gemini async API with timeout safeguard
                response = await asyncio.wait_for(
                    self._client.aio.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                    ),
                    timeout=timeout_seconds,
                )
                ai_data = self._extract_json(response.text)
            except asyncio.TimeoutError:
                logger.warning(f"Gemini API timed out after {timeout_seconds}s for case {case.case_number}. Using rule-based fallback.")
            except Exception as exc:
                logger.warning(f"Gemini API error during case analysis ({exc}). Using rule-based fallback.")

        # If AI was not available or failed/timed out, execute deterministic rule-based fallback
        if not ai_data:
            ai_data = self._rule_based_fallback(case, categories, teams, recent_cases)

        # Resolve category ID
        suggested_cat_id = None
        s_cat_name = ai_data.get("suggested_category_name")
        if s_cat_name and s_cat_name.lower() in cat_map:
            suggested_cat_id = cat_map[s_cat_name.lower()].id
        elif categories:
            # Fallback to current case category or first matched
            suggested_cat_id = case.category_id or categories[0].id

        # Resolve team ID
        suggested_team_id = None
        s_team_name = ai_data.get("suggested_team_name")
        if s_team_name and s_team_name.lower() in team_map:
            suggested_team_id = team_map[s_team_name.lower()].id
        elif suggested_cat_id:
            # Match default team for category
            cat_obj = next((c for c in categories if c.id == suggested_cat_id), None)
            if cat_obj and cat_obj.default_team_id:
                suggested_team_id = cat_obj.default_team_id

        # Validate priority enum
        suggested_priority = CasePriority.MEDIUM
        raw_pri = str(ai_data.get("suggested_priority", "")).upper()
        if raw_pri in CasePriority.__members__:
            suggested_priority = CasePriority[raw_pri]

        # Validate severity enum
        suggested_severity = CaseSeverity.MODERATE
        raw_sev = str(ai_data.get("suggested_severity", "")).upper()
        if raw_sev in CaseSeverity.__members__:
            suggested_severity = CaseSeverity[raw_sev]

        # Map related case numbers/IDs to integer IDs
        related_case_ids: List[int] = []
        raw_related = ai_data.get("related_case_ids", []) or ai_data.get("related_case_numbers", [])
        for item in raw_related:
            if isinstance(item, int):
                related_case_ids.append(item)
            elif isinstance(item, str):
                match = next((rc.id for rc in recent_cases if rc.case_number == item), None)
                if match:
                    related_case_ids.append(match)

        analysis = AICaseAnalysis(
            case_id=case.id,
            suggested_category_id=suggested_cat_id,
            suggested_priority=suggested_priority,
            suggested_severity=suggested_severity,
            suggested_team_id=suggested_team_id,
            missing_information=ai_data.get("missing_information", []) or [],
            recommended_questions=ai_data.get("recommended_questions", []) or [],
            related_case_ids=related_case_ids,
            recommended_next_action=ai_data.get("recommended_next_action"),
            case_summary=ai_data.get("case_summary"),
            risk_insight=ai_data.get("risk_insight"),
            confidence_score=str(ai_data.get("confidence_score", "0.80")),
            is_accepted=False,
            is_overridden=False,
        )

        db.add(analysis)
        await db.flush()

        # Record timeline event
        await TimelineService.record_event(
            db=db,
            case_id=case.id,
            event_type="AI_ANALYSIS_COMPLETED",
            summary=f"AI Case Analysis completed (Confidence: {analysis.confidence_score}).",
            actor=actor,
            details={
                "analysis_id": analysis.id,
                "suggested_priority": analysis.suggested_priority.value if analysis.suggested_priority else None,
                "suggested_severity": analysis.suggested_severity.value if analysis.suggested_severity else None,
                "confidence_score": analysis.confidence_score,
            },
        )

        return analysis

    async def detect_duplicates(
        self,
        title: str,
        description: str,
        db: AsyncSession,
        exclude_case_id: Optional[int] = None,
        category_id: Optional[int] = None,
    ) -> AIDuplicateCheckResponse:
        """
        Scans open and recent tickets to find potential duplicates based on semantic and keyword overlap.
        """
        query = select(Case).where(Case.status.notin_([CaseStatus.CLOSED, CaseStatus.CANCELLED]))
        if exclude_case_id:
            query = query.where(Case.id != exclude_case_id)
        if category_id:
            query = query.where(Case.category_id == category_id)

        query = query.order_by(Case.created_at.desc()).limit(25)
        candidates = (await db.execute(query)).scalars().all()

        if not candidates:
            return AIDuplicateCheckResponse(potential_duplicates=[], count=0)

        # Tokenize query
        search_words = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", (title + " " + description).lower()))
        matches: List[AIDuplicateMatch] = []

        for c in candidates:
            c_words = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", (c.title + " " + c.description).lower()))
            if not search_words or not c_words:
                continue

            intersection = search_words.intersection(c_words)
            union = search_words.union(c_words)
            jaccard = len(intersection) / len(union) if union else 0.0

            # Title matching has extra weight
            c_title_words = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", c.title.lower()))
            q_title_words = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", title.lower()))
            title_overlap = len(q_title_words.intersection(c_title_words)) / max(len(q_title_words), 1)

            composite_score = round(min((jaccard * 0.5) + (title_overlap * 0.5), 1.0), 2)

            if composite_score >= 0.25:
                matching_terms = list(intersection)[:4]
                reason = f"High keyword overlap on terms: {', '.join(matching_terms)}" if matching_terms else "Similar title and problem description."
                matches.append(
                    AIDuplicateMatch(
                        case_id=c.id,
                        case_number=c.case_number,
                        title=c.title,
                        similarity_score=composite_score,
                        reason=reason,
                    )
                )

        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        return AIDuplicateCheckResponse(potential_duplicates=matches[:5], count=len(matches[:5]))

    async def draft_communication(
        self,
        case: Case,
        draft_type: str,
        db: AsyncSession,
        instructions: Optional[str] = None,
        timeout_seconds: float = 6.0,
    ) -> AIDraftMessageResponse:
        """
        Drafts professional, empathetic IT support communications tailored to the ticket context.
        Types: INFO_REQUEST, STATUS_UPDATE, WORKAROUND, RESOLUTION_EXPLANATION.
        """
        if self.is_available:
            try:
                prompt = (
                    f"You are a Senior Office IT Help Desk Specialist. Draft a professional, courteous in-app message to the employee.\n"
                    f"Ticket Number: {case.case_number}\n"
                    f"Title: {case.title}\n"
                    f"Description: {case.description}\n"
                    f"Message Type: {draft_type}\n"
                    f"Additional Guidance: {instructions or 'Standard helpful response'}\n\n"
                    f"Respond ONLY with valid JSON matching:\n"
                    f'{{\n  "subject": "Clear subject line",\n  "drafted_message": "Courteous body text",\n  "key_points": ["Point 1", "Point 2"]\n}}'
                )
                response = await asyncio.wait_for(
                    self._client.aio.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                    ),
                    timeout=timeout_seconds,
                )
                parsed = self._extract_json(response.text)
                if parsed and "drafted_message" in parsed:
                    return AIDraftMessageResponse(
                        draft_type=draft_type,
                        subject=parsed.get("subject", f"Update regarding {case.case_number}"),
                        drafted_message=parsed["drafted_message"],
                        key_points=parsed.get("key_points", []),
                    )
            except Exception as e:
                logger.warning(f"AI draft generation failed ({e}). Using deterministic template fallback.")

        # Fallback template draft
        return self._draft_fallback(case, draft_type, instructions)

    # -------------------------------------------------------------------------
    # Helper & Fallback Methods
    # -------------------------------------------------------------------------

    def _build_triage_prompt(
        self,
        case: Case,
        categories: List[Category],
        teams: List[Team],
        recent_cases: List[Case],
    ) -> str:
        cat_names = [c.name for c in categories]
        team_names = [t.name for t in teams]
        recent_summaries = [f"{rc.case_number}: {rc.title}" for rc in recent_cases[:5]]

        return (
            f"You are an expert Senior Office IT Help Desk Triage Engineer.\n"
            f"Analyze this IT support ticket and return a structured JSON response.\n\n"
            f"TICKET DETAILS:\n"
            f"- Case Number: {case.case_number}\n"
            f"- Title: {case.title}\n"
            f"- Description: {case.description}\n"
            f"- Office Location: {case.office_location or 'Not specified'}\n\n"
            f"ALLOWED CATEGORIES (Pick best exact match):\n{json.dumps(cat_names)}\n\n"
            f"ALLOWED TEAMS (Pick best exact match):\n{json.dumps(team_names)}\n\n"
            f"RECENT ACTIVE TICKETS (For related case detection):\n{json.dumps(recent_summaries)}\n\n"
            f"REQUIREMENTS:\n"
            f"1. suggested_category_name: must be one of the allowed categories.\n"
            f"2. suggested_priority: LOW, MEDIUM, HIGH, or CRITICAL.\n"
            f"3. suggested_severity: MINOR, MODERATE, MAJOR, or CRITICAL.\n"
            f"4. suggested_team_name: must be one of the allowed teams.\n"
            f"5. missing_information: list of missing details (e.g. error codes, IP, hardware model, asset tag).\n"
            f"6. recommended_questions: list of specific questions to ask the requester.\n"
            f"7. related_case_numbers: list of case numbers from recent tickets that may be related, or empty list.\n"
            f"8. recommended_next_action: technical step the technician should take first.\n"
            f"9. case_summary: 1-2 sentence executive summary of the problem.\n"
            f"10. risk_insight: potential productivity or business operational impact.\n"
            f"11. confidence_score: decimal string between 0.00 and 1.00.\n\n"
            f"Return ONLY valid JSON matching this schema:"
            """
{
  "suggested_category_name": "...",
  "suggested_priority": "MEDIUM",
  "suggested_severity": "MODERATE",
  "suggested_team_name": "...",
  "missing_information": ["..."],
  "recommended_questions": ["..."],
  "related_case_numbers": [],
  "recommended_next_action": "...",
  "case_summary": "...",
  "risk_insight": "...",
  "confidence_score": "0.90"
}
"""
        )

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Cleans and extracts JSON object from raw LLM output text."""
        if not text:
            return None
        text = text.strip()
        # Remove Markdown code fence if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        try:
            return json.loads(text)
        except Exception:
            # Attempt to find the first '{' and last '}'
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except Exception:
                    pass
        return None

    def _rule_based_fallback(
        self,
        case: Case,
        categories: List[Category],
        teams: List[Team],
        recent_cases: List[Case],
    ) -> Dict[str, Any]:
        """
        Deterministic, offline-resilient IT help desk triage heuristics.
        """
        text = (case.title + " " + case.description).lower()

        # Category and Team matching heuristics
        cat_name = "General IT Support"
        team_name = "General IT Support"
        priority = CasePriority.MEDIUM
        severity = CaseSeverity.MODERATE

        if any(k in text for k in ["wifi", "wi-fi", "network", "internet", "ethernet", "router", "dns", "gateway"]):
            cat_name = "Wi-Fi / Network Issue"
            team_name = "Network Support"
            priority = CasePriority.HIGH
            severity = CaseSeverity.MAJOR
        elif any(k in text for k in ["vpn", "remote access", "anyconnect", "tunnel"]):
            cat_name = "VPN / Remote Access"
            team_name = "Network Support"
            priority = CasePriority.HIGH
        elif any(k in text for k in ["laptop", "pc", "desktop", "battery", "screen", "keyboard", "mouse", "monitor", "charger", "hardware"]):
            cat_name = "Laptop / PC Hardware Problem"
            team_name = "Hardware Support"
            priority = CasePriority.HIGH
        elif any(k in text for k in ["printer", "scanner", "paper jam", "toner", "print"]):
            cat_name = "Printer & Scanner Issue"
            team_name = "Hardware Support"
            priority = CasePriority.LOW
            severity = CaseSeverity.MINOR
        elif any(k in text for k in ["password", "login", "locked", "sso", "access", "permission", "badge", "account"]):
            cat_name = "Account & Access Permissions"
            team_name = "Accounts & Access"
            priority = CasePriority.MEDIUM
        elif any(k in text for k in ["email", "outlook", "thunderbird", "mailbox", "inbox"]):
            cat_name = "Office Email & Messaging"
            team_name = "Systems & Infrastructure"
            priority = CasePriority.HIGH
        elif any(k in text for k in ["software", "crash", "install", "license", "windows", "macos", "linux", "excel"]):
            cat_name = "Software & Operating System"
            team_name = "Systems & Infrastructure"
            priority = CasePriority.MEDIUM

        # Missing info detection heuristics
        missing_info: List[str] = []
        questions: List[str] = []

        if not any(k in text for k in ["error", "code", "message", "screenshot"]):
            missing_info.append("Exact error code or on-screen message")
            questions.append("Could you please provide the exact error message or a screenshot if possible?")

        if not any(k in text for k in ["reboot", "restarted", "turn off"]):
            questions.append("Have you tried restarting the application or device?")

        if not case.office_location:
            missing_info.append("Workstation or office desk location")
            questions.append("Which floor and desk number are you currently located at?")

        # Related cases
        related: List[str] = []
        for rc in recent_cases:
            if cat_name.lower() in rc.title.lower() or any(w in rc.title.lower() for w in text.split()[:3]):
                related.append(rc.case_number)

        summary = f"Requester reports an issue regarding {case.title.strip()}."
        risk = "May impact individual daily office workflow until diagnosed."

        return {
            "suggested_category_name": cat_name,
            "suggested_priority": priority.value,
            "suggested_severity": severity.value,
            "suggested_team_name": team_name,
            "missing_information": missing_info or ["Device asset tag"],
            "recommended_questions": questions or ["Is any other colleague experiencing this same issue?"],
            "related_case_numbers": related[:2],
            "recommended_next_action": f"Contact requester and perform preliminary diagnostic verification on {cat_name}.",
            "case_summary": summary,
            "risk_insight": risk,
            "confidence_score": "0.78",
        }

    def _draft_fallback(self, case: Case, draft_type: str, instructions: Optional[str]) -> AIDraftMessageResponse:
        subject = f"Update regarding your IT ticket {case.case_number}"
        if draft_type == "INFO_REQUEST":
            subject = f"Information Needed: Ticket {case.case_number} - {case.title}"
            body = (
                f"Hello,\n\n"
                f"We are actively looking into your IT ticket ({case.case_number}: {case.title}). "
                f"To help us resolve this swiftly, could you please provide a few additional details?\n"
                f"1. Exact error message or screenshot if displayed.\n"
                f"2. Your current workstation desk number/location.\n"
                f"3. Has this device been restarted recently?\n\n"
                f"Thank you for your cooperation.\n"
                f"Office IT Help Desk Team"
            )
            key_points = ["Requested error code/screenshot", "Requested workstation desk location", "Asked about restart"]
        elif draft_type == "STATUS_UPDATE":
            body = (
                f"Hello,\n\n"
                f"This is an update regarding ticket {case.case_number}. Our technical team has been assigned "
                f"and is investigating the root cause. We will notify you as soon as remediation steps are underway.\n\n"
                f"Best regards,\nOffice IT Help Desk"
            )
            key_points = ["Technician assigned", "Investigation underway", "Next update promised"]
        elif draft_type == "WORKAROUND":
            body = (
                f"Hello,\n\n"
                f"While we work on the permanent fix for {case.title}, please try the following temporary workaround:\n"
                f"- Disconnect and reconnect your network connection, or try restarting the impacted application.\n"
                f"Please let us know if this temporarily restores your ability to work.\n\n"
                f"Best regards,\nOffice IT Help Desk"
            )
            key_points = ["Temporary workaround suggested", "Requested feedback on stability"]
        else:  # RESOLUTION_EXPLANATION
            body = (
                f"Hello,\n\n"
                f"We are pleased to inform you that remediation for ticket {case.case_number} ({case.title}) "
                f"has been completed. Please test your setup and let us know if everything is working smoothly.\n\n"
                f"Best regards,\nOffice IT Help Desk"
            )
            key_points = ["Remediation applied", "Requested requester confirmation"]

        return AIDraftMessageResponse(
            draft_type=draft_type,
            subject=subject,
            drafted_message=body,
            key_points=key_points,
        )


ai_service = AIService()
