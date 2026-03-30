from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    UserCreateSerializer,
    UserListSerializer,
    UserUpdateSerializer,
)
from .permissions import IsAdminRole, IsSuperAdminRole

from api.inventory.utils import log_activity


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"detail": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = authenticate(username=user_obj.username, password=password)
        if user is None:
            # ❌ Optional: log failed login attempt
            # log_activity(
            #     request=request,
            #     action="LOGIN",
            #     module="Authentication",
            #     description=f"Failed login attempt for email '{email}'",
            # )

            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # # ✅ SUCCESS LOGIN → LOG HERE
        # log_activity(
        #     request=request,
        #     action="LOGIN",
        #     module="Authentication",
        #     description=f"User '{user.username}' logged in successfully",
        #     target_id=user.id,
        #     target_name=user.username,
        # )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.profile.role,
                "unit": user.profile.unit,
            },
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.profile.role,
                "unit": user.profile.unit,
            }
        )


class UserManagementViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("-id")
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return UserUpdateSerializer
        return UserListSerializer

    def get_queryset(self):
        user = self.request.user

        if not hasattr(user, "profile"):
            return User.objects.none()

        role = user.profile.role

        if role == "super_admin":
            return User.objects.all().order_by("-id")

        if role == "admin":
            return User.objects.filter(profile__role="viewer").order_by("-id")

        return User.objects.none()

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)

        log_activity(
            request=request,
            action="VIEW",
            module="User Management",
            description="Viewed User Management table",
        )

        return response

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        response = super().retrieve(request, *args, **kwargs)

        log_activity(
            request=request,
            action="VIEW",
            module="User Management",
            description=f"Viewed user '{instance.username}'",
            target_id=instance.id,
            target_name=instance.username,
        )

        return response

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)

        if response.status_code in [200, 201]:
            username = response.data.get("username")
            user_id = response.data.get("id")

            log_activity(
                request=request,
                action="CREATE",
                module="User Management",
                description=f"Created user '{username}'",
                target_id=user_id,
                target_name=username,
            )

        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_username = instance.username

        response = super().update(request, *args, **kwargs)

        if response.status_code in [200, 202]:
            log_activity(
                request=request,
                action="UPDATE",
                module="User Management",
                description=f"Updated user '{old_username}'",
                target_id=instance.id,
                target_name=old_username,
            )

        return response

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_username = instance.username

        response = super().partial_update(request, *args, **kwargs)

        if response.status_code in [200, 202]:
            log_activity(
                request=request,
                action="UPDATE",
                module="User Management",
                description=f"Partially updated user '{old_username}'",
                target_id=instance.id,
                target_name=old_username,
            )

        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if not hasattr(request.user, "profile"):
            return Response(
                {"detail": "User profile not found."},
                status=status.HTTP_403_FORBIDDEN,
            )

        requester_role = request.user.profile.role
        target_role = instance.profile.role if hasattr(instance, "profile") else None

        if requester_role == "admin":
            if target_role != "viewer":
                return Response(
                    {"detail": "Admin can only delete viewer accounts."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        elif requester_role == "super_admin":
            if target_role == "super_admin":
                return Response(
                    {"detail": "Super admin cannot delete another super admin here."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            return Response(
                {"detail": "You do not have permission to delete users."},
                status=status.HTTP_403_FORBIDDEN,
            )

        username = instance.username
        user_id = instance.id

        instance.delete()

        log_activity(
            request=request,
            action="DELETE",
            module="User Management",
            description=f"Deleted user '{username}'",
            target_id=user_id,
            target_name=username,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)