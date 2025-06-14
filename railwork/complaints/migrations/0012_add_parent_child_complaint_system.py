# Generated by Django 5.2.1 on 2025-06-05 11:03

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('complaints', '0011_populate_hash_ids'),
    ]

    operations = [
        migrations.AddField(
            model_name='complaint',
            name='closed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Closed At'),
        ),
        migrations.AddField(
            model_name='complaint',
            name='closed_status',
            field=models.CharField(blank=True, choices=[('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'), ('RESOLVED', 'Resolved')], max_length=20, null=True, verbose_name='Status When Closed'),
        ),
        migrations.AddField(
            model_name='complaint',
            name='intensity_count',
            field=models.IntegerField(default=0, help_text='Number for daughter complaints (1, 2, 3...)', verbose_name='Intensity Count'),
        ),
        migrations.AddField(
            model_name='complaint',
            name='is_closed',
            field=models.BooleanField(default=False, verbose_name='Is Closed'),
        ),
        migrations.AddField(
            model_name='complaint',
            name='parent_complaint',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='daughter_complaints', to='complaints.complaint', verbose_name='Parent Complaint'),
        ),
        migrations.AlterField(
            model_name='complaint',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'), ('RESOLVED', 'Resolved')], default='PENDING', max_length=20, verbose_name='Status'),
        ),
    ]
