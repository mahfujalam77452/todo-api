import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0002_bulkemail'),
        ('teams', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DailySummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_date', models.DateField()),
                ('sent_to', models.EmailField(blank=True, max_length=254)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='daily_summaries', to='teams.team')),
            ],
            options={
                'ordering': ['-report_date', 'team_id'],
                'constraints': [models.UniqueConstraint(fields=('team', 'report_date'), name='daily_summary_team_date_unique')],
            },
        ),
    ]