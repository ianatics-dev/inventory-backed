from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
import pandas as pd
import numpy as np

from quickstart import models
from . import  serializers
from accounts.permissions import IsAdminOrReadOnly, IsSuperAdminRole, IsAdminRole
from .utils import log_activity
from rest_framework.permissions import IsAuthenticated

class GunViewSet(viewsets.ModelViewSet):
    queryset = models.Guns.objects.all().order_by("-id")
    serializer_class = serializers.GunSerializer
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def import_xlsx(self, request):
        file = request.FILES.get("file")

        if not file:
            return Response(
                {"detail": "No file uploaded. Use form-data with key `file`."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not file.name.endswith((".xlsx", ".xls")):
            return Response(
                {"detail": "Only .xlsx or .xls files are allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            df = pd.read_excel(file)
        except Exception as e:
            return Response(
                {"detail": f"Failed to read Excel file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if df.empty:
            return Response(
                {"detail": "The uploaded Excel file is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Normalize headers
        df.columns = [str(col).strip().lower() for col in df.columns]

        # Expected based on your screenshot/model
        required_columns = [
            "type",
            "make",
            "caliber",
            "serial_no",
            "property_no",
        ]

        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            return Response(
                {
                    "detail": "Missing required columns.",
                    "missing_columns": missing,
                    "received_columns": list(df.columns),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        def clean_str(value):
            if pd.isna(value):
                return None
            value = str(value).strip()
            return value if value else None

        def clean_int(value, default=0):
            if pd.isna(value) or value == "":
                return default
            try:
                return int(float(value))
            except (ValueError, TypeError):
                return default

        def clean_decimal(value, default="0"):
            if pd.isna(value) or value == "":
                return Decimal(default)
            try:
                # remove commas if excel contains formatted numbers
                return Decimal(str(value).replace(",", "").strip())
            except (InvalidOperation, ValueError, TypeError):
                return Decimal(default)

        def clean_date(value):
            if pd.isna(value) or value == "":
                return None

            # If only year is provided like 2022
            if isinstance(value, (int, float)) and not pd.isna(value):
                year = int(value)
                if 1900 <= year <= 2100:
                    return timezone.datetime(year, 1, 1).date()

            try:
                parsed = pd.to_datetime(value, errors="coerce")
                if pd.isna(parsed):
                    return None
                return parsed.date()
            except Exception:
                return None

        def map_source(value):
            raw = clean_str(value)
            if not raw:
                return "PROCURED"

            raw_upper = raw.upper().replace(" ", "_")
            valid = {"PROCURED", "DONATED_FOUND_AT_STATION", "LOANED"}
            return raw_upper if raw_upper in valid else "PROCURED"

        def map_status(value):
            raw = clean_str(value)
            if not raw:
                return "SVC"

            raw_upper = raw.upper()
            valid = {"SVC", "UNSVC", "BER"}
            return raw_upper if raw_upper in valid else "SVC"

        created = 0
        updated = 0
        errors = []

        with transaction.atomic():
            for index, row in df.iterrows():
                excel_row = index + 2  # row 1 is header in Excel

                try:
                    serial_no = clean_str(row.get("serial_no"))
                    property_no = clean_str(row.get("property_no"))

                    if not serial_no and not property_no:
                        errors.append({
                            "row": excel_row,
                            "detail": "Either serial_no or property_no is required."
                        })
                        continue

                    defaults = {
                        "type": clean_str(row.get("type")),
                        "make": clean_str(row.get("make")),
                        "caliber": clean_str(row.get("caliber")),
                        "acquisition_date": clean_date(row.get("acquisition_date")),
                        "acquisition_cost": clean_decimal(row.get("acquisition_cost")),
                        "cost_of_repair": clean_decimal(row.get("cost_of_repair")),
                        "current_depreciated_value": clean_decimal(row.get("current_depreciated_value")),
                        "source": map_source(row.get("source")),
                        "status": map_status(row.get("status")),
                        "balance_qty": clean_int(row.get("balance_qty")),
                        "balance_value": clean_decimal(row.get("balance_value")),
                        "on_hand_qty": clean_int(row.get("on_hand_qty")),
                        "on_hand_value": clean_decimal(row.get("on_hand_value")),
                        "short_qty": clean_int(row.get("short_qty")),
                        "short_value": clean_decimal(row.get("short_value")),
                        "over_qty": clean_int(row.get("over_qty")),
                        "over_value": clean_decimal(row.get("over_value")),
                    }

                    # Prefer property_no as unique identity, fallback to serial_no
                    if property_no:
                        gun, was_created = models.Guns.objects.update_or_create(
                            property_no=property_no,
                            defaults={
                                **defaults,
                                "serial_no": serial_no,
                            }
                        )
                    else:
                        gun, was_created = models.Guns.objects.update_or_create(
                            serial_no=serial_no,
                            defaults={
                                **defaults,
                                "property_no": property_no,
                            }
                        )

                    # Optional: create/update issued person if columns exist
                    name = clean_str(row.get("name"))
                    unit = clean_str(row.get("unit"))
                    sub_unit = clean_str(row.get("sub_unit"))

                    if name:
                        person_defaults = {
                            "name": name,
                            "unit": unit,
                            "sub_unit": sub_unit,
                        }

                        person, _ = models.Persons.objects.update_or_create(
                            gun=gun,
                            defaults=person_defaults,
                        )

                    if was_created:
                        created += 1
                    else:
                        updated += 1

                except Exception as e:
                    errors.append({
                        "row": excel_row,
                        "detail": str(e),
                    })

        return Response(
            {
                "detail": "Import completed.",
                "created": created,
                "updated": updated,
                "errors": errors,
            },
            status=status.HTTP_200_OK,
        )