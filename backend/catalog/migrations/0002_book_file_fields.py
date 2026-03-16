from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='medium',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='book',
            name='board',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='book',
            name='local_path',
            field=models.CharField(blank=True, max_length=1000),
        ),
        migrations.AddField(
            model_name='book',
            name='file_size',
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='book',
            name='checksum_sha256',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='book',
            name='file_status',
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
