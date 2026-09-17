import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/core/constants.dart';
import 'package:frontend/models/user.dart';
import 'package:frontend/models/case_item.dart';
import 'package:frontend/models/communication.dart';
import 'package:frontend/models/task.dart';
import 'package:frontend/models/ai_analysis.dart';
import 'package:frontend/models/dashboard_metrics.dart';
import 'package:frontend/models/notification_item.dart';

void main() {
  group('Core Enums Tests', () {
    test('UserRole mappings', () {
      expect(UserRole.fromString('REQUESTER'), UserRole.requester);
      expect(UserRole.fromString('OPERATOR'), UserRole.operator);
      expect(UserRole.fromString('TEAM_LEAD'), UserRole.teamLead);
      expect(UserRole.fromString('MANAGER'), UserRole.manager);
      expect(UserRole.fromString('ADMIN'), UserRole.admin);
      expect(UserRole.fromString('UNKNOWN'), UserRole.requester);
    });

    test('CaseStatus mappings', () {
      expect(CaseStatus.fromString('REPORTED'), CaseStatus.reported);
      expect(CaseStatus.fromString('INVESTIGATING'), CaseStatus.investigating);
      expect(CaseStatus.fromString('RESOLUTION_PROPOSED'), CaseStatus.resolutionProposed);
      expect(CaseStatus.fromString('CLOSED'), CaseStatus.closed);
      expect(CaseStatus.fromString('REOPENED'), CaseStatus.reopened);
    });

    test('CasePriority mappings', () {
      expect(CasePriority.fromString('LOW'), CasePriority.low);
      expect(CasePriority.fromString('MEDIUM'), CasePriority.medium);
      expect(CasePriority.fromString('HIGH'), CasePriority.high);
      expect(CasePriority.fromString('CRITICAL'), CasePriority.critical);
    });

    test('MessageType mappings', () {
      expect(MessageType.fromString('COMMUNICATION'), MessageType.communication);
      expect(MessageType.fromString('INFO_REQUEST'), MessageType.infoRequest);
      expect(MessageType.fromString('INFO_RESPONSE'), MessageType.infoResponse);
    });
  });

  group('Model Deserialization Tests', () {
    test('UserModel.fromJson parses correctly', () {
      final json = {
        'id': 1,
        'email': 'requester@company.local',
        'full_name': 'Alex Requester',
        'role': 'REQUESTER',
        'department': 'Sales',
        'is_active': true,
        'created_at': '2026-09-17T10:00:00Z',
      };
      final user = UserModel.fromJson(json);
      expect(user.id, 1);
      expect(user.email, 'requester@company.local');
      expect(user.fullName, 'Alex Requester');
      expect(user.role, UserRole.requester);
      expect(user.department, 'Sales');
      expect(user.isActive, true);
    });

    test('CaseItem.fromJson parses correctly', () {
      final json = {
        'id': 101,
        'case_number': 'IT-10001',
        'title': 'VPN connection timeout',
        'description': 'Cannot connect from home Wi-Fi',
        'category_id': 2,
        'category_name': 'Network & VPN',
        'priority': 'HIGH',
        'severity': 'MAJOR',
        'status': 'INVESTIGATING',
        'requester_id': 1,
        'requester_name': 'Alex Requester',
        'assigned_operator_id': 2,
        'assigned_operator_name': 'Sam Operator',
        'is_escalated': false,
        'created_at': '2026-09-17T11:00:00Z',
        'updated_at': '2026-09-17T11:30:00Z',
      };
      final item = CaseItem.fromJson(json);
      expect(item.id, 101);
      expect(item.caseNumber, 'IT-10001');
      expect(item.title, 'VPN connection timeout');
      expect(item.priority, CasePriority.high);
      expect(item.status, CaseStatus.investigating);
      expect(item.requesterName, 'Alex Requester');
      expect(item.assignedOperatorName, 'Sam Operator');
    });

    test('ChecklistTask.fromJson parses correctly', () {
      final json = {
        'id': 1,
        'case_id': 101,
        'title': 'Verify DNS settings',
        'is_completed': true,
        'completed_at': '2026-09-17T11:20:00Z',
        'created_at': '2026-09-17T11:05:00Z',
      };
      final task = ChecklistTask.fromJson(json);
      expect(task.id, 1);
      expect(task.caseId, 101);
      expect(task.title, 'Verify DNS settings');
      expect(task.isCompleted, true);
    });

    test('AiTriageResult.fromJson parses correctly', () {
      final json = {
        'suggested_category_id': 2,
        'suggested_category_name': 'Network',
        'suggested_priority': 'HIGH',
        'suggested_severity': 'MAJOR',
        'confidence_score': 0.94,
        'summary': 'Network DNS Gateway Issue',
        'missing_info_questions': ['What error code is shown in the VPN client?'],
        'suggested_tasks': ['Check VPN server logs', 'Ping DNS gateway'],
      };
      final ai = AiTriageResult.fromJson(json);
      expect(ai.suggestedCategoryId, 2);
      expect(ai.suggestedPriority, CasePriority.high);
      expect(ai.confidenceScore, 0.94);
      expect(ai.summary, 'Network DNS Gateway Issue');
      expect(ai.missingInfoQuestions.length, 1);
      expect(ai.suggestedTasks.length, 2);
    });

    test('RequesterDashboardData.fromJson parses correctly', () {
      final json = {
        'active_cases_count': 3,
        'waiting_for_requester_count': 1,
        'resolved_cases_count': 12,
        'unread_notifications_count': 2,
        'recent_cases': [
          {
            'id': 1,
            'case_number': 'IT-10001',
            'title': 'Test Case',
            'description': 'Desc',
            'priority': 'LOW',
            'severity': 'MINOR',
            'status': 'REPORTED',
            'requester_id': 1,
            'created_at': '2026-09-17T10:00:00Z',
            'updated_at': '2026-09-17T10:00:00Z',
          }
        ],
      };
      final data = RequesterDashboardData.fromJson(json);
      expect(data.activeCasesCount, 3);
      expect(data.waitingForRequesterCount, 1);
      expect(data.resolvedCasesCount, 12);
      expect(data.unreadNotificationsCount, 2);
      expect(data.recentCases.length, 1);
    });

    test('NotificationItem.fromJson parses correctly', () {
      final json = {
        'id': 5,
        'user_id': 1,
        'title': 'Resolution Proposed',
        'message': 'IT Operator resolved your issue.',
        'notification_type': 'RESOLUTION',
        'case_id': 101,
        'is_read': false,
        'created_at': '2026-09-17T12:00:00Z',
      };
      final notif = NotificationItem.fromJson(json);
      expect(notif.id, 5);
      expect(notif.title, 'Resolution Proposed');
      expect(notif.notificationType, NotificationType.resolution);
      expect(notif.isRead, false);
      expect(notif.caseId, 101);
    });

    test('CommunicationMessage and InternalNote fromJson parse correctly', () {
      final msgJson = {
        'id': 1,
        'case_id': 101,
        'sender_id': 2,
        'sender_name': 'Sam Operator',
        'message_type': 'INFO_REQUEST',
        'content': 'Could you provide the exact laptop model?',
        'created_at': '2026-09-17T11:10:00Z',
      };
      final msg = CommunicationMessage.fromJson(msgJson);
      expect(msg.id, 1);
      expect(msg.content, 'Could you provide the exact laptop model?');
      expect(msg.messageType, MessageType.infoRequest);

      final noteJson = {
        'id': 2,
        'case_id': 101,
        'author_id': 2,
        'author_name': 'Sam Operator',
        'note_text': 'Checked switch port, looks good.',
        'created_at': '2026-09-17T11:15:00Z',
      };
      final note = InternalNote.fromJson(noteJson);
      expect(note.id, 2);
      expect(note.noteText, 'Checked switch port, looks good.');
    });

    test('InvestigationRecord and ResolutionRecord fromJson parse correctly', () {
      final invJson = {
        'id': 1,
        'case_id': 101,
        'operator_id': 2,
        'observations': 'Cable loose',
        'actions_taken': 'Replaced cable',
        'created_at': '2026-09-17T11:20:00Z',
      };
      final inv = InvestigationRecord.fromJson(invJson);
      expect(inv.id, 1);
      expect(inv.observations, 'Cable loose');

      final resJson = {
        'id': 1,
        'case_id': 101,
        'operator_id': 2,
        'actions_taken': 'Configured port',
        'created_at': '2026-09-17T11:25:00Z',
      };
      final res = ResolutionRecord.fromJson(resJson);
      expect(res.id, 1);
      expect(res.actionsTaken, 'Configured port');
    });
  });
}

