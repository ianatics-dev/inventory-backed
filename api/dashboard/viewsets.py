from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Count
from quickstart import models

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from quickstart import models
from accounts.permissions import IsAdminOrReadOnly

class DashboardViewset(APIView):
    permission_classes = [IsAdminOrReadOnly]
    def get(self, request, format=None):
        guns_count = models.Guns.objects.count()

        issued_count = models.Guns.objects.filter(disposition="ISSUED").count()
        on_stock_count = models.Guns.objects.filter(disposition__in=["ON_STOCK", "FOR_RELEASE"]).count()
        on_stock_validated = models.Guns.objects.filter(disposition__in=["ON_STOCK", "FOR_RELEASE"],
                                                        validated="Validated").count()

        issued_validated = models.Guns.objects.filter(disposition="ISSUED", validated="Validated").count()
        # on_stock_validated = models.Guns.objects.filter(disposition="ON_STOCK", validated="Validated").count()

        total_validated = models.Guns.objects.filter(validated="Validated").count()

        data = {
            "guns_count": guns_count,
            "issued_count": issued_count,
            "on_stock_count": on_stock_count,
            "issued_validated": issued_validated,
            "on_stock_validated": on_stock_validated,
            "total_validated": total_validated,
        }
        return Response(data)

class TotalShortFirearms(APIView):
    def get(self, request, format=None):
        makes_count = (
            models.Guns.objects
            .exclude(make__isnull=True)
            .exclude(make='')
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
def long_arm_pie(request):
    data = [
        {"name": "M16", "value": 62},
        {"name": "M4", "value": 45},
        {"name": "GALIL", "value": 30},
        {"name": "SMG", "value": 15},
        {"name": "THOMPSON", "value": 10},
        {"name": "NORINCO", "value": 8},
    ]
    return Response(data)
