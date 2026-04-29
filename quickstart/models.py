# from datetime import datetime, timezone

from django.utils import timezone
from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


# Create your models here.
class BaseModel(models.Model):
    created_date = models.DateTimeField(auto_now=True)
    modified_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="%(class)s_creator",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="%(class)s_updater",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )

class Guns(BaseModel):
    SOURCE_CHOICES = (
        ("PROCURED", "Procured"),
        ("DONATED_FOUND_AT_STATION", "Donated Found at Station"),
        ("LOANED", "Loaned"),
    )

    STATUS_CHOICES = (
        ("SVC", "Svc"),
        ("UNSVC", "Unsvc"),
        ("BER", "BER"),
    )

    DISPOSITION_CHOICES = (
        ("ISSUED", "Issued"),
        ("ON_STOCK", "On Stock"),
    )

    serial_no = models.CharField(max_length=250, null=True, blank=True)
    make = models.CharField(max_length=250, null=True, blank=True)
    type = models.CharField(max_length=250, null=True, blank=True)
    caliber = models.CharField(max_length=250, null=True, blank=True)
    property_no = models.CharField(max_length=250, null=True, blank=True)

    # if excel only stores year, consider IntegerField instead
    acquisition_date = models.DateField(null=True, blank=True)

    acquisition_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)
    cost_of_repair = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)
    current_depreciated_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)

    source = models.CharField(max_length=250, null=True, blank=True, choices=SOURCE_CHOICES, default="PROCURED")
    status = models.CharField(max_length=250, null=True, blank=True, choices=STATUS_CHOICES, default="SVC")

    balance_qty = models.IntegerField(null=True, blank=True, default=0)
    balance_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)

    on_hand_qty = models.IntegerField(null=True, blank=True, default=0)
    on_hand_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)

    short_qty = models.IntegerField(null=True, blank=True, default=0)
    short_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)

    over_qty = models.IntegerField(null=True, blank=True, default=0)
    over_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)

    disposition = models.CharField(max_length=250, null=True, blank=True, choices=DISPOSITION_CHOICES, default="ON_STOCK")

    def __str__(self):
        return f"{self.property_no or ''} - {self.make or ''} - {self.serial_no or ''}".strip()

class Persons(BaseModel):
    rank = models.CharField(max_length=250, null=True, blank=True)
    name = models.CharField(max_length=250, null=True, blank=True)
    unit = models.CharField(max_length=250, null=True, blank=True)
    sub_unit = models.CharField(max_length=250, null=True, blank=True)
    station = models.CharField(max_length=250, null=True, blank=True)
    issued_unit = models.CharField(max_length=250, null=True, blank=True)

    # ✅ one person = one gun, one gun = one person
    gun = models.OneToOneField(
        Guns, on_delete=models.SET_NULL, null=True, blank=True, related_name="issued_to"
    )

    def __str__(self):
        return f"{(self.rank or '').strip()} {(self.name or '').strip()} {(self.unit or '').strip()}".strip()


class Pars(BaseModel):
    person = models.ForeignKey(Persons, on_delete=models.CASCADE, related_name="pars", null=True, blank=True)
    img = models.FileField(upload_to="person_attachments/", null=True, blank=True)
    date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"PAR - {self.person_id} - {self.date}"


class GunHistory(BaseModel):
    """
    ✅ This is your History table for the gun:
    date, disposition, image, and optional person reference.
    """

    EVENT_CHOICES = (
        ("ISSUED", "Issued"),
        ("TURN_IN", "Turn In"),
        ("STATUS_CHANGE", "Status Change"),
    )

    gun = models.ForeignKey(Guns, on_delete=models.CASCADE, related_name="history", null=True, blank=True)
    person = models.ForeignKey(Persons, on_delete=models.SET_NULL, null=True, blank=True, related_name="gun_history")
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES, null=True, blank=True)
    disposition = models.CharField(max_length=50, null=True, blank=True)  # snapshot
    date = models.DateField(default=timezone.now(), null=True, blank=True)
    img = models.FileField(upload_to="gun_history/", null=True, blank=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.gun_id} - {self.event_type} - {self.date}  - {self.gun}"

class GunHistoryImage(BaseModel):
    history = models.ForeignKey("GunHistory", on_delete=models.CASCADE, related_name="images")
    img = models.FileField(upload_to="person_attachments/", null=True, blank=True)

    def __str__(self):
        return f"HistoryImage {self.id} - History {self.history_id}"


class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ("VIEW", "View"),
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs"
    )

    username = models.CharField(max_length=150, null=True, blank=True)
    role = models.CharField(max_length=50, null=True, blank=True)

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    module = models.CharField(max_length=100)
    description = models.TextField()

    target_id = models.CharField(max_length=100, null=True, blank=True)
    target_name = models.CharField(max_length=255, null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.username} - {self.action} - {self.module}"