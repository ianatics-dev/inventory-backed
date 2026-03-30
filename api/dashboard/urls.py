from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import viewsets


urlpatterns = [
    path('dashboard/', viewsets.DashboardViewset.as_view()),
    path('short_arm_pie/', viewsets.TotalShortFirearms.as_view()),
    path('long_arm_pie/', viewsets.TotalShortFirearms.as_view()),
]