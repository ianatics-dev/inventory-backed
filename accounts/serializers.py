from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()
    unit = serializers.CharField(allow_null=True, allow_blank=True)


class UserListSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="profile.role", read_only=True)
    unit = serializers.CharField(source="profile.unit", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "unit",
            "is_active",
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, default="viewer")
    unit = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "role",
            "unit",
            "is_active",
        ]

    def validate_role(self, value):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        if not hasattr(request.user, "profile"):
            raise serializers.ValidationError("User profile not found.")

        creator_role = request.user.profile.role

        if creator_role == "super_admin":
            if value not in ["admin", "viewer"]:
                raise serializers.ValidationError(
                    "Super admin can only create admin or viewer accounts."
                )
        elif creator_role == "admin":
            if value != "viewer":
                raise serializers.ValidationError(
                    "Admin can only create viewer accounts."
                )
        else:
            raise serializers.ValidationError(
                "You do not have permission to create users."
            )

        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_email(self, value):
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def create(self, validated_data):
        role = validated_data.pop("role", "viewer")
        unit = validated_data.pop("unit", "")
        password = validated_data.pop("password")

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=password,
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            is_active=validated_data.get("is_active", True),
        )

        if not hasattr(user, "profile"):
            UserProfile.objects.create(user=user)

        user.profile.role = role
        user.profile.unit = unit
        user.profile.save()

        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=False)
    unit = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "role",
            "unit",
            "is_active",
        ]

    def validate_role(self, value):
        request = self.context.get("request")
        target_user = self.instance

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        if not hasattr(request.user, "profile"):
            raise serializers.ValidationError("User profile not found.")

        editor_role = request.user.profile.role

        if editor_role == "admin":
            if value != "viewer":
                raise serializers.ValidationError(
                    "Admin can only assign viewer role."
                )

            if hasattr(target_user, "profile") and target_user.profile.role != "viewer":
                raise serializers.ValidationError(
                    "Admin can only edit viewer accounts."
                )

        return value

    def validate_username(self, value):
        qs = User.objects.filter(username=value).exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_email(self, value):
        if value:
            qs = User.objects.filter(email=value).exclude(id=self.instance.id)
            if qs.exists():
                raise serializers.ValidationError("Email already exists.")
        return value

    def update(self, instance, validated_data):
        request = self.context.get("request")
        editor_role = request.user.profile.role if hasattr(request.user, "profile") else None

        if editor_role == "admin":
            if hasattr(instance, "profile") and instance.profile.role != "viewer":
                raise serializers.ValidationError(
                    {"detail": "Admin can only edit viewer accounts."}
                )

        role = validated_data.pop("role", None)
        unit = validated_data.pop("unit", None)
        password = validated_data.pop("password", None)

        instance.username = validated_data.get("username", instance.username)
        instance.email = validated_data.get("email", instance.email)
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.is_active = validated_data.get("is_active", instance.is_active)

        if password:
            instance.set_password(password)

        instance.save()

        if not hasattr(instance, "profile"):
            UserProfile.objects.create(user=instance)

        if role is not None:
            instance.profile.role = role
        if unit is not None:
            instance.profile.unit = unit

        instance.profile.save()

        return instance