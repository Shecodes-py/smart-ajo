from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0005_alter_otp_phone_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='phone_number',
            field=models.CharField(max_length=50, blank=True),
        ),
    ]
