from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import viewsets
from . import import_file

router = DefaultRouter()
router.register(r"guns", viewsets.GunViewSet, basename="guns")
router.register(r"person", viewsets.PersonViewSet, basename="person")
router.register(r"pars", viewsets.ParsViewSet, basename="pars")
router.register(r"activity-logs", viewsets.ActivityLogViewSet, basename="activity-logs")

urlpatterns = [
    path("", include(router.urls)),
    path("activity-log/create-log/", viewsets.ActivityLogCreateView.as_view(), name="activity-log-create"),
    path("import-guns/", viewsets.ImportGunsExcel.as_view()),
    path("import-issued-excel/", viewsets.ImportIssuedExcel.as_view(), name="import-issued-excel"),
    # path(
    #     "import-inventory-whereabouts-excel/",
    #     import_file.ImportPhysicalCountExcel.as_view(),
    #     name="import-inventory-whereabouts-excel",
    # ),
]