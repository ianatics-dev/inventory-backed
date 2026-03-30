from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user
            and user.is_authenticated
            and hasattr(user, "profile")
            and user.profile.role in ["admin", "super_admin"]
        )


class IsSuperAdminRole(BasePermission):
    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        return hasattr(user, "profile") and user.profile.role == "super_admin"


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        return hasattr(user, "profile") and user.profile.role in ["admin", "super_admin"]
#
# class IsSuperAdminRole(BasePermission):
#     def has_permission(self, request, view):
#         user = request.user
#         return bool(
#             user
#             and user.is_authenticated
#             and hasattr(user, "profile")
#             and user.profile.role == "super_admin"
#         )