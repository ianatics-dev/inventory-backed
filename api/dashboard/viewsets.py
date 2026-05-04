from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Count, Case, When, Value, CharField
from quickstart import models

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from quickstart import models
from accounts.permissions import IsAdminOrReadOnly
from api.inventory import serializers
from django.db.models.functions import ExtractYear, Cast
from rest_framework.pagination import PageNumberPagination



SHORT_ARM_TYPES = ["PISTOL", "REVOLVER"]


class AcquisitionDetailsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class DashboardViewset(APIView):
    permission_classes = [IsAdminOrReadOnly]
    def get(self, request, format=None):
        guns_count = models.Guns.objects.count()

        issued_count = models.Guns.objects.filter(disposition="ISSUED").count()
        on_stock_count = models.Guns.objects.filter(disposition="ON_STOCK").count()
        unsvc_items = models.Guns.objects.filter(status="UNSVC").count()
        ber_items = models.Guns.objects.filter(status="BER").count()
        # issued_validated = models.Guns.objects.filter(disposition="ISSUED").count()
        # on_stock_validated = models.Guns.objects.filter(disposition="ON_STOCK", validated="Validated").count()

        # total_validated = models.Guns.objects.filter(validated="Validated").count()

        data = {
            "guns_count": guns_count,
            "issued_count": issued_count,
            "on_stock_count": on_stock_count,
            # "issued_validated": issued_validated,
            # "on_stock_validated": on_stock_validated,
            # "total_validated": total_validated,
            "problem": unsvc_items + ber_items
        }
        return Response(data)

class TotalShortFirearms(APIView):
    def get(self, request, format=None):
        makes_count = (
            models.Guns.objects
            .exclude(make__isnull=True)
            .exclude(make='')
            .filter(type__iexact="Pistol")
            .values('make')
            .annotate(total=Count('make'))
            .order_by('-total')  # optional
        )

        data = [
            {"name": row["make"], "value": row["total"]}
            for row in makes_count
        ]

        return Response(data)

class TotalLongFirearms(APIView):
    def get(self, request, format=None):
        makes_count = (
            models.Guns.objects
            .exclude(make__isnull=True)
            .exclude(make='')
            .exclude(type__iexact="Pistol")
            .values('make')
            .annotate(total=Count('make'))
            .order_by('-total')  # optional
        )

        data = [
            {"name": row["make"], "value": row["total"]}
            for row in makes_count
        ]

        return Response(data)

@api_view(["GET"])
def issued_summary_by_year(request):
    data = (
        models.GunHistory.objects
        .filter(event_type="ISSUED", date__isnull=False)
        .annotate(year=ExtractYear("date"))
        .values("year")
        .annotate(issued=Count("id"))
        .order_by("year")
    )

    return Response([
        {
            "year": item["year"],
            "issued": item["issued"],
        }
        for item in data
    ])


@api_view(["GET"])
def issued_details_by_year(request, year):
    histories = (
        models.GunHistory.objects
        .filter(event_type="ISSUED", date__year=year)
        .select_related("gun", "person")
        .order_by("-date", "-id")
    )

    rows = []

    for history in histories:
        gun = history.gun
        person = history.person

        rows.append({
            "id": history.id,
            "serial_no": gun.serial_no if gun else "",
            "type": gun.type if gun else "",
            "make": gun.make if gun else "",
            "issued_to": person.name if person else "",
            "rank": getattr(person, "rank", ""),
            "unit": person.unit if person else "",
            "sub_unit": person.sub_unit if person else "",
            "date_issued": history.date,
        })

    return Response(rows)

class GunsDropDownView(APIView):
    permission_classes = [IsAdminOrReadOnly]
    def get(self, request):

        data = models.Guns.objects.filter(disposition="ON_STOCK")
        serializer = serializers.GunSerializer(data, many=True)

        return Response(serializer.data)

class LongArmGunsDropDownView(APIView):
    permission_classes = [IsAdminOrReadOnly]
    def get(self, request):

        data = models.Guns.objects.filter(disposition="ON_STOCK").exclude(type__iexact="Pistol")
        serializer = serializers.GunSerializer(data, many=True)



        return Response(serializer.data)


def acquisition_summary_queryset(qs):
    dated = (
        qs.filter(acquisition_date__isnull=False)
        .annotate(year=Cast(ExtractYear("acquisition_date"), CharField()))
        .values("year")
        .annotate(count=Count("id"))
        .order_by("year")
    )

    no_date_count = qs.filter(acquisition_date__isnull=True).count()

    data = list(dated)

    if no_date_count > 0:
        data.append({
            "year": "No Date",
            "count": no_date_count,
        })

    return data


@api_view(["GET"])
def short_arm_acquisition_summary(request):
    qs = models.Guns.objects.filter(type__in=SHORT_ARM_TYPES)

    return Response(acquisition_summary_queryset(qs))


@api_view(["GET"])
def long_arm_acquisition_summary(request):
    qs = models.Guns.objects.exclude(type__in=SHORT_ARM_TYPES)

    return Response(acquisition_summary_queryset(qs))


def paginate_guns(request, qs):
    paginator = AcquisitionDetailsPagination()
    page = paginator.paginate_queryset(qs, request)

    data = [
        {
            "id": gun.id,
            "serial_no": gun.serial_no,
            "type": gun.type,
            "make": gun.make,
            "caliber": gun.caliber,
            "property_no": gun.property_no,
            "acquisition_date": gun.acquisition_date,
            "status": gun.status,
            "disposition": gun.disposition,
        }
        for gun in page
    ]

    return paginator.get_paginated_response(data)


@api_view(["GET"])
def short_arm_acquisition_details(request, year):
    qs = models.Guns.objects.filter(type__in=SHORT_ARM_TYPES)

    if year == "no-date":
        qs = qs.filter(acquisition_date__isnull=True)
    else:
        qs = qs.filter(acquisition_date__year=year)

    qs = qs.order_by("type", "make", "serial_no")

    return paginate_guns(request, qs)


@api_view(["GET"])
def long_arm_acquisition_details(request, year):
    qs = models.Guns.objects.exclude(type__in=SHORT_ARM_TYPES)

    if year == "no-date":
        qs = qs.filter(acquisition_date__isnull=True)
    else:
        qs = qs.filter(acquisition_date__year=year)

    qs = qs.order_by("type", "make", "serial_no")

    return paginate_guns(request, qs)