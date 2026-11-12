import factory
from django.contrib.auth import get_user_model

from categories.models import Category
from todos.models import Todo
from teams.models import Membership, Team


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    name = factory.Sequence(lambda n: f"User {n}")
    role = "member"
    password = factory.PostGenerationMethodCall("set_password", "A-safe-password-123!")


class StaffUserFactory(UserFactory):
    is_staff = True


class AdminUserFactory(UserFactory):
    role = "admin"
    is_staff = True
    is_superuser = True


class TeamFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Team

    name = factory.Sequence(lambda n: f"Team {n}")


class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Membership

    user = factory.SubFactory(UserFactory)
    team = factory.SubFactory(TeamFactory)


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")


class TodoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Todo

    user = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"Todo {n}")
    description = ""
    is_completed = False
    priority = Todo.Priority.MEDIUM
    due_date = None
