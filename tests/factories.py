import factory
from django.contrib.auth import get_user_model

from categories.models import Category
from todos.models import Todo


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    name = factory.Sequence(lambda n: f"User {n}")
    password = factory.PostGenerationMethodCall("set_password", "A-safe-password-123!")


class StaffUserFactory(UserFactory):
    is_staff = True


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
