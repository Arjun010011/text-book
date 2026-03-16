from django.db import models


class Provider(models.Model):
    key = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Book(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    external_id = models.CharField(max_length=120)
    title = models.CharField(max_length=500)
    authors = models.CharField(max_length=500, blank=True)
    language = models.CharField(max_length=120, blank=True)
    medium = models.CharField(max_length=120, blank=True)
    grade = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=120, blank=True)
    school_type = models.CharField(max_length=50, blank=True)
    syllabus = models.CharField(max_length=120, blank=True)
    board = models.CharField(max_length=120, blank=True)
    download_url = models.URLField(max_length=1000, blank=True)
    source_url = models.URLField(max_length=1000, blank=True)
    cover_url = models.URLField(max_length=1000, blank=True)
    local_path = models.CharField(max_length=1000, blank=True)
    file_size = models.BigIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    file_status = models.CharField(max_length=40, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['provider', 'external_id']),
            models.Index(fields=['grade', 'subject']),
        ]
        unique_together = ('provider', 'external_id')

    def __str__(self):
        return self.title
