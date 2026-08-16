from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="LoginThrottleBucket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64, unique=True)),
                ("failures", models.PositiveIntegerField(default=0)),
                ("window_started_at", models.DateTimeField()),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "login throttle bucket",
                "verbose_name_plural": "login throttle buckets",
                "ordering": ("updated_at",),
            },
        ),
    ]
