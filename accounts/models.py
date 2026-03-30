from django.db import models
from django.contrib.auth.models import User, AbstractUser


class UserProfile(models.Model):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("viewer", "Viewer"),
        ("super_admin", "Super Admin"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="viewer")
    unit = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"
