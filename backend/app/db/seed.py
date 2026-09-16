import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.enums import CasePriority, UserRole
from app.models.user import Team
from app.models.category import Category
from app.models.sla import SLAPolicy


async def seed_initial_data():
    async with AsyncSessionLocal() as session:
        # 1. Seed Teams
        teams_data = [
            {"name": "Network Support", "description": "Handles office Wi-Fi, Ethernet, VPN, routers and network connectivity issues."},
            {"name": "Hardware Support", "description": "Handles laptops, desktops, monitors, printers, mice and physical accessories."},
            {"name": "Systems & Infrastructure", "description": "Handles internal office servers, OS upgrades, software installation and email clients."},
            {"name": "Accounts & Access", "description": "Handles employee login credentials, permission requests, and SSO accounts."},
            {"name": "General IT Support", "description": "Handles general workplace IT triage, peripherals, and unclassified requests."},
        ]

        team_objects = {}
        for t_data in teams_data:
            stmt = select(Team).where(Team.name == t_data["name"])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                team = Team(**t_data)
                session.add(team)
                await session.flush()
                team_objects[team.name] = team
            else:
                team_objects[existing.name] = existing

        # 2. Seed Categories
        categories_data = [
            {"name": "Wi-Fi / Network Issue", "description": "Problems with office Wi-Fi connectivity or internet access.", "default_priority": CasePriority.HIGH, "team_name": "Network Support"},
            {"name": "Laptop / PC Hardware Problem", "description": "Issues with keyboard, screen, battery, power, or hardware failure.", "default_priority": CasePriority.HIGH, "team_name": "Hardware Support"},
            {"name": "Software & Operating System", "description": "Software crashes, licensing issues, or software installation requests.", "default_priority": CasePriority.MEDIUM, "team_name": "Systems & Infrastructure"},
            {"name": "Office Email & Messaging", "description": "Outlook, Thunderbird, or office email login/sending issues.", "default_priority": CasePriority.HIGH, "team_name": "Systems & Infrastructure"},
            {"name": "Account & Access Permissions", "description": "Password resets, domain logins, system permissions, and badges.", "default_priority": CasePriority.MEDIUM, "team_name": "Accounts & Access"},
            {"name": "Printer & Scanner Issue", "description": "Office printer paper jams, offline status, or driver configuration.", "default_priority": CasePriority.LOW, "team_name": "Hardware Support"},
            {"name": "VPN / Remote Access", "description": "Office VPN connection drops, token authentication, or remote gateway errors.", "default_priority": CasePriority.HIGH, "team_name": "Network Support"},
        ]

        for c_data in categories_data:
            stmt = select(Category).where(Category.name == c_data["name"])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                team = team_objects.get(c_data["team_name"])
                category = Category(
                    name=c_data["name"],
                    description=c_data["description"],
                    default_priority=c_data["default_priority"],
                    default_team_id=team.id if team else None,
                )
                session.add(category)

        # 3. Seed SLA Policies
        sla_data = [
            {"name": "Critical SLA", "priority": CasePriority.CRITICAL, "response_time_hours": 1, "resolution_time_hours": 4},
            {"name": "High SLA", "priority": CasePriority.HIGH, "response_time_hours": 2, "resolution_time_hours": 8},
            {"name": "Medium SLA", "priority": CasePriority.MEDIUM, "response_time_hours": 4, "resolution_time_hours": 24},
            {"name": "Low SLA", "priority": CasePriority.LOW, "response_time_hours": 8, "resolution_time_hours": 72},
        ]

        for s_data in sla_data:
            stmt = select(SLAPolicy).where(SLAPolicy.priority == s_data["priority"])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                sla = SLAPolicy(**s_data)
                session.add(sla)

        await session.commit()
        print("SEED_DATA_SUCCESS: Initial Teams, Categories, and SLA Policies seeded.")


if __name__ == "__main__":
    asyncio.run(seed_initial_data())
