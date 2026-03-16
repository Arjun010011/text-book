from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Provider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Book',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_id', models.CharField(max_length=120)),
                ('title', models.CharField(max_length=500)),
                ('authors', models.CharField(blank=True, max_length=500)),
                ('language', models.CharField(blank=True, max_length=120)),
                ('grade', models.CharField(blank=True, max_length=20)),
                ('subject', models.CharField(blank=True, max_length=120)),
                ('school_type', models.CharField(blank=True, max_length=50)),
                ('syllabus', models.CharField(blank=True, max_length=120)),
                ('download_url', models.URLField(blank=True, max_length=1000)),
                ('source_url', models.URLField(blank=True, max_length=1000)),
                ('cover_url', models.URLField(blank=True, max_length=1000)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='catalog.provider')),
            ],
            options={
                'unique_together': {('provider', 'external_id')},
            },
        ),
        migrations.AddIndex(
            model_name='book',
            index=models.Index(fields=['provider', 'external_id'], name='catalog_boo_provider_ae7d2c_idx'),
        ),
        migrations.AddIndex(
            model_name='book',
            index=models.Index(fields=['grade', 'subject'], name='catalog_boo_grade_6d3b60_idx'),
        ),
    ]
