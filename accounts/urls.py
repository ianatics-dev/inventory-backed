from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LoginView, MeView, UserManagementViewSet

router = DefaultRouter()
router.register("users", UserManagementViewSet, basename="users")

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path("", include(router.urls)),
]