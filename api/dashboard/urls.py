from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import viewsets


urlpatterns = [
    path('dashboard/', viewsets.DashboardViewset.as_view()),
    path('short_arm_pie/', viewsets.TotalShortFirearms.as_view()),
    path('long_arm_pie/', viewsets.TotalLongFirearms.as_view()),
    path('available_guns/', viewsets.GunsDropDownView.as_view()),
    path('available_guns_longarm/', viewsets.LongArmGunsDropDownView.as_view()),
    path("issued-summary-by-year/", viewsets.issued_summary_by_year),
    path("issued-details-by-year/<int:year>/", viewsets.issued_details_by_year),
    path("short-arm-acquisition-summary/", viewsets.short_arm_acquisition_summary),
    path("long-arm-acquisition-summary/", viewsets.long_arm_acquisition_summary),
    path("short-arm-acquisition-details/<str:year>/", viewsets.short_arm_acquisition_details),
    path("long-arm-acquisition-details/<str:year>/", viewsets.long_arm_acquisition_details),
]