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

def norm(v) -> str:
    # ✅ handles NaN / NaT / None
    if v is None:
        return ""
    if isinstance(v, float) and np.isnan(v):
        return ""
    if pd.isna(v):
        return ""
    s = str(v).strip()
    # ✅ extra safety (sometimes "nan" comes as string already)
    if s.lower() in ["nan", "none", "null", "nat"]:
        return ""
    return s

def norm_upper(v) -> str:
    return norm(v).upper()

def norm_validated(s: str) -> str:
    v = norm_upper(s)
    if v in ["VALIDATED", "YES", "TRUE", "1"]:
        return "Validated"
    if v in ["NOT VALIDATED", "NO", "FALSE", "0", "NOTVALIDATED"]:
        return "Not Validated"
    # keep original if unknown
    return norm(s) or "Not Validated"

def norm_disposition(s: str) -> str:
    v = norm_upper(s).replace(" ", "_").replace("-", "_")
    # expected: ON_STOCK, FOR_RELEASE, ISSUED
    if v in ["ON_STOCK", "ONSTOCK"]:
        return "ON_STOCK"
    if v in ["FOR_RELEASE", "FORRELEASE"]:
        return "FOR_RELEASE"
    if v in ["ISSUED"]:
        return "ISSUED"
    return "ON_STOCK"

def split_rank_and_name(full_name: str):
    s = norm(full_name)
    if not s:
        return "", ""

    parts = s.split()
    if len(parts) == 1:
        return "", parts[0]

    rank = parts[0].strip()
    name = " ".join(parts[1:]).strip()
    return rank, name


def split_mmkc(value):
    """
    Example values:
    JERICHO // PISTOL / 9MM
    GLOCK / G17 GEN4 / PISTOL / 9MM
    CANIK / TP9SF ELITE-S / PISTOL / 9MM
    """
    s = norm(value)
    if not s:
        return "", "", "", ""

    s = s.replace("//", "/")
    parts = [p.strip() for p in s.split("/") if p.strip()]

    make = parts[0] if len(parts) > 0 else ""
    model = parts[1] if len(parts) > 1 else ""
    kind = parts[2] if len(parts) > 2 else ""
    caliber = parts[3] if len(parts) > 3 else ""

    return make, model, kind, caliber

class GunViewSet(viewsets.ModelViewSet):
    queryset = models.Guns.objects.all().order_by("-id")
    serializer_class = serializers.GunSerializer
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    @action(detail=False, methods=["get"])
    def for_release(self, request):
        qs = self.get_queryset().filter(disposition="FOR_RELEASE")
        ser = self.get_serializer(qs, many=True, context={"request": request})

        return Response(ser.data, status=200)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def issue(self, request, pk=None):
        gun = self.get_object()

        existing_person = getattr(gun, "issued_to", None)

        if existing_person and gun.disposition != "ISSUED":
            existing_person.gun = None
            existing_person.save()
            existing_person = None

        if gun.disposition == "ISSUED" or existing_person is not None:
            return Response({"detail": "This gun is already issued."}, status=400)

        rank = request.data.get("rank")
        name = request.data.get("name")
        unit = request.data.get("unit")
        sub_unit = request.data.get("sub_unit")
        station = request.data.get("station")
        issued_unit = request.data.get("issued_unit")
        date_str = request.data.get("date")

        if not all([rank, name, unit, sub_unit, station, issued_unit]):
            return Response({"detail": "Missing required fields."}, status=400)

        if date_str:
            try:
                issue_date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                return Response({"date": "Invalid date format. Use YYYY-MM-DD."}, status=400)
        else:
            issue_date = timezone.now().date()

        imgs = request.FILES.getlist("img")[:2]

        with transaction.atomic():
            person = models.Persons.objects.create(
                rank=rank,
                name=name,
                unit=unit,
                sub_unit=sub_unit,
                station=station,
                issued_unit=issued_unit,
                gun=gun,
            )

            gun.disposition = "ISSUED"
            gun.save()

            hist = models.GunHistory.objects.create(
                gun=gun,
                person=person,
                event_type="ISSUED",
                disposition="ISSUED",
                date=issue_date,
            )

            for f in imgs:
                models.GunHistoryImage.objects.create(history=hist, img=f)

        out = self.get_serializer(gun, context={"request": request}).data
        return Response(out, status=200)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def turn_in(self, request, pk=None):
        gun = self.get_object()

        date_str = request.data.get("date")
        if date_str:
            try:
                d = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                return Response({"date": "Invalid date format. Use YYYY-MM-DD."}, status=400)
        else:
            d = timezone.now().date()

        imgs = request.FILES.getlist("img")
        if not imgs:
            imgs = request.FILES.getlist("images")
        imgs = imgs[:2]

        person = getattr(gun, "issued_to", None)

        with transaction.atomic():
            if person:
                person.gun = None
                person.save()

            gun.disposition = "ON_STOCK"
            gun.save()

            hist = models.GunHistory.objects.create(
                gun=gun,
                person=person,
                event_type="TURN_IN",
                disposition="ON_STOCK",
                date=d,
            )

            for f in imgs:
                models.GunHistoryImage.objects.create(history=hist, img=f)

        out = serializers.GunSerializer(gun, context={"request": request}).data
        return Response(out, status=200)

    def update(self, request, *args, **kwargs):
        """
        Handles:
        1. firearm table edit
        2. issued table edit (gun + issued person fields)

        Accepted gun fields:
        - faid
        - serial_no
        - make
        - model
        - kind
        - caliber
        - disposition
        - validated

        Accepted issued person fields:
        - rank
        - name
        - unit
        - sub_unit
        - station
        - issued_unit

        Optional:
        - full_name  (fallback only)
        """
        partial = kwargs.pop("partial", False)
        gun = self.get_object()
        data = request.data

        gun_fields = [
            "faid",
            "serial_no",
            "make",
            "model",
            "kind",
            "caliber",
            "disposition",
            "validated",
        ]

        person_fields = [
            "rank",
            "name",
            "unit",
            "sub_unit",
            "station",
            "issued_unit",
        ]

        try:
            with transaction.atomic():
                # update gun fields
                for field in gun_fields:
                    if field in data:
                        setattr(gun, field, data.get(field))

                # update issued person if currently assigned
                person = getattr(gun, "issued_to", None)

                if person:
                    for field in person_fields:
                        if field in data:
                            setattr(person, field, data.get(field))

                    # optional fallback if frontend sends only full_name
                    full_name = data.get("full_name")
                    if full_name and "rank" not in data and "name" not in data:
                        full_name = str(full_name).strip()
                        if full_name:
                            if " " in full_name:
                                guessed_rank, guessed_name = full_name.split(" ", 1)
                                person.rank = guessed_rank
                                person.name = guessed_name
                            else:
                                person.name = full_name

                    person.save()

                gun.save()

        except Exception as e:
            return Response(
                {"detail": f"Update failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        out = self.get_serializer(gun, context={"request": request}).data
        return Response(out, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Deletes a firearm record.
        Safer behavior:
        - do not allow delete if firearm is currently ISSUED
        - if linked person exists, unlink first
        """
        gun = self.get_object()
        person = getattr(gun, "issued_to", None)

        if gun.disposition == "ISSUED" or person is not None:
            return Response(
                {"detail": "Cannot delete a firearm that is currently issued. Turn it in first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                if person:
                    person.gun = None
                    person.save()

                gun.delete()

        except Exception as e:
            return Response(
                {"detail": f"Delete failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Firearm deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )


class PersonViewSet(viewsets.ModelViewSet):
    queryset = models.Persons.objects.all().order_by("-id")
    serializer_class = serializers.PersonSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAdminOrReadOnly, IsSuperAdminRole]


class ParsViewSet(viewsets.ModelViewSet):
    queryset = models.Pars.objects.select_related("person").all().order_by("-id")
    serializer_class = serializers.ParsSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAdminOrReadOnly, IsSuperAdminRole]

class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.ActivityLog.objects.all().order_by("-created_at")
    serializer_class = serializers.ActivityLogSerializer
    permission_classes = [IsSuperAdminRole]

    def get_queryset(self):
        qs = super().get_queryset()

        user = self.request.query_params.get("user")
        action = self.request.query_params.get("action")
        module = self.request.query_params.get("module")

        if user:
            qs = qs.filter(username__icontains=user)

        if action:
            qs = qs.filter(action=action)

        if module:
            qs = qs.filter(module__icontains=module)

        return qs

class ActivityLogCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        action = request.data.get("action")
        module = request.data.get("module")
        description = request.data.get("description")
        target_id = request.data.get("target_id")
        target_name = request.data.get("target_name")

        if not action or not module or not description:
            return Response(
                {"detail": "action, module, and description are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_activity(
            request=request,
            action=action,
            module=module,
            description=description,
            target_id=target_id,
            target_name=target_name,
        )

        return Response({"detail": "Activity logged."}, status=status.HTTP_201_CREATED)



# ------------------------------------ for imports -----------------------------------------------------------
class ImportGunsExcel(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAdminOrReadOnly, IsSuperAdminRole]

    # POST multipart/form-data:
    # file: <xlsx>
    def post(self, request):
        f = request.FILES.get("file")
        if not f:
            return Response({"file": "This field is required."}, status=400)

        try:
            df = pd.read_excel(f)
        except Exception as e:
            return Response({"detail": f"Invalid excel file: {e}"}, status=400)

        # normalize column names
        df.columns = [str(c).strip().upper() for c in df.columns]

        required = [
            "FAID", "SERIAL NO.", "MAKE", "MODEL", "KIND", "CALIBER",
            "STATUS", "DISPOSITION", "VALIDATED"
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return Response({"detail": f"Missing columns: {missing}"}, status=400)

        created = 0
        updated = 0
        skipped = 0
        errors = []

        for idx, row in df.iterrows():
            try:
                faid = norm(row.get("FAID"))
                if not faid:
                    skipped += 1
                    continue

                payload = {
                    "faid": faid,
                    "serial_no": norm(row.get("SERIAL NO.")),
                    "make": norm(row.get("MAKE")),
                    "model": norm(row.get("MODEL")),
                    "kind": norm(row.get("KIND")),
                    "caliber": norm(row.get("CALIBER")),
                    "status": norm(row.get("STATUS")),
                    "validated": norm_validated(row.get("VALIDATED")),
                    "disposition": norm_disposition(row.get("DISPOSITION")),
                }

                # ✅ update by faid (unique identifier)
                obj = models.Guns.objects.filter(faid=faid).first()
                if obj:
                    for k, v in payload.items():
                        setattr(obj, k, v)
                    obj.save()
                    updated += 1
                else:
                    models.Guns.objects.create(**payload)
                    created += 1

            except Exception as e:
                errors.append({"row": int(idx) + 2, "faid": str(row.get("FAID")), "error": str(e)})

        return Response(
            {
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "errors": errors[:50],  # cap
            },
            status=status.HTTP_200_OK,
        )

class ImportIssuedExcel(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAdminOrReadOnly, IsSuperAdminRole]

    # POST multipart/form-data
    # file: <xlsx>
    def post(self, request):
        f = request.FILES.get("file")
        if not f:
            return Response({"file": "This field is required."}, status=400)

        try:
            df = pd.read_excel(f)
        except Exception as e:
            return Response({"detail": f"Invalid excel file: {e}"}, status=400)

        # normalize column names
        df.columns = [str(c).strip().upper() for c in df.columns]

        required = [
            "NAME",
            "UNIT",
            "SUBUNIT",
            "STATION",
            "ISSUING UNIT",
            "FAID",
            "SERIAL NO.",
            "MAKE/MODEL/KIND/CALIBER",
            "STATUS",
            "VALIDATED",
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return Response(
                {"detail": f"Missing columns: {missing}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_people = 0
        updated_people = 0
        created_guns = 0
        updated_guns = 0
        skipped = 0
        errors = []

        for idx, row in df.iterrows():
            try:
                full_name = norm(row.get("NAME"))
                faid = norm(row.get("FAID"))

                if not full_name or not faid:
                    skipped += 1
                    continue

                rank, person_name = split_rank_and_name(full_name)
                make, model, kind, caliber = split_mmkc(
                    row.get("MAKE/MODEL/KIND/CALIBER")
                )

                gun_payload = {
                    "faid": faid,
                    "serial_no": norm(row.get("SERIAL NO.")),
                    "make": make,
                    "model": model,
                    "kind": kind,
                    "caliber": caliber,
                    "status": norm(row.get("STATUS")),
                    "validated": norm_validated(row.get("VALIDATED")),
                    "disposition": "ISSUED",
                }

                # 1. create/update gun by FAID
                gun_obj = models.Guns.objects.filter(faid=faid).first()
                if gun_obj:
                    for k, v in gun_payload.items():
                        setattr(gun_obj, k, v)
                    gun_obj.save()
                    updated_guns += 1
                else:
                    gun_obj = models.Guns.objects.create(**gun_payload)
                    created_guns += 1

                # 2. because gun is OneToOne, make sure this gun is only linked to one person
                existing_owner = models.Persons.objects.filter(gun=gun_obj).first()

                person_payload = {
                    "rank": rank,
                    "name": person_name,
                    "unit": norm(row.get("UNIT")),
                    "sub_unit": norm(row.get("SUBUNIT")),
                    "station": norm(row.get("STATION")),
                    "issued_unit": norm(row.get("ISSUING UNIT")),
                    "gun": gun_obj,
                }

                # 3. find person
                # first try exact person
                person_obj = models.Persons.objects.filter(
                    rank__iexact=rank,
                    name__iexact=person_name,
                ).first()

                if person_obj:
                    # if this person already has another gun, unlink old gun first
                    if person_obj.gun and person_obj.gun != gun_obj:
                        old_gun = person_obj.gun
                        old_gun.disposition = "ON_STOCK"
                        old_gun.save()

                    for k, v in person_payload.items():
                        setattr(person_obj, k, v)
                    person_obj.save()
                    updated_people += 1

                    # if gun used to belong to another person, unlink that other person
                    if existing_owner and existing_owner.id != person_obj.id:
                        existing_owner.gun = None
                        existing_owner.save()

                else:
                    # if gun already belongs to another person, unlink first
                    if existing_owner:
                        existing_owner.gun = None
                        existing_owner.save()

                    models.Persons.objects.create(**person_payload)
                    created_people += 1

            except Exception as e:
                errors.append({
                    "row": int(idx) + 2,
                    "faid": str(row.get("FAID")),
                    "name": str(row.get("NAME")),
                    "error": str(e),
                })

        return Response(
            {
                "created_people": created_people,
                "updated_people": updated_people,
                "created_guns": created_guns,
                "updated_guns": updated_guns,
                "skipped": skipped,
                "errors": errors[:50],
            },
            status=status.HTTP_200_OK,
        )