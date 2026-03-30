from rest_framework import serializers
from quickstart import models


class AbsoluteFileUrlMixin:
    def build_abs(self, request, file_field):
        if not file_field:
            return None
        url = file_field.url
        return request.build_absolute_uri(url) if request else url


class GunHistorySerializer(serializers.ModelSerializer):
    image_urls = serializers.SerializerMethodField()

    class Meta:
        model = models.GunHistory
        fields = ["id", "date", "event_type", "disposition", "image_urls"]

    def get_image_urls(self, obj):
        request = self.context.get("request")
        urls = []
        for im in obj.images.all().order_by("id"):
            if not im.img:
                continue
            url = im.img.url
            urls.append(request.build_absolute_uri(url) if request else url)
        return urls


class GunSerializer(serializers.ModelSerializer):
    history = GunHistorySerializer(many=True, read_only=True)
    issued_to = serializers.SerializerMethodField()

    class Meta:
        model = models.Guns
        fields = [
            "id",
            "faid",
            "serial_no",
            "make",
            "model",
            "kind",
            "caliber",
            "status",
            "validated",
            "disposition",
            "issued_to",
            "history",
        ]

    def get_issued_to(self, obj):
        # If related_name is "issued_to", this works:
        person = getattr(obj, "issued_to", None)
        if not person:
            return None

        return {
            "id": person.id,
            "rank": person.rank,
            "name": person.name,
            "full_name": f"{person.rank or ''} {person.name or ''}".strip(),
            "unit": person.unit,
            "sub_unit": person.sub_unit,
            "station": person.station,
            "issued_unit": person.issued_unit,
        }


class ParsSerializer(serializers.ModelSerializer):
    img_url = serializers.SerializerMethodField()

    class Meta:
        model = models.Pars
        fields = ["id", "person", "date", "img", "img_url"]
        extra_kwargs = {"img": {"write_only": True, "required": False, "allow_null": True}}

    def get_img_url(self, obj):
        request = self.context.get("request")
        return AbsoluteFileUrlMixin().build_abs(request, obj.img)


class PersonSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    gun_details = GunSerializer(source="gun", read_only=True)
    par_files = ParsSerializer(source="pars", many=True, read_only=True)

    # ✅ to assign a gun when creating/updating
    gun_id = serializers.PrimaryKeyRelatedField(
        queryset=models.Guns.objects.all(),
        source="gun",
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = models.Persons
        fields = [
            "id",
            "rank",
            "name",
            "full_name",
            "unit",
            "sub_unit",
            "station",
            "issued_unit",
            "gun_details",
            "gun_id",
            "par_files",
        ]

    def get_full_name(self, obj):
        return f"{obj.rank or ''} {obj.name or ''}".strip()


# ✅ payload for issuing a gun
class IssueGunSerializer(serializers.Serializer):
    gun_id = serializers.IntegerField()
    rank = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    unit = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    sub_unit = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    station = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    issued_unit = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    date = serializers.DateField(required=False)
    img = serializers.FileField(required=False, allow_null=True)


class TurnInGunSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    img = serializers.FileField(required=False, allow_null=True)


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ActivityLog
        fields = "__all__"