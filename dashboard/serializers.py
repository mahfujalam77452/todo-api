from rest_framework import serializers


class RateSerializer(serializers.Serializer):
    completed = serializers.IntegerField()
    total = serializers.IntegerField()
    percentage = serializers.FloatField()


class OverviewSerializer(serializers.Serializer):
    users = serializers.IntegerField()
    teams = serializers.IntegerField()
    todos = serializers.IntegerField()
    incomplete_todos = serializers.IntegerField()
    completed_todos = serializers.IntegerField()
    pending_assignments = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    bottlenecks = serializers.DictField()


class DashboardUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()
    team = serializers.DictField(allow_null=True)
    created_count = serializers.IntegerField()
    assigned_count = serializers.IntegerField()
    completed_count = serializers.IntegerField()
    rejected_count = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    rejection_rate = serializers.FloatField()


class DashboardTeamSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    member_count = serializers.IntegerField()
    todo_count = serializers.IntegerField()
    completed_count = serializers.IntegerField()
    pending_assignment_count = serializers.IntegerField()
    completion_rate = serializers.FloatField()


class ActivitySerializer(serializers.Serializer):
    type = serializers.CharField()
    todo_id = serializers.IntegerField()
    title = serializers.CharField()
    user_id = serializers.IntegerField(allow_null=True)
    occurred_at = serializers.DateTimeField()
    assignment_status = serializers.CharField(allow_null=True)


class DashboardTodoSerializer(serializers.Serializer):
    todo = serializers.DictField()
