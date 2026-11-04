from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    """Manager for a user model that logs in with an email address."""

    use_in_migrations = True

    @staticmethod
    def _clean_email(email):
        email = (email or "").strip().lower()
        if not email:
            raise ValueError("The email must be set.")
        return email

    def _create_user(self, email, password, name, **extra_fields):
        email = self._clean_email(email)
        name = (name or "").strip()
        if not name:
            raise ValueError("The name must be set.")
        user = self.model(email=email, name=name, **extra_fields)
        user.set_password(password)  # hashes; password=None -> unusable password
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, name="", **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, name, **extra_fields)

    def create_superuser(self, email, password=None, name="", **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, name, **extra_fields)


class User(AbstractUser):
    # Drop the fields we don't use from AbstractUser.
    username = None
    first_name = None
    last_name = None

    name = models.CharField(max_length=150)
    # unique=True is required by Django's auth checks for USERNAME_FIELD;
    # the Lower() constraint below makes it case-insensitive.
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]  # asked by `createsuperuser` in addition to email

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="user_email_ci_unique"),
        ]

    def clean(self):
        super().clean()
        # Runs before the unique checks in forms (admin, serializers' full_clean).
        self.email = (self.email or "").strip().lower()
        self.name = (self.name or "").strip()

    def save(self, *args, **kwargs):
        # Safety net for any code path that skips the manager/clean().
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    def __str__(self):
        return self.email