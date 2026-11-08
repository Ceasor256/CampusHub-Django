import uuid
from functools import cached_property

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        """Django-admin access only. CampusHub staff roles are separate (StaffRole)."""
        extra.update(is_staff=True, is_superuser=True)
        user = self._create(email, password, **extra)
        StaffRole.objects.get_or_create(user=user, role=StaffRole.Role.ADMIN)
        return user

    def get_by_natural_key(self, email):
        return self.get(email__iexact=email)


class User(AbstractUser):
    """
    One account for every role: a student can buy, sell, post gigs, apply,
    and own businesses. Staff powers come only from StaffRole rows.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        DELETED = "deleted", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    first_name = None
    last_name = None
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=16, blank=True, help_text="E.164, e.g. +256772123456. Never public.")
    bio = models.CharField(max_length=400, blank=True)
    campus = models.ForeignKey("core.Campus", null=True, blank=True, on_delete=models.SET_NULL, related_name="members")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    suspended_reason = models.CharField(max_length=500, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    student_verified_at = models.DateTimeField(null=True, blank=True)
    onboarded_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]
    objects = UserManager()

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="user_email_ci_uq")]

    def __str__(self):
        return self.full_name or self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or "").lower()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------ authorization
    @cached_property
    def roles(self) -> set[str]:
        if not self.pk:
            return set()
        return set(self.staff_roles.values_list("role", flat=True))

    @property
    def is_active_member(self):
        return self.status == self.Status.ACTIVE

    @property
    def is_suspended(self):
        return self.status == self.Status.SUSPENDED

    @property
    def is_staff_member(self):
        return bool(self.roles & {"admin", "moderator", "support"})

    @property
    def can_moderate(self):
        return bool(self.roles & {"admin", "moderator"})

    @property
    def is_platform_admin(self):
        return "admin" in self.roles

    @property
    def first_name_display(self):
        return (self.full_name or "").split(" ")[0]


class StaffRole(models.Model):
    """Staff permissions. Granted by admins or the CLI, never via profile edits."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MODERATOR = "moderator", "Moderator"
        SUPPORT = "support", "Support"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="staff_roles")
    role = models.CharField(max_length=10, choices=Role.choices)
    granted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "role"], name="staff_role_uq")]
