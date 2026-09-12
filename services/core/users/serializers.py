from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "role",
            "organization", "is_active", "date_joined",
        ]
        read_only_fields = ["id", "organization", "date_joined"]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "password", "is_active"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        # `organization` la fija el ViewSet (OrganizationScopedModelViewSet),
        # nunca el body de la request.
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class MeSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "organization_id", "is_staff", "is_superuser"]
        read_only_fields = fields
